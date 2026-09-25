import createClient from 'openapi-fetch'
import type { paths } from './schema'

// Typed against the backend contract (schema.d.ts is generated from
// contracts/openapi.json). A wrong path, param or body is a compile error.
// Empty baseUrl = same origin (/api is proxied by Vite in dev).
export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL ?? '' })

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === 'object' && detail !== null && 'detail' in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : `Request failed with status ${status}`
    super(message)
    this.status = status
    this.detail = detail
  }
}

/** Turn openapi-fetch's {data, error} result into a value or a thrown ApiError. */
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok || data === undefined) throw new ApiError(response.status, error)
  return data
}
