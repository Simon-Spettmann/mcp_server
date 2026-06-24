# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Nextcloud MCP Server - Main Entry Point

This is a standalone MCP server that exposes Nextcloud capabilities as tools.
It has NO LLM dependencies and can be used by any MCP client.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nc_py_api import AsyncNextcloudApp
from nc_py_api.ex_app import AppAPIAuthMiddleware, run_app, set_handlers

from ex_app.lib.mcp_server import create_mcp_server, http_mcp_app, stdio_mcp_app
from ex_app.lib.tool_loader import setup_mcp_server

# Create the MCP server
mcp = create_mcp_server()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up handlers for Nextcloud ex_app
    set_handlers(app, enabled_handler, trigger_handler=None)

    # Set up MCP server with tools
    await setup_mcp_server(mcp)

    async with http_mcp_app.lifespan(app):
        yield


APP = FastAPI(lifespan=lifespan)
APP.add_middleware(AppAPIAuthMiddleware)

# Mount the MCP server at /mcp
APP.mount("/mcp", http_mcp_app)

# For stdio transport (CLI clients), we can run the server directly
# This is handled by the __main__ block in mcp_server.py


async def enabled_handler(enabled: bool, nc: AsyncNextcloudApp) -> str:
    """Handle app enable/disable events."""
    if enabled:
        print("Nextcloud MCP Server enabled")
    else:
        print("Nextcloud MCP Server disabled")
    return ""


async def trigger_handler(providerId: str):
    """Handle trigger events (not used for MCP server)."""
    pass


if __name__ == "__main__":
    run_app("main:APP", log_level="info")
