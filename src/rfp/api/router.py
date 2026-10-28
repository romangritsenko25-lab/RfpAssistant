"""The assembled ``/api`` router."""

from fastapi import APIRouter

from rfp.api import auth_routes, jobs_routes, knowledge_routes, logs_routes
from rfp.api.schemas import ErrorResponse

api_router = APIRouter(
    prefix="/api",
    responses={401: {"model": ErrorResponse, "description": "Not logged in"}},
)
for module in (auth_routes, jobs_routes, knowledge_routes, logs_routes):
    api_router.include_router(module.router)
