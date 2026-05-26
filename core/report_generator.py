"""
report_generator.py — Generate reports by comparing wallet snapshots.

Supports daily, weekly, and monthly periods.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config.settings import SNAPSHOT_DIR, REPORTS_DIR
from utils.helpers import format_usd, format_pct

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self):
        self.snapshot_dir = SNAPSHOT_DIR
        self.reports_dir = REPORTS_DIR

    # ── SNAPSHOT LOADING ──────────────────────────────────────────────────

    def _load_snapshot(self, date_str: str) -> dict | None:
        path = self.snapshot_dir / f"{date_str}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _find_closest_snapshot(self, target_date: datetime) -> dict | None:
        for delta in range(0, 8):
            for direction in [0, -1, 1]:
                d = target_date + timedelta(days=delta * direction)
                snap = self._load_snapshot(d.strftime("%Y-%m-%d"))
                if snap:
                    return snap
        return None

    def list_snapshots(self) -> list[str]:
        files = sorted(self.snapshot_dir.glob("*.json"))
        return [f.stem for f in files]

    # ── COMPARISON ────────────────────────────────────────────────────────

    def _compare_snapshots(self, current: dict, previous: dict) -> list[dict]:
        prev_map = {w["address"]: w for w in previous.get("wallets", [])}
        results = []

        for wallet in current.get("wallets", []):
            addr = wallet["address"]
            curr_usd = self._parse_usd(wallet.get("total_usd", 0))
            prev_usd = self._parse_usd(prev_map.get(addr, {}).get("total_usd", 0))
            delta = curr_usd - prev_usd
            pct = (delta / prev_usd * 100) if prev_usd else 0

            results.append({
                "address": addr,
                "label": wallet.get("label", ""),
                "current_usd": curr_usd,
                "previous_usd": prev_usd,
                "delta_usd": delta,
                "delta_pct": round(pct, 2),
            })

        results.sort(key=lambda r: abs(r["delta_usd"]), reverse=True)
        return results

    @staticmethod
    def _parse_usd(val) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val.replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    # ── REPORT GENERATION ─────────────────────────────────────────────────

    def generate_report(self, period: str = "daily") -> dict:
        now = datetime.now(timezone.utc)
        if period == "daily":
            delta_days = 1
        elif period == "weekly":
            delta_days = 7
        elif period == "monthly":
            delta_days = 30
        else:
            return {"error": f"Unknown period: {period}. Use daily/weekly/monthly."}

        current = self._find_closest_snapshot(now)
        if not current:
            return {"error": "No current snapshot found. Run snapshot first."}

        previous = self._find_closest_snapshot(now - timedelta(days=delta_days))
        if not previous:
            return {"error": f"No previous snapshot found for {period} comparison."}

        comparisons = self._compare_snapshots(current, previous)
        total_current = sum(r["current_usd"] for r in comparisons)
        total_previous = sum(r["previous_usd"] for r in comparisons)
        total_delta = total_current - total_previous

        report = {
            "period": period,
            "generated_at": now.isoformat(),
            "current_snapshot": current.get("timestamp", ""),
            "previous_snapshot": previous.get("timestamp", ""),
            "summary": {
                "total_wallets": len(comparisons),
                "total_current_usd": total_current,
                "total_previous_usd": total_previous,
                "total_delta_usd": total_delta,
                "total_delta_pct": round((total_delta / total_previous * 100) if total_previous else 0, 2),
                "gainers": len([r for r in comparisons if r["delta_usd"] > 0]),
                "losers": len([r for r in comparisons if r["delta_usd"] < 0]),
            },
            "wallets": comparisons,
        }

        # Save report
        ts = now.strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"{ts}_{period}_report.json"
        path.write_text(json.dumps(report, indent=2, default=str))
        report["saved"] = str(path)

        logger.info(f"{period.capitalize()} report generated: {len(comparisons)} wallets")
        return report

    def list_reports(self) -> list[dict]:
        reports = []
        for f in sorted(self.reports_dir.glob("*_report.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                reports.append({
                    "filename": f.name,
                    "period": data.get("period", ""),
                    "generated_at": data.get("generated_at", ""),
                    "total_wallets": data.get("summary", {}).get("total_wallets", 0),
                    "total_delta_usd": data.get("summary", {}).get("total_delta_usd", 0),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return reports

    def load_report(self, filename: str) -> dict | None:
        path = self.reports_dir / filename
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
