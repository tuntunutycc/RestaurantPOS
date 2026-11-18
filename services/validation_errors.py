"""422 responses that survive a NaN / Infinity in the rejected input.

FastAPI copies the rejected value into the error body. For `NaN` that makes the
body impossible to encode as JSON, so a client that sent one got a 500 instead
of a 422. Same shape as FastAPI's own response; only non-finite numbers are
written as text.
"""

from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(item) for item in value]
    return value


async def _validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(_finite(exc.errors()))})


def install(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
