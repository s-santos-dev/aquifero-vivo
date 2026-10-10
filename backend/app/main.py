from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.v1 import router as api_v1_router
from app.climate.api import router as climate_router
from app.config import get_settings

app = FastAPI(
    title="Aquífero Vivo API",
    summary="Dados operacionais e hidrogeológicos do Aquífero Vivo",
    description=(
        "API REST versionada para consulta de poços, setores de atendimento e "
        "séries de medições. Todas as coleções oferecem paginação e filtros tipados."
    ),
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "Projeto Aquífero Vivo"},
    license_info={"name": "Uso interno"},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse()


app.include_router(api_v1_router)
app.include_router(climate_router)
