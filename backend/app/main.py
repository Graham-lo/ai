from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_accounts import router as accounts_router
from app.api.routes_attribution import router as attribution_router
from app.api.routes_deepseek import router as deepseek_router
from app.api.routes_exports import router as exports_router
from app.api.routes_imports import router as imports_router
from app.api.routes_market import router as market_router
from app.api.routes_plugins import router as plugins_router
from app.api.routes_reports import router as reports_router
from app.api.routes_sync import router as sync_router
from app.core.logging import configure_logging
from app.scheduler.monthly import start_monthly_scheduler

configure_logging()

app = FastAPI(title="Trade Check Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plugins_router, prefix="/plugins", tags=["plugins"])
app.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
app.include_router(sync_router, prefix="/sync", tags=["sync"])
app.include_router(reports_router, prefix="/reports", tags=["reports"])
app.include_router(deepseek_router, prefix="/reports", tags=["reports"])
app.include_router(attribution_router, prefix="/reports", tags=["reports"])
app.include_router(exports_router, prefix="/exports", tags=["exports"])
app.include_router(imports_router, prefix="/imports", tags=["imports"])
app.include_router(market_router, prefix="/market", tags=["market"])


@app.on_event("startup")
async def _startup() -> None:
    start_monthly_scheduler()
