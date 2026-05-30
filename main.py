"""
main.py — OnchainIntell Insider Wallet Tracker: CLI Entry Point

Commands:
  discover        Auto-discover insider wallets from trending tokens
  watchlist       List all tracked wallets
  add-wallet      Add a wallet address to the watchlist
  remove-wallet   Remove a wallet from the watchlist
  wallet          Show full detail for a tracked wallet
  snapshot        Take daily balance snapshot of all watched wallets
  report          Generate daily/weekly/monthly report
  scan-token      Scan a specific token for holders and flow
  alerts          Show recent large transactions from watched wallets
  trending        Show trending tokens on Arkham

Usage:
  python main.py discover
  python main.py watchlist
  python main.py add-wallet 0x1234...
  python main.py snapshot
  python main.py report --period daily
  python main.py scan-token --slug pepe
  python main.py alerts
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config.settings import REPORTS_DIR, LOGS_DIR
from core.arkham_client import ArkhamClient, ArkhamAPIError
from core.wallet_tracker import WalletTracker
from core.report_generator import ReportGenerator
from utils.helpers import format_usd, truncate_address, human_time_ago

# ── Logging setup ─────────────────────────────────────────────────────────────
log_file = LOGS_DIR / f"onchain_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ],
)
logger = logging.getLogger("main")
console = Console()


# ── CLI ROOT ──────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="2.0.0", prog_name="onchainintell")
def cli():
    """OnchainIntell — Insider Wallet Tracker"""
    pass


# ── COMMAND: discover ─────────────────────────────────────────────────────────

@cli.command()
def discover():
    """Auto-discover insider wallets from trending token flows."""
    console.rule("[bold cyan]DISCOVERING WALLETS")
    tracker = WalletTracker()
    discovered = tracker.discover_wallets()

    if not discovered:
        console.print("[yellow]No new wallets discovered.[/yellow]")
        return

    table = Table(title=f"Discovered {len(discovered)} Wallets")
    table.add_column("Address", style="cyan")
    table.add_column("Label")
    table.add_column("Token", style="yellow")
    table.add_column("Inflow", style="green")
    table.add_column("Outflow", style="red")

    for w in discovered:
        table.add_row(
            truncate_address(w.get("address", "")),
            w.get("label", "—"),
            w.get("token", "—"),
            format_usd(w.get("in_usd", 0)),
            format_usd(w.get("out_usd", 0)),
        )
    console.print(table)


# ── COMMAND: watchlist ────────────────────────────────────────────────────────

@cli.command()
def watchlist():
    """List all tracked wallets."""
    tracker = WalletTracker()
    wallets = tracker.get_watchlist()

    if not wallets:
        console.print("[dim]No wallets in watchlist. Run 'discover' first.[/dim]")
        return

    table = Table(title=f"Watchlist — {len(wallets)} Wallets")
    table.add_column("#", style="dim")
    table.add_column("Address", style="cyan")
    table.add_column("Label")
    table.add_column("Token Source", style="yellow")
    table.add_column("Added", style="dim")

    for i, w in enumerate(wallets, 1):
        table.add_row(
            str(i),
            truncate_address(w.get("address", "")),
            w.get("label", "—"),
            w.get("token_source", "—"),
            w.get("added_at", "—")[:10],
        )
    console.print(table)


# ── COMMAND: add-wallet ───────────────────────────────────────────────────────

@cli.command("add-wallet")
@click.argument("address")
@click.option("--label", default="", help="Optional label for the wallet")
def add_wallet(address: str, label: str):
    """Add a wallet address to the watchlist."""
    tracker = WalletTracker()
    wallet = tracker.add_wallet(address, label=label)
    console.print(f"[green]Added:[/green] {truncate_address(address)} — {label or 'no label'}")


# ── COMMAND: remove-wallet ────────────────────────────────────────────────────

@cli.command("remove-wallet")
@click.argument("address")
def remove_wallet(address: str):
    """Remove a wallet from the watchlist."""
    tracker = WalletTracker()
    if tracker.remove_wallet(address):
        console.print(f"[green]Removed:[/green] {address}")
    else:
        console.print(f"[red]Not found:[/red] {address}")


# ── COMMAND: wallet ───────────────────────────────────────────────────────────

@cli.command()
@click.argument("address")
def wallet(address: str):
    """Show full detail for a tracked wallet."""
    tracker = WalletTracker()
    detail = tracker.get_wallet_detail(address)

    if not detail:
        console.print(f"[red]Wallet not found in watchlist:[/red] {address}")
        return

    balance = detail.get("balance", {})
    console.print(Panel(
        f"Address:  [cyan]{detail['address']}[/cyan]\n"
        f"Label:    {detail.get('label', '—')}\n"
        f"Balance:  [green]{format_usd(balance.get('total_usd', 0))}[/green]",
        title="Wallet Detail",
    ))

    transfers = detail.get("transfers", [])
    if transfers:
        table = Table(title=f"Recent Transfers ({len(transfers)})")
        table.add_column("Time", style="dim")
        table.add_column("Amount", style="green")
        table.add_column("Token", style="cyan")
        table.add_column("From")
        table.add_column("To")
        table.add_column("TX Hash", style="dim")

        for t in transfers[:15]:
            table.add_row(
                human_time_ago(t.get("blockTimestamp", 0)),
                format_usd(t.get("historicalUSD", 0)),
                t.get("tokenSymbol", "?"),
                truncate_address(t.get("fromAddress", "")),
                truncate_address(t.get("toAddress", "")),
                truncate_address(t.get("transactionHash", "")),
            )
        console.print(table)

    swaps = detail.get("swaps", [])
    if swaps:
        table = Table(title=f"DEX Swaps ({len(swaps)})")
        table.add_column("Time", style="dim")
        table.add_column("Token", style="cyan")
        table.add_column("Amount", style="green")
        table.add_column("Chain")

        for s in swaps[:10]:
            table.add_row(
                human_time_ago(s.get("timestamp", 0)),
                s.get("tokenSymbol", "?"),
                format_usd(s.get("historicalUSD", 0)),
                s.get("chain", "?"),
            )
        console.print(table)


# ── COMMAND: snapshot ─────────────────────────────────────────────────────────

@cli.command()
def snapshot():
    """Take daily balance snapshot of all watched wallets."""
    console.rule("[bold cyan]TAKING SNAPSHOT")
    tracker = WalletTracker()
    result = tracker.take_snapshot()

    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        return

    console.print(f"[green]Snapshot saved:[/green] {result['saved']}")
    console.print(f"Wallets captured: {result['wallets']}")


# ── COMMAND: report ───────────────────────────────────────────────────────────

@cli.command()
@click.option("--period", type=click.Choice(["daily", "weekly", "monthly"]),
              default="daily", help="Report period")
def report(period: str):
    """Generate daily/weekly/monthly report comparing snapshots."""
    console.rule(f"[bold cyan]{period.upper()} REPORT")
    gen = ReportGenerator()
    result = gen.generate_report(period)

    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        return

    summary = result.get("summary", {})
    console.print(Panel(
        f"Period:         {result['period']}\n"
        f"Wallets:        {summary.get('total_wallets', 0)}\n"
        f"Current Total:  {format_usd(summary.get('total_current_usd', 0))}\n"
        f"Previous Total: {format_usd(summary.get('total_previous_usd', 0))}\n"
        f"Delta:          {format_usd(summary.get('total_delta_usd', 0))} "
        f"({summary.get('total_delta_pct', 0):+.1f}%)\n"
        f"Gainers:        {summary.get('gainers', 0)}\n"
        f"Losers:         {summary.get('losers', 0)}\n"
        f"Saved:          {result.get('saved', '—')}",
        title=f"{period.capitalize()} Report",
    ))

    wallets = result.get("wallets", [])
    if wallets:
        table = Table(title="Top Movers")
        table.add_column("Address", style="cyan")
        table.add_column("Label")
        table.add_column("Current", style="green")
        table.add_column("Delta", style="bold")
        table.add_column("Delta %")

        for w in wallets[:10]:
            delta = w.get("delta_usd", 0)
            color = "green" if delta >= 0 else "red"
            table.add_row(
                truncate_address(w.get("address", "")),
                w.get("label", "—"),
                format_usd(w.get("current_usd", 0)),
                f"[{color}]{format_usd(delta)}[/{color}]",
                f"[{color}]{w.get('delta_pct', 0):+.1f}%[/{color}]",
            )
        console.print(table)


# ── COMMAND: scan-token ───────────────────────────────────────────────────────

@cli.command("scan-token")
@click.option("--slug", required=True, help="Token slug (e.g. pepe, bitcoin)")
def scan_token(slug: str):
    """Scan a token for holders, flow, and watchlist overlap."""
    console.rule(f"[bold cyan]TOKEN SCAN: {slug.upper()}")
    tracker = WalletTracker()
    result = tracker.scan_token(slug)

    holders = result.get("holders", [])
    if holders:
        table = Table(title="Top Holders")
        table.add_column("Address", style="cyan")
        table.add_column("Label")
        table.add_column("Balance", style="green")
        table.add_column("In Watchlist", style="yellow")

        watchlist_addrs = {w["address"] for w in tracker.get_watchlist()}
        for h in holders[:10]:
            addr = h.get("address", "")
            table.add_row(
                truncate_address(addr),
                h.get("arkhamLabel", "—"),
                format_usd(h.get("balanceUSD", 0)),
                "YES" if addr in watchlist_addrs else "",
            )
        console.print(table)

    flows = result.get("top_flow", [])
    if flows:
        table = Table(title="Top Flow (24h)")
        table.add_column("Address", style="cyan")
        table.add_column("Inflow", style="green")
        table.add_column("Outflow", style="red")

        for f in flows[:10]:
            table.add_row(
                truncate_address(f.get("address", "")),
                format_usd(f.get("inUSD", 0)),
                format_usd(f.get("outUSD", 0)),
            )
        console.print(table)


# ── COMMAND: alerts ───────────────────────────────────────────────────────────

@cli.command()
@click.option("--min-usd", default=500000, type=float, help="Min USD threshold")
def alerts(min_usd: float):
    """Show recent large transactions from watched wallets."""
    console.rule("[bold red]ALERTS")
    tracker = WalletTracker()
    result = tracker.get_alerts(min_usd=min_usd)

    if not result:
        console.print("[green]No alerts in the last 24h.[/green]")
        return

    table = Table(title=f"Alerts — {len(result)} Transactions")
    table.add_column("Address", style="cyan")
    table.add_column("Label")
    table.add_column("Token", style="yellow")
    table.add_column("Amount", style="green")
    table.add_column("From")
    table.add_column("To")
    table.add_column("TX Hash", style="dim")

    for a in result[:20]:
        table.add_row(
            truncate_address(a.get("address", "")),
            a.get("label", "—"),
            a.get("token", "—"),
            format_usd(a.get("amount_usd", 0)),
            truncate_address(a.get("from", "")),
            truncate_address(a.get("to", "")),
            truncate_address(a.get("tx_hash", "")),
        )
    console.print(table)


# ── COMMAND: trending ─────────────────────────────────────────────────────────

@cli.command()
def trending():
    """Show trending tokens on Arkham."""
    console.rule("[bold cyan]TRENDING TOKENS")
    client = ArkhamClient()
    try:
        tokens = client.get_trending_tokens()
        for i, t in enumerate(tokens[:10], 1):
            sym = t.get("symbol", "?")
            name = t.get("name", "?")
            console.print(f"  {i}. [cyan]{sym}[/cyan] — {name}")
    except ArkhamAPIError as e:
        console.print(f"[red]Error: {e}[/red]")


# ── COMMAND: reports (list) ───────────────────────────────────────────────────

@cli.command("reports")
def list_reports():
    """List all generated reports."""
    gen = ReportGenerator()
    reports = gen.list_reports()

    if not reports:
        console.print("[dim]No reports generated yet.[/dim]")
        return

    table = Table(title="Reports")
    table.add_column("Filename", style="dim")
    table.add_column("Period", style="cyan")
    table.add_column("Generated", style="dim")
    table.add_column("Wallets")
    table.add_column("Delta", style="bold")

    for r in reports[:20]:
        delta = r.get("total_delta_usd", 0)
        color = "green" if delta >= 0 else "red"
        table.add_row(
            r.get("filename", ""),
            r.get("period", ""),
            r.get("generated_at", "")[:16],
            str(r.get("total_wallets", 0)),
            f"[{color}]{format_usd(delta)}[/{color}]",
        )
    console.print(table)


# ── SIGNALS ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--hours", default=24, help="Lookback window in hours")
@click.option("--min-usd", default=100000, help="Minimum USD threshold")
def signals(hours, min_usd):
    """Detect onchain signals: whale buys, VC movements, accumulation."""
    from core.signal_detector import SignalDetector

    console.print(f"[bold]Scanning for signals ({hours}h, min ${min_usd:,.0f})...[/bold]")
    detector = SignalDetector()
    results = detector.detect_all(hours=hours, min_usd=min_usd)

    if not results:
        console.print("[dim]No signals detected.[/dim]")
        return

    table = Table(title=f"Signals ({len(results)})")
    table.add_column("Score", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Entity/Token")
    table.add_column("Action")
    table.add_column("Amount", style="bold")
    table.add_column("TX Hash", style="dim")

    for s in results[:20]:
        score = s.get("score", 0)
        color = "green" if score >= 70 else "yellow" if score >= 50 else "dim"
        table.add_row(
            f"[{color}]{score}[/{color}]",
            s.get("signal_type", ""),
            s.get("entity") or s.get("token", ""),
            s.get("action", ""),
            format_usd(s.get("amount_usd", 0)),
            (s.get("tx_hash", "") or "")[:16],
        )
    console.print(table)


# ── CAPTION ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--type", "signal_type", default="whale_buy",
              type=click.Choice(["whale_buy", "vc_movement", "accumulation", "anomaly"]))
@click.option("--entity", default="", help="Entity name")
@click.option("--token", default="", help="Token symbol")
@click.option("--amount", default=0.0, help="Amount in USD")
@click.option("--tx-hash", default="", help="Transaction hash")
@click.option("--description", default="", help="Signal description")
def caption(signal_type, entity, token, amount, tx_hash, description):
    """Generate AI caption for a signal."""
    from core.caption_generator import CaptionGenerator

    gen = CaptionGenerator()
    signal = {
        "signal_type": signal_type,
        "entity": entity,
        "label": entity,
        "action": "bought",
        "amount_usd": amount,
        "token": token,
        "tx_hash": tx_hash,
        "description": description,
    }

    console.print("[bold]Generating caption...[/bold]")
    try:
        result = gen.generate_from_signal(signal)
        console.print()
        console.print(Panel(
            result.get("caption", "No caption generated"),
            title="Generated Caption",
            border_style="green",
        ))
        if result.get("hashtags"):
            console.print(f"[dim]Hashtags: {' '.join(result['hashtags'])}[/dim]")
        if result.get("thread"):
            console.print("[dim]Thread:[/dim]")
            for t in result["thread"]:
                console.print(f"  [dim]{t}[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
