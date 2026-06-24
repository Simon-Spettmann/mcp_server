# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Logger module for Nextcloud MCP Server."""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("nextcloud_mcp_server")
logger.setLevel(logging.INFO)


async def log(nc, level, content):
    """Log a message to both console and Nextcloud."""
    logger.log((level + 1) * 10, content)
    try:
        await nc.log(level, content)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.debug(f"Failed to log to Nextcloud: {e}")
