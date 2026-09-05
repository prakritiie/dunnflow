from __future__ import annotations
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import DunnflowError
from app.core.logging import log


def _body(code, message, detail, request_id):
    return {"error": {"code": code, "message": message,
                      "detail": detail or {}, "request_id": request_id}}


def install(app):
    @app.exception_handler(DunnflowError)
    async def _domain(request: Request, exc: DunnflowError):
        rid = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(status_code=exc.status,
                            content=_body(exc.code, exc.message, exc.detail, rid))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", str(uuid.uuid4()))
        fields = [{"field": ".".join(str(x) for x in e["loc"][1:]), "issue": e["msg"]}
                  for e in exc.errors()]
        return JSONResponse(status_code=422,
                            content=_body("VALIDATION_FAILED", "Request validation failed",
                                          {"fields": fields}, rid))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", str(uuid.uuid4()))
        # never leak stack traces, SQL, or secrets to the client
        log.error("unhandled", request_id=rid, error=type(exc).__name__, message=str(exc))
        return JSONResponse(status_code=500,
                            content=_body("INTERNAL_ERROR", "An internal error occurred", {}, rid))
