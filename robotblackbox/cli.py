"""Command-line interface for RobotBlackBox"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from robotblackbox import __version__
from robotblackbox.config import Config
from robotblackbox.agent import BlackBoxAgent

app = typer.Typer(
    name="robotblackbox",
    help="RobotBlackBox - Real-time observability for robot fleets",
    add_completion=False,
)
console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


@app.command()
def start(
    robot_id: str = typer.Option("robot_001", "--robot-id", "-r", help="Unique robot identifier"),
    server: str = typer.Option("ws://localhost:8000", "--server", "-s", help="Server WebSocket URL"),
    mock: bool = typer.Option(False, "--mock", "-m", help="Use mock data (no ROS2 required)"),
    hz: float = typer.Option(10.0, "--hz", help="Collection frequency in Hz"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """
    Start the RobotBlackBox agent.
    
    Examples:
        rbb start --robot-id my_robot --server wss://blackbox.example.com
        rbb start --mock  # Test without ROS2
    """
    setup_logging(verbose)
    
    # Load config
    if config_file and config_file.exists():
        config = Config.from_file(config_file)
    else:
        config = Config(
            robot_id=robot_id,
            server_url=server,
            use_mock=mock,
            collection_hz=hz,
        )
    
    console.print(f"[bold green]⬛ RobotBlackBox v{__version__}[/]")
    console.print(f"   Robot: [cyan]{config.robot_id}[/]")
    console.print(f"   Server: [cyan]{config.server_url}[/]")
    console.print(f"   Mode: [cyan]{'mock' if config.use_mock else 'ROS2'}[/]")
    console.print()
    
    agent = BlackBoxAgent(config)
    
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/]")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    init: bool = typer.Option(False, "--init", help="Create default config file"),
    path: Path = typer.Option(Path.home() / ".robotblackbox" / "config.json", "--path", "-p"),
):
    """
    Manage configuration.
    
    Examples:
        rbb config --init           # Create default config
        rbb config --show           # Show current config
    """
    if init:
        cfg = Config()
        cfg.save(path)
        console.print(f"[green]Config saved to {path}[/]")
    
    if show:
        if path.exists():
            cfg = Config.from_file(path)
        else:
            cfg = Config()
        console.print(cfg.model_dump_json(indent=2))


@app.command()
def version():
    """Show version."""
    console.print(f"RobotBlackBox v{__version__}")


@app.command()
def test_connection(
    server: str = typer.Option("ws://localhost:8000", "--server", "-s"),
):
    """
    Test connection to server.
    """
    import websockets
    
    async def _test():
        try:
            url = f"{server}/api/health"
            # Quick HTTP check first
            import urllib.request
            http_url = url.replace("ws://", "http://").replace("wss://", "https://")
            with urllib.request.urlopen(http_url, timeout=5) as resp:
                if resp.status == 200:
                    console.print(f"[green]✓ Server reachable at {server}[/]")
                    return
        except Exception as e:
            console.print(f"[red]✗ Cannot reach server: {e}[/]")
    
    asyncio.run(_test())


if __name__ == "__main__":
    app()
