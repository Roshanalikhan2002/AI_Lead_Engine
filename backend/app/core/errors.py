"""Consistent API errors and request context middleware."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.system.rate_limit import SENSITIVE_PREFIXES, enforce_rate_limit

logger = logging.getLogger(__name__)


def error_body(code: str, message: str, **extra: Any) -> dict:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if extra:
        payload["error"].update(extra)
    return payload


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        path = request.url.path
        try:
            if (
                path.startswith("/api/bookings/")
                or path.startswith("/api/book/")
                or path.startswith("/api/public/")
                or (path == "/api/meetings/book" and request.method == "POST")
            ):
                enforce_rate_limit(request, public_booking=True)
            elif any(path.startswith(p) for p in SENSITIVE_PREFIXES) and request.method != "GET":
                enforce_rate_limit(request, sensitive=True)
            elif path.startswith("/api/") and request.method != "GET":
                enforce_rate_limit(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=_normalize_http_detail(exc.detail),
                headers={"X-Request-ID": request_id},
            )

        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled error request_id=%s path=%s", request_id, path)
            return JSONResponse(
                status_code=500,
                content={
                    **error_body("INTERNAL_ERROR", "An unexpected error occurred."),
                    "detail": "An unexpected error occurred.",
                },
                headers={"X-Request-ID": request_id},
            )

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            path,
            response.status_code,
            duration_ms,
        )
        return response


def _normalize_http_detail(detail: Any) -> dict:
    """Preserve FastAPI `detail` for compatibility; add structured `error` when useful."""
    if isinstance(detail, dict) and "error" in detail:
        err = detail["error"]
        if "detail" not in detail and isinstance(err, dict):
            return {**detail, "detail": err.get("message", "Request failed.")}
        return detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return {
            "detail": detail,
            "error": {"code": str(detail["code"]), "message": str(detail["message"])},
        }
    if isinstance(detail, str):
        return {"detail": detail, "error": {"code": "HTTP_ERROR", "message": detail}}
    if isinstance(detail, list):
        return {
            "detail": jsonable_encoder(detail),
            "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed."},
        }
    return {"detail": detail, **error_body("HTTP_ERROR", "Request failed.")}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)
        body = _normalize_http_detail(exc.detail)
        headers = {"X-Request-ID": request_id} if request_id else None
        return JSONResponse(status_code=exc.status_code, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(exc.errors()),
                "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed."},
            },
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled exception request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={
                **error_body("INTERNAL_ERROR", "An unexpected error occurred."),
                "detail": "An unexpected error occurred.",
            },
            headers={"X-Request-ID": request_id} if request_id else None,
        )
