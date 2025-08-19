"""Command-line interface for NVIDIA Orchestrator."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

import uvicorn

from nvidia_orchestrator import __version__
from nvidia_orchestrator.api.app import app
from nvidia_orchestrator.main import run
from nvidia_orchestrator.monitoring.health_monitor import run_forever


def main(argv: Optional[List[str]] = None) -> int:
    """
    Run the NVIDIA Orchestrator CLI.
    
    Args:
        argv: Command-line arguments. If None, uses sys.argv.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        prog="nvidia-orchestrator",
        description="NVIDIA Orchestrator - Container orchestration system"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands"
    )

    # Server command (runs both API and monitor)
    server_parser = subparsers.add_parser(
        "server",
        help="Run the full server (API + monitor)"
    )
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    # API server command (API only)
    api_parser = subparsers.add_parser(
        "api",
        help="Run only the API server"
    )
    api_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    api_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    # Monitor command (monitor only)
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Run only the health monitor"
    )
    monitor_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Monitoring interval in seconds (default: 60)"
    )

    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information"
    )

    args = parser.parse_args(argv)

    if args.command == "server":
        # Run full server (API + monitor)
        run()
        return 0

    elif args.command == "api":
        # Run API only
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    elif args.command == "monitor":
        # Run monitor only
        os.environ["HEALTH_INTERVAL_SECONDS"] = str(args.interval)
        run_forever()
        return 0

    elif args.command == "version":
        print(f"NVIDIA Orchestrator version {__version__}")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
