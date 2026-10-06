import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.core.cloudflare import CloudflareClient
from app.core.database import SessionLocal, utcnow
from app.features.audits.models import Audit, StageRun
from app.features.audits.routes import router as audit_router
from app.features.documents.routes import router as document_router
from app.features.usage.models import ApiCall

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ai_client = CloudflareClient()
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        for audit in db.scalars(select(Audit).where(Audit.status.in_(["processing", "queued"]))):
            audit.status, audit.assessment, audit.error = (
                "interrupted",
                "incomplete_analysis",
                "Xử lý bị gián đoạn; có thể thử lại",
            )
            audit.updated_at = utcnow()
        for run in db.scalars(select(StageRun).where(StageRun.status == "processing")):
            run.status, run.finished_at = "interrupted", utcnow()
        for call in db.scalars(select(ApiCall).where(ApiCall.status == "reserved")):
            call.status, call.error_code = "interrupted", "process_restart"
            # Keep the reservation: a request may have reached Cloudflare before interruption.
        db.commit()
    yield


app = FastAPI(title="AI Expense Audit", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(audit_router)
app.include_router(document_router)


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "postgresql"}
