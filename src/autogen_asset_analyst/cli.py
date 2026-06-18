"""CLI interface for AutoGen Asset Analyst - Investment Research Roundtable."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from autogen_asset_analyst import __version__
from autogen_asset_analyst.analyzer import run_roundtable
from autogen_asset_analyst.config import settings
from autogen_asset_analyst.visualization import AGENT_CONFIG, generate_html_report

app = typer.Typer(
    name="autogen-analyst",
    help="AutoGen Asset Analyst - Investment Research Roundtable",
    add_completion=False,
)

console = Console()


@app.command()
def roundtable(
    asset_lens_path: Optional[str] = typer.Option(
        None, "--asset-lens-path", "-p", help="Path to the asset-lens project directory"
    ),
    max_rounds: Optional[int] = typer.Option(
        None, "--max-rounds", "-r", help="Maximum number of discussion rounds"
    ),
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Analysis date (YYYYMMDD), e.g. 20260613"
    ),
) -> None:
    """Run the Investment Research Roundtable discussion."""
    lens_path = asset_lens_path or settings.ASSET_LENS_PATH
    rounds = max_rounds or settings.ROUNDTABLE_MAX_ROUNDS

    # Validate path
    if not Path(lens_path).exists():
        console.print(f"[red]Error: asset-lens path not found: {lens_path}[/red]")
        console.print("[dim]Tip: Set ASSET_LENS_PATH in .env or use --asset-lens-path option[/dim]")
        raise typer.Exit(code=1)

    date_label = f", Date: [bold]{date}[/bold]" if date else ""
    console.print(Panel(
        f"Asset-Lens: [bold]{lens_path}[/bold]\n"
        f"Max Rounds: [bold]{rounds}[/bold]{date_label}",
        title="Investment Research Roundtable",
    ))

    # Show agent lineup
    console.print("\n[bold]Roundtable Participants:[/bold]")
    for agent_key, config in AGENT_CONFIG.items():
        console.print(f"  {config['avatar']} {config['name']}")

    with console.status("[bold green]Running roundtable discussion..."):
        result = run_roundtable(lens_path, rounds, date=date)

    errors = result.errors
    if errors:
        console.print("[bold red]Errors encountered:[/bold red]")
        for error in errors:
            console.print(f"  [red]- {error}[/red]")
        raise typer.Exit(code=1)

    # Display discussion summary
    messages = result.messages
    if messages:
        console.print(f"\n[bold]Roundtable completed ({len(messages)} messages)[/bold]")

        # Show each agent's contribution count
        agent_counts: dict[str, int] = {}
        for msg in messages:
            source = msg.get("source", "Unknown")
            agent_counts[source] = agent_counts.get(source, 0) + 1

        console.print("\n[bold]Agent Contributions:[/bold]")
        for source, count in agent_counts.items():
            config = AGENT_CONFIG.get(source, {"avatar": "💬", "name": source})
            console.print(f"  {config['avatar']} {config['name']}: {count} messages")

        # Show veto count
        if result.vetoes:
            console.print(f"\n[bold red]Vetoes: {len(result.vetoes)}[/bold red]")

        # Display discussion preview
        console.print("\n[bold]Discussion Preview:[/bold]")
        for msg in messages:
            source = msg.get("source", "Unknown")
            content = msg.get("content", "")
            config = AGENT_CONFIG.get(source, {"avatar": "💬", "name": source, "color": "#64748b"})
            preview = content[:150] + "..." if len(content) > 150 else content
            console.print(f"\n  {config['avatar']} [{config['color']}]{config['name']}[/{config['color']}]")
            console.print(f"  {preview}")

    # Display consensus
    if result.consensus:
        console.print("\n[bold magenta]Consensus Decision:[/bold magenta]")
        preview = result.consensus[:500] + ("..." if len(result.consensus) > 500 else "")
        console.print(preview)


@app.command()
def report(
    asset_lens_path: Optional[str] = typer.Option(
        None, "--asset-lens-path", "-p", help="Path to the asset-lens project directory"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output directory for the HTML report (default: ./output)"
    ),
    max_rounds: Optional[int] = typer.Option(
        None, "--max-rounds", "-r", help="Maximum number of discussion rounds"
    ),
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Analysis date (YYYYMMDD), e.g. 20260613"
    ),
) -> None:
    """Generate an HTML report from the roundtable discussion."""
    lens_path = asset_lens_path or settings.ASSET_LENS_PATH
    rounds = max_rounds or settings.ROUNDTABLE_MAX_ROUNDS

    # Validate path
    if not Path(lens_path).exists():
        console.print(f"[red]Error: asset-lens path not found: {lens_path}[/red]")
        raise typer.Exit(code=1)

    date_label = f", Date: [bold]{date}[/bold]" if date else ""
    console.print(Panel(
        f"Generating report from: [bold]{lens_path}[/bold]{date_label}",
        title="AutoGen Asset Analyst - Report",
    ))

    with console.status("[bold green]Running roundtable and generating report..."):
        result = run_roundtable(lens_path, rounds, date=date)

    errors = result.errors
    if errors:
        console.print("[bold red]Errors encountered:[/bold red]")
        for error in errors:
            console.print(f"  [red]- {error}[/red]")
        raise typer.Exit(code=1)

    if not result.messages and not result.consensus:
        console.print("[bold red]No discussion data was generated.[/bold red]")
        raise typer.Exit(code=1)

    # Generate HTML report
    html = generate_html_report(result, lens_path)

    # Determine output path
    output_dir = Path(output) if output else Path("./output")
    output_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"roundtable_report_{timestamp}.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    console.print(f"\n[bold green]Report saved to: {output_path}[/bold green]")
    console.print(f"[dim]Messages: {len(result.messages)} | Vetoes: {len(result.vetoes)}[/dim]")
    if result.token_usage:
        t = result.token_usage
        console.print(
            f"[dim]Tokens: {t.get('total_tokens', 0)} "
            f"(prompt: {t.get('prompt_tokens', 0)}, completion: {t.get('completion_tokens', 0)})[/dim]"
        )


@app.command()
def version() -> None:
    """Show the version."""
    console.print(f"AutoGen Asset Analyst v{__version__} (Investment Research Roundtable)")


if __name__ == "__main__":
    app()
