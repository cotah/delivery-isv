"""Router central do v1 (ADR-020 + ADR-021).

Agrupa todos os sub-routers da API v1 sob o prefixo `/api/v1/`.
Cada módulo de rota (stores, products, etc.) exporta seu próprio
APIRouter e é incluído aqui em checkpoints subsequentes.
"""

from fastapi import APIRouter

from app.api.v1 import addresses, auth, customers, stores, users

router = APIRouter(prefix="/api/v1")

router.include_router(addresses.router)
router.include_router(auth.router)
router.include_router(customers.router)
router.include_router(stores.router)
router.include_router(users.router)
