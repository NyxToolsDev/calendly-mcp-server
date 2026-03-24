"""Entry point for calendly-mcp server."""

import asyncio

from calendly_mcp.server import run_server


def main() -> None:
    """Synchronous entry point used by the ``calendly-mcp`` console script."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
