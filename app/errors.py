from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.keitaro import KeitaroError
from app.services import ServiceError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(_: Request, error: ServiceError):
        return JSONResponse(status_code=error.status, content={"detail": error.detail})

    @app.exception_handler(KeitaroError)
    async def keitaro_error(_: Request, error: KeitaroError):
        status = 404 if error.status == 404 else 502
        return JSONResponse(status_code=status, content={"detail": f"Keitaro: {error.detail}"})
