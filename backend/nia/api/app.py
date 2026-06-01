from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nia.api.crawl import router as crawl_router
from nia.api.data import router as data_router
from nia.api.monitor import router as monitor_router
from nia.api.query import router as query_router
from nia.api.settings import router as settings_router

app = FastAPI(title="Nexus Intelligence Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl_router)
app.include_router(query_router)
app.include_router(data_router)
app.include_router(monitor_router)
app.include_router(settings_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
