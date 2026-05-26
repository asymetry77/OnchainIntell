"""
api_server.py — FastAPI REST server for OnchainIntell Insider Wallet Tracker.

Endpoints for wallet discovery, watchlist management, snapshots,
token scanning, reports, and alerts.

Run:
    uvicorn api_server:app --reload --port 8000
"""

import json
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config.settings import REPORTS_DIR, SNAPSHOT_DIR, WATCHLIST_PATH
from core.arkham_client import ArkhamClient, ArkhamAPIError
from core.wallet_tracker import WalletTracker
from core.report_generator import ReportGenerator
from utils.helpers import format_usd, truncate_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_server")

app = FastAPI(
    title="OnchainIntell — Insider Wallet Tracker",
    description="Track insider wallets, altcoin flows, and generate reports",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class AddWalletRequest(BaseModel):
    address: str
    label: Optional[str] = ""

class ReportRequest(BaseModel):
    period: str = "daily"


# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(str(frontend_path / "index.html"))

@app.get("/api/health")
def health():
    return {
        "status": "online",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "version": "2.0.0",
    }


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    tracker = WalletTracker()
    report_gen = ReportGenerator()
    watchlist = tracker.get_watchlist()
    snapshots = report_gen.list_snapshots()
    reports = report_gen.list_reports()

    try:
        alerts = tracker.get_alerts()
    except Exception:
        alerts = []

    return {
        "wallets_tracked": len(watchlist),
        "snapshots_taken": len(snapshots),
        "reports_generated": len(reports),
        "alerts_24h": len(alerts),
        "last_discovery": _wl_meta("last_discovery"),
        "last_snapshot": _wl_meta("last_snapshot"),
        "recent_alerts": alerts[:5],
    }


# ── WATCHLIST ─────────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
def get_watchlist():
    tracker = WalletTracker()
    return {"success": True, "wallets": tracker.get_watchlist()}

@app.post("/api/watchlist")
def add_wallet(req: AddWalletRequest):
    tracker = WalletTracker()
    try:
        wallet = tracker.add_wallet(req.address, label=req.label or "")
        return {"success": True, "wallet": wallet}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.delete("/api/watchlist/{address}")
def remove_wallet(address: str):
    tracker = WalletTracker()
    removed = tracker.remove_wallet(address)
    if not removed:
        raise HTTPException(404, detail="Wallet not found")
    return {"success": True, "removed": address}


# ── DISCOVERY ─────────────────────────────────────────────────────────────────

@app.post("/api/discover")
def discover():
    tracker = WalletTracker()
    try:
        discovered = tracker.discover_wallets()
        return {"success": True, "discovered": len(discovered), "wallets": discovered}
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(500, detail=str(e))


# ── WALLET DETAIL ─────────────────────────────────────────────────────────────

@app.get("/api/wallet/{address}")
def wallet_detail(address: str):
    tracker = WalletTracker()
    detail = tracker.get_wallet_detail(address)
    if not detail:
        raise HTTPException(404, detail="Wallet not found in watchlist")
    return {"success": True, "wallet": detail}


# ── TOKEN SCANNER ─────────────────────────────────────────────────────────────

@app.get("/api/token/{slug}/holders")
def token_holders(slug: str):
    tracker = WalletTracker()
    try:
        result = tracker.scan_token(slug)
        return {"success": True, **result}
    except ArkhamAPIError as e:
        raise HTTPException(502, detail=str(e))

@app.get("/api/token/{slug}/flow")
def token_flow(slug: str, time_last: str = "24h"):
    client = ArkhamClient()
    try:
        flows = client.get_token_top_flow(slug, time_last=time_last)
        return {"success": True, "token": slug, "flows": flows}
    except ArkhamAPIError as e:
        raise HTTPException(502, detail=str(e))

@app.get("/api/tokens/trending")
def trending_tokens():
    client = ArkhamClient()
    try:
        tokens = client.get_trending_tokens()
        return {"success": True, "tokens": tokens}
    except ArkhamAPIError as e:
        raise HTTPException(502, detail=str(e))

@app.get("/api/token/search")
def search_token(q: str = Query(..., description="Token name or symbol")):
    client = ArkhamClient()
    try:
        results = client.search_token(q)
        return {"success": True, "results": results}
    except ArkhamAPIError as e:
        raise HTTPException(502, detail=str(e))


# ── SNAPSHOTS ─────────────────────────────────────────────────────────────────

@app.post("/api/snapshot")
def take_snapshot():
    tracker = WalletTracker()
    try:
        result = tracker.take_snapshot()
        return {"success": True, **result}
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(500, detail=str(e))

@app.get("/api/snapshots")
def list_snapshots():
    gen = ReportGenerator()
    return {"success": True, "snapshots": gen.list_snapshots()}


# ── REPORTS ───────────────────────────────────────────────────────────────────

@app.post("/api/report/generate")
def generate_report(req: ReportRequest):
    gen = ReportGenerator()
    try:
        report = gen.generate_report(req.period)
        if "error" in report:
            raise HTTPException(400, detail=report["error"])
        return {"success": True, "report": report}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(500, detail=str(e))

@app.get("/api/reports")
def list_reports():
    gen = ReportGenerator()
    return {"success": True, "reports": gen.list_reports()}

@app.get("/api/reports/{filename}")
def get_report(filename: str):
    gen = ReportGenerator()
    report = gen.load_report(filename)
    if not report:
        raise HTTPException(404, detail="Report not found")
    return {"success": True, "report": report}


# ── ALERTS ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def get_alerts(min_usd: float = 500000):
    tracker = WalletTracker()
    try:
        alerts = tracker.get_alerts(min_usd=min_usd)
        return {"success": True, "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(500, detail=str(e))


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _wl_meta(key: str):
    if WATCHLIST_PATH.exists():
        try:
            data = json.loads(WATCHLIST_PATH.read_text())
            return data.get(key)
        except (json.JSONDecodeError, OSError):
            pass
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
