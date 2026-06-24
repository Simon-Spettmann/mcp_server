# Nextcloud MCP Server

[![REUSE status](https://api.reuse.software/badge/github.com/nextcloud/context_agent)](https://api.reuse.software/info/github.com/nextcloud/context_agent)

A **minimal, standalone MCP (Model Context Protocol) server** that exposes **Nextcloud's native capabilities** as tools. This is a **pure tool gateway** with **no LLM dependencies** and **no external service integrations** - it only exposes what Nextcloud itself provides.

## What is MCP?

The [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/specification) is a standard protocol for exposing tools and resources to AI models and other clients. It allows any MCP-compatible client to access Nextcloud's capabilities.

## Features

- ✅ **Pure Nextcloud** - Only exposes Nextcloud's native APIs
- ✅ **No LLM required** - Standalone tool gateway
- ✅ **No external services** - No YouTube, DuckDuckGo, weather APIs, etc.
- ✅ **Minimal dependencies** - Only what's needed for Nextcloud integration
- ✅ **MCP-compliant** - Follows the MCP specification
- ✅ **Authenticated** - Uses Nextcloud's authentication system

## Available Tools

This server exposes the following **Nextcloud-native** capabilities as MCP tools:

### Core Nextcloud Tools
- **Mail**: Send emails, list accounts, list folders, list mails
- **Talk**: List conversations, send messages, list messages, create conversations
- **Calendar**: Create/delete events, list calendars, list events
- **Files**: Create/delete files, list files, read files, upload files
- **Contacts**: Find people in contacts, list all contacts

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   MCP Client     │     │  Nextcloud MCP   │
│  (Any language)  │◄───►│    Server        │
│                 │     │  (This app)      │
└─────────────────┘     └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Nextcloud     │
                    │   (Native APIs) │
                    └─────────────────┘
```

**No external APIs. No third-party services. Pure Nextcloud.**

## Usage

### For MCP Clients

Connect to the MCP server at `/mcp` endpoint. The server uses HTTP transport.

Example configuration for an MCP client:
```json
{
  "servers": {
    "nextcloud": {
      "url": "https://your-nextcloud.com/ocs/v2.php/apps/nextcloud_mcp_server/mcp",
      "transport": "http"
    }
  }
}
```

### For Nextcloud Administrators

1. Install the app from the Nextcloud App Store or via Docker
2. The MCP server will be available at `/mcp` endpoint
3. Any MCP-compatible client can now access Nextcloud tools

## Installation

### Via Nextcloud App Store (Coming Soon)
1. Go to Nextcloud Admin → Apps
2. Search for "Nextcloud MCP Server"
3. Install and enable

### Via Docker
```bash
# Using the official image
docker run -d \
  --name nextcloud_mcp_server \
  -e NEXTCLOUD_URL=https://your-nextcloud.com \
  -e NEXTCLOUD_USERNAME=admin \
  -e NEXTCLOUD_PASSWORD=yourpassword \
  ghcr.io/nextcloud/nextcloud_mcp_server:latest
```

### From Source
```bash
# Clone the repository
git clone https://github.com/nextcloud/context_agent.git
cd context_agent/mcp_server

# Install dependencies
pip install -r pyproject.toml

# Run
python -m ex_app.lib.main
```

## Development

### Adding New Tools

To add a new Nextcloud-native tool:

1. Create a new file in `ex_app/lib/tools/` (e.g., `new_tool.py`)
2. Implement the following functions:

```python
from nc_py_api import AsyncNextcloudApp

async def get_tools(nc: AsyncNextcloudApp):
    """Return a list of tool functions that use Nextcloud APIs."""
    async def my_tool(param1: str, param2: int) -> str:
        """Tool description."""
        # Use nc.* methods to interact with Nextcloud
        # Example: await nc.files.list("/")
        return result

    return [my_tool]

def get_category_name():
    """Return the category name for this tool module."""
    return "My Category"

async def is_available(nc: AsyncNextcloudApp):
    """Check if this tool module is available (e.g., required app is installed)."""
    try:
        # Check if the required Nextcloud app is available
        await nc.capabilities
        return "some_app" in await nc.capabilities
    except Exception:
        return False
```

3. The tool will be automatically loaded and registered with the MCP server

### Tool Function Signatures

Tool functions can have any signature. The MCP server will:
- Inject the `AsyncNextcloudApp` instance when needed
- Handle both sync and async functions
- Extract tool name and description from function metadata

Example signatures that work:
```python
# With Nextcloud instance as first parameter
async def my_tool(nc: AsyncNextcloudApp, param1: str) -> str:
    ...

# Without Nextcloud instance (uses context)
async def my_tool(param1: str) -> str:
    ...
```

## Design Philosophy

This MCP server follows a **minimalist approach**:

1. **Only Nextcloud APIs** - No external service integrations
2. **No LLM dependencies** - Pure tool gateway
3. **Clean separation** - Tools are independent of any AI agent
4. **Extensible** - Easy to add new Nextcloud capabilities
5. **Standalone** - Works without any other components

This allows the MCP server to be:
- **Reliable** - No dependencies on external services
- **Secure** - Only accesses Nextcloud's own data
- **Maintainable** - Clear scope and purpose
- **Reusable** - Can be used by any MCP client

## Security

- All requests are authenticated via Nextcloud's authentication system
- Each tool call runs in the context of the authenticated user
- Tools have access only to the resources the user has permission to access
- No external API calls mean no additional security surface

## License

AGPL-3.0-or-later - See LICENSE file for details.

## Contributing

Contributions are welcome! Please see the main [context_agent](https://github.com/nextcloud/context_agent) repository for contribution guidelines.
