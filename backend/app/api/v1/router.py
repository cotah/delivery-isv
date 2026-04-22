"""Router central do v1 (ADR-020 + ADR-021).

Agrupa todos os sub-routers da API v1 sob o prefixo `/api/v1/`.
Cada módulo de rota (stores, products, etc.) exporta seu próprio
APIRouter e é incluído aqui em checkpoints subsequentes.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

# Rotas individuais serão incluídas aqui em checkpoints seguintes.
# Ex: router.include_router(stores.router)  # Checkpoint 1b
