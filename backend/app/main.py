from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api import errors
from app.api.v1.router import router
from app.core.config import settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # fail fast if config is unloadable rather than at first request
    from app.domain.policy.engine import policy_version
    from app.domain.constraints.kernel import constraint_version
    from app.domain.taxonomy.loader import taxonomy_version
    policy_version(); constraint_version(); taxonomy_version()
    yield
    from app.executors.idempotency import STORE
    await STORE.close()


app = FastAPI(title="dunnflow", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,     # allow-list from env, never "*"
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def _request_id_and_headers(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = request.state.request_id
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


errors.install(app)
app.include_router(router)
