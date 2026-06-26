# Nextcloud MCP Server with OAuth 2.1 and App Password Support

A dedicated MCP (Model Context Protocol) server for Nextcloud that provides:

- **OAuth 2.1 authentication** with PKCE (Proof Key for Code Exchange) support
- **Nextcloud App Password authentication** for simpler integrations
- **Dual authentication** allowing both methods to work side by side
- **File access operations** (CRUD, list, search)
- **Per-user access control** based on authentication method and scopes

## Features

### Authentication Methods

1. **OAuth 2.1 with PKCE** - Secure, modern authentication for web applications
   - Full OAuth 2.1 protocol implementation
   - PKCE support to prevent authorization code interception
   - Token exchange, refresh, and revocation
   - Granular scope-based permissions

2. **Nextcloud App Passwords** - Simple authentication for programmatic access
   - Uses existing Nextcloud App Password infrastructure
   - HTTP Basic Authentication support
   - Predefined access levels

3. **Legacy Token Authentication** - Backward compatibility with existing integrations
   - Maintains compatibility with current authentication methods
   - Gradual migration path

### File Operations

- **List files and directories** - Browse the file system
- **Read files** - Access file contents
- **Write files** - Create and modify files
- **Create files and directories** - Add new content
- **Delete files and directories** - Remove content
- **Get file information** - Retrieve metadata
- **Search files** - Find content by name or content
- **Check file existence** - Verify if a file exists

### Access Control

- **Per-user permissions** based on authentication method
- **Scope-based access** for OAuth users
- **Method-based restrictions** (e.g., App Passwords can't delete)
- **Configurable access levels** via settings

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server exApp                          │
├─────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │
│  │  OAuth 2.1       │    │ App Passwords    │    │ Legacy   │ │
│  │  Provider        │    │ Auth Handler     │    │ Auth     │ │
│  └────────┬────────┘    └────────┬────────┘    └────┬────┘ │
│           │                        │                     │        │
│           └────────────────────────┼─────────────────────┘        │
│                                    │                              │
│                    ┌───────────────▼───────────────┐            │
│                    │    Dual Authentication        │            │
│                    │    Middleware                 │            │
│                    └───────────────┬───────────────┘            │
│                                    │                              │
│                    ┌───────────────▼───────────────┐            │
│                    │    Access Control             │            │
│                    │    Middleware                 │            │
│                    └───────────────┬───────────────┘            │
│                                    │                              │
│                    ┌───────────────▼───────────────┐            │
│                    │    File Access Tools          │            │
│                    │    - list_files                │            │
│                    │    - read_file                 │            │
│                    │    - write_file                │            │
│                    │    - create_file               │            │
│                    │    - delete_file               │            │
│                    │    - create_directory          │            │
│                    │    - delete_directory          │            │
│                    │    - get_file_info             │            │
│                    │    - search_files              │            │
│                    │    - file_exists               │            │
│                    └───────────────────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Nextcloud instance with App API support
- Required Python packages (see `pyproject.toml`)

### Setup

1. Install the package:
   ```bash
   pip install -e .
   ```

2. The MCP server is automatically available as part of the exApp.

## Configuration

The MCP server can be configured through the Nextcloud admin settings:

### Authentication Methods

- **OAuth 2.1 (Recommended)** - Enable for modern, secure authentication
- **Nextcloud App Passwords** - Enable for simpler integrations
- **Legacy Token Authentication** - Enable for backward compatibility

### OAuth Settings

- **Default OAuth Scopes** - Default scopes for new OAuth clients
- **Access Token Expiration** - Token lifetime in seconds
- **Enable PKCE** - Require PKCE for OAuth authorization code flow

## Usage

### OAuth 2.1 Authentication

#### 1. Create an OAuth Client

```python
from ex_app.mcp_server import MCPServer

server = MCPServer()
nc_app = AsyncNextcloudApp()

# Initialize server
mcp = await server.initialize(nc_app)

# Create OAuth client for a user
client_credentials = await server.create_oauth_client(
    user_id="username",
    client_name="My MCP Client",
    redirect_uris=["http://localhost:8080/callback"]
)

print(f"Client ID: {client_credentials['client_id']}")
print(f"Client Secret: {client_credentials['client_secret']}")
```

#### 2. Authorization Flow with PKCE

```python
# Generate PKCE code verifier and challenge
import secrets
import base64
import hashlib

code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip('=')

# Get authorization URL
auth_url = await server.get_oauth_authorization_url(
    client_id=client_credentials['client_id'],
    redirect_uri="http://localhost:8080/callback",
    scopes=["read", "write"],
    state=secrets.token_urlsafe(32)
)

# Redirect user to auth_url for authorization
# After authorization, exchange code for tokens
```

#### 3. Exchange Authorization Code for Tokens

```python
# After receiving the authorization code from the redirect
auth_code = "AUTHORIZATION_CODE_FROM_REDIRECT"

# Exchange code for tokens (with PKCE verification)
# Note: This is handled automatically by the OAuth provider
```

#### 4. Use Access Token

```python
# Use the access token in requests
access_token = "YOUR_ACCESS_TOKEN"

# Make requests to the MCP server
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://nextcloud/mcp/tools/list",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )
```

### App Password Authentication

#### 1. Create an App Password in Nextcloud

1. Go to Nextcloud Settings → Security → App Passwords
2. Create a new app password for your application
3. Copy the generated password

#### 2. Use App Password in Requests

```python
import base64
import httpx

username = "your_username"
app_password = "your_app_password"

# Encode credentials for Basic Auth
credentials = f"{username}:{app_password}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://nextcloud/mcp/tools/list",
        headers={
            "Authorization": f"Basic {encoded_credentials}"
        }
    )
```

### File Operations

#### List Files

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://nextcloud/mcp/tools/call",
        json={
            "name": "list_files",
            "arguments": {
                "path": "/Documents",
                "include_hidden": False,
                "recursive": False
            }
        },
        headers={
            "Authorization": "Bearer YOUR_ACCESS_TOKEN"
        }
    )
    
    result = response.json()
    print(f"Files: {result['files']}")
    print(f"Directories: {result['directories']}")
