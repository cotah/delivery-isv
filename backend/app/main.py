from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router

app = FastAPI(
    title="ISV Delivery API",
    version=__version__,
)

# CORS aberto para dev local. Produção terá allow_origins específico por ambiente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
