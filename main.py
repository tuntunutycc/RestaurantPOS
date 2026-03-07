"""FastAPI application for the Restaurant POS system."""

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from database import engine
from models import Base
from routers import menu, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield
    # Optional: cleanup on shutdown (e.g. close pool)
    engine.dispose()


app = FastAPI(title="Restaurant POS API", lifespan=lifespan)
app.include_router(menu.router)
app.include_router(orders.router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"message": "POS Server is running"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Avoid 404 when browsers request favicon.ico."""
    return Response(status_code=204)


static_dir = Path(__file__).parent / "static"


@app.get("/waiter")
def waiter_page():
    """Serve the Waiter POS UI."""
    return FileResponse(static_dir / "waiter.html")


app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
