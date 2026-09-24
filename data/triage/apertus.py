"""Minimal OpenAI-compatible client for the Swisscom Apertus endpoint.

Uses only the standard library so the pipeline needs no new dependencies. The
endpoint is vLLM-backed, so ``response_format`` with a strict JSON schema is
honoured by the decoder -- responses are grammar-constrained rather than
merely requested, which is what makes an open model reliable here.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

from . import config


class ApertusError(RuntimeError):
    pass


class _RateLimiter:
    """Shared minimum-interval limiter, which slows itself down on any 429.

    The gateway's effective limit sits below the documented 5 req/s under
    sustained load, so rather than guess a safe constant we start slow and
    back off further whenever the server pushes back. The rate never recovers
    during a run: a short job finishing slightly slower beats one that dies.
    """

    def __init__(self, per_second: float) -> None:
        self._interval = 1.0 / per_second
        self._max_interval = 1.0 / config.MIN_REQUESTS_PER_SECOND
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._interval

    def throttle(self) -> float:
        """Widen the request interval after a rate-limit response."""
        with self._lock:
            self._interval = min(self._interval * config.THROTTLE_FACTOR, self._max_interval)
            return self._interval


class ApertusClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        config.load_dotenv()
        self.api_key = api_key or os.environ.get(config.API_KEY_ENV, "")
        if not self.api_key:
            raise ApertusError(
                f"No API key. Set {config.API_KEY_ENV} in the environment or in "
                f"{config.DATA_DIR / '.env'} (see .env.example)."
            )
        self.base_url = (base_url or config.BASE_URL).rstrip("/")
        self.model = model or config.MODEL
        self._limiter = _RateLimiter(config.REQUESTS_PER_SECOND)

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        schema_name: str = "evidence",
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int = 400,
    ) -> dict:
        """One schema-constrained completion, returned as a parsed dict."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        if seed is not None:
            payload["seed"] = seed

        raw = self._post("/chat/completions", payload)
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ApertusError(f"Unexpected response shape: {raw}") from exc
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ApertusError(f"Model did not return JSON: {content[:300]}") from exc

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(config.MAX_RETRIES):
            self._limiter.acquire()
            request = urllib.request.Request(
                f"{self.base_url}{path}",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "jira-triage/1.0",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=config.REQUEST_TIMEOUT) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                # 401 means the key or entitlement is wrong; retrying cannot help.
                if exc.code in (401, 403):
                    raise ApertusError(f"HTTP {exc.code} -- check the key: {detail}") from exc
                last_error = ApertusError(f"HTTP {exc.code}: {detail}")
                if exc.code == 429:
                    # Slow every worker down, then wait out the window. The
                    # server's Retry-After wins if it sends one.
                    self._limiter.throttle()
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        backoff = float(retry_after) if retry_after else 0.0
                    except ValueError:
                        backoff = 0.0
                    time.sleep(max(backoff, 5.0 * (2**attempt)))
                    continue
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < config.MAX_RETRIES - 1:
                time.sleep(2.0 * (2**attempt))

        raise ApertusError(f"Request failed after {config.MAX_RETRIES} attempts: {last_error}")

    def healthcheck(self) -> str:
        """Cheap round-trip so failures surface before a long run starts."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
            "max_tokens": 8,
            "temperature": 0.0,
        }
        raw = self._post("/chat/completions", payload)
        return raw["choices"][0]["message"]["content"].strip()
