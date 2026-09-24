from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import __version__
from app.api import insights, knowledge, system, tickets, triage
from app.config import settings


def _operation_id(route: APIRoute) -> str:
    # Clean operationIds (e.g. "list_tickets") in the OpenAPI contract.
    return route.name


app = FastAPI(
    title="Swiss Life Triage Agent API",
    version=__version__,
    generate_unique_id_function=_operation_id,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every route lives under /api so the frontend dev proxy and any deployment
# can forward a single prefix.
api = APIRouter(prefix="/api")
for module in (system, tickets, triage, knowledge, insights):
    api.include_router(module.router)
app.include_router(api)