```

#### Read File

```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://nextcloud/mcp/tools/call",
        json={
            "name": "read_file",
            "arguments": {
                "path": "/Documents/example.txt",
                "encoding": "utf-8"
            }
        },
        headers={
            "Authorization": "Bearer YOUR_ACCESS_TOKEN"
        }
    )
    
    result = response.json()
    print(f"Content: {result['content']}")
```

#### Write File

```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://nextcloud/mcp/tools/call",
        json={
            "name": "write_file",
            "arguments": {
                "path": "/Documents/example.txt",
                "content": "Hello, World!",
                "encoding": "utf-8",
                "overwrite": True
            }
        },
        headers={
            "Authorization": "Bearer YOUR_ACCESS_TOKEN"
        }
    )
    
    result = response.json()
    print(f"Success: {result['success']}")
```

## Access Control

### Authentication Method Access Levels

| Method | Read | Write | Delete | Admin | Search |
|--------|------|-------|--------|-------|--------|
| OAuth 2.1 | ✅ | ✅ | ✅ | ❌ | ✅ |
| App Password | ✅ | ✅ | ❌ | ❌ | ✅ |
| Legacy | ✅ | ❌ | ❌ | ❌ | ❌ |

### OAuth Scopes

- `read` - Read files and directories
- `write` - Create and modify files
- `delete` - Delete files and directories
- `admin` - Administrative operations
- `search` - Search for files

## Development

### Project Structure

```
ex_app/mcp_server/
├── __init__.py           # Main module exports
├── main.py              # Entry point for the exApp
├── server.py            # FastMCP server implementation
├── README.md            # This documentation
├── auth/
│   ├── __init__.py      # Auth module exports
│   ├── provider.py      # OAuth 2.1 provider
│   ├── app_password.py  # App Password authentication
│   └── middleware.py    # Authentication middleware
├── models/
│   ├── __init__.py      # Models module exports
│   ├── auth.py          # Authentication models
│   └── files.py         # File system models
└── tools/
    ├── __init__.py      # Tools module exports
    └── files.py         # File access tools
```

### Running Tests

```bash
# Run the MCP server directly
python -m ex_app.mcp_server.main

# Or use the existing exApp infrastructure
python -m ex_app.lib.main
```

## Security Considerations

1. **OAuth 2.1 with PKCE** is the most secure authentication method
2. **App Passwords** should be used for trusted internal applications only
3. **Legacy authentication** should be disabled when not needed
4. **Token expiration** should be set to appropriate values
5. **Access control** should be configured based on your security requirements

## Migration from Legacy Authentication

1. **Enable both OAuth and App Password** authentication methods
2. **Create OAuth clients** for existing users
3. **Update client applications** to use OAuth or App Passwords
4. **Monitor usage** of different authentication methods
5. **Gradually disable** legacy authentication when no longer needed

## License

AGPL-3.0-or-later

## Contributing

Contributions are welcome! Please follow the existing code style and patterns.
