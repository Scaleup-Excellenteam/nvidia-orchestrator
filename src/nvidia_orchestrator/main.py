"""
Main entry point for NVIDIA Orchestrator server.

This module starts both the API server and health monitor.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import signal
import sys


def run_api_server() -> None:
    """Run the API server in a separate process."""
    import uvicorn

    from nvidia_orchestrator.api.app import app
    from nvidia_orchestrator.utils.logger import logger

    logger.info("Starting API server on port 8000...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )


def run_health_monitor() -> None:
    """Run the health monitor in a separate process."""
    from nvidia_orchestrator.monitoring.health_monitor import run_forever
    from nvidia_orchestrator.utils.logger import logger

    logger.info("Starting health monitor...")
    run_forever()


def run() -> None:
    """
    Main entry point that runs both API server and health monitor.
    
    This function starts both components in separate processes and handles
    graceful shutdown on SIGINT/SIGTERM.
    """
    from nvidia_orchestrator.utils.logger import logger

    logger.info("Starting NVIDIA Orchestrator...")

    # Create processes for API and monitor
    api_process = multiprocessing.Process(target=run_api_server, name="api-server")
    monitor_process = multiprocessing.Process(target=run_health_monitor, name="health-monitor")

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")

        # Terminate processes
        if api_process.is_alive():
            logger.info("Stopping API server...")
            api_process.terminate()
            api_process.join(timeout=5)

        if monitor_process.is_alive():
            logger.info("Stopping health monitor...")
            monitor_process.terminate()
            monitor_process.join(timeout=5)

        logger.info("Shutdown complete")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start processes
        logger.info("Starting API server process...")
        api_process.start()

        logger.info("Starting health monitor process...")
        monitor_process.start()

        logger.info("NVIDIA Orchestrator is running. Press Ctrl+C to stop.")

        # Wait for processes
        api_process.join()
        monitor_process.join()

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        signal_handler(signal.SIGTERM, None)


async def run_async() -> None:
    """
    Async version of the main entry point using asyncio.
    
    This is an alternative implementation using asyncio for environments
    that prefer async/await patterns.
    """
    import uvicorn

    from nvidia_orchestrator.api.app import app
    from nvidia_orchestrator.utils.logger import logger

    logger.info("Starting NVIDIA Orchestrator (async mode)...")

    # Create tasks for both components
    async def run_api():
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def run_monitor():
        from nvidia_orchestrator.monitoring.health_monitor import sample_once
        while True:
            try:
                sample_once()
                await asyncio.sleep(60)  # Default interval
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(60)

    # Run both tasks concurrently
    try:
        await asyncio.gather(
            run_api(),
            run_monitor()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    # Use multiprocessing for better isolation
    multiprocessing.set_start_method('spawn', force=True)
    run()
