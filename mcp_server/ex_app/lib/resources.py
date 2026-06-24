# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
MCP Resources for Nextcloud MCP Server.

Resources allow MCP clients to browse and discover Nextcloud data structures.
Each resource represents a browsable URI that can be read to get structured data.
"""
import json
from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context
from nc_py_api import AsyncNextcloudApp

from ex_app.lib.mcp_server import get_nextcloud_from_context


def get_nc_from_context() -> AsyncNextcloudApp:
    """Get Nextcloud instance from FastMCP context."""
    return get_nextcloud_from_context()


async def list_resources() -> list[dict[str, Any]]:
    """List all available Nextcloud resources."""
    return [
        {
            "uri": "nextcloud://files/",
            "name": "Files",
            "description": "Browse Nextcloud files and directories",
            "mimeType": "application/json",
            "size": None,
        },
        {
            "uri": "nextcloud://calendars/",
            "name": "Calendars",
            "description": "Browse Nextcloud calendars and events",
            "mimeType": "application/json",
            "size": None,
        },
        {
            "uri": "nextcloud://contacts/",
            "name": "Contacts",
            "description": "Browse Nextcloud contacts and address books",
            "mimeType": "application/json",
            "size": None,
        },
        {
            "uri": "nextcloud://mail/",
            "name": "Mail",
            "description": "Browse Nextcloud mail accounts and mailboxes",
            "mimeType": "application/json",
            "size": None,
        },
        {
            "uri": "nextcloud://talk/",
            "name": "Talk",
            "description": "Browse Nextcloud Talk conversations",
            "mimeType": "application/json",
            "size": None,
        },
        {
            "uri": "nextcloud://shares/",
            "name": "Shares",
            "description": "Browse Nextcloud file shares",
            "mimeType": "application/json",
            "size": None,
        },
    ]


async def read_resource(uri: str) -> dict[str, Any]:
    """Read a Nextcloud resource by URI."""
    nc = get_nc_from_context()

    # Parse the URI
    if not uri.startswith("nextcloud://"):
        raise ValueError(f"Invalid resource URI: {uri}")

    path = uri[len("nextcloud://") :]
    parts = path.rstrip("/").split("/")

    if not parts or parts == [""]:
        # Root resource - list all top-level resources
        return {
            "type": "directory",
            "name": "Nextcloud",
            "uri": "nextcloud://",
            "children": [
                {"type": "directory", "name": "files", "uri": "nextcloud://files/"},
                {"type": "directory", "name": "calendars", "uri": "nextcloud://calendars/"},
                {"type": "directory", "name": "contacts", "uri": "nextcloud://contacts/"},
                {"type": "directory", "name": "mail", "uri": "nextcloud://mail/"},
                {"type": "directory", "name": "talk", "uri": "nextcloud://talk/"},
            ],
        }

    resource_type = parts[0]
    resource_path = "/".join(parts[1:]) if len(parts) > 1 else ""

    # Handle each resource type
    if resource_type == "files":
        return await _read_files_resource(nc, resource_path)
    elif resource_type == "calendars":
        return await _read_calendars_resource(nc, resource_path)
    elif resource_type == "contacts":
        return await _read_contacts_resource(nc, resource_path)
    elif resource_type == "mail":
        return await _read_mail_resource(nc, resource_path)
    elif resource_type == "talk":
        return await _read_talk_resource(nc, resource_path)
    elif resource_type == "shares":
        return await _read_shares_resource(nc, resource_path)
    else:
        raise ValueError(f"Unknown resource type: {resource_type}")


async def _read_shares_resource(nc: AsyncNextcloudApp, path: str) -> dict[str, Any]:
    """Read shares resource."""
    try:
        if path == "":
            # List all shares for the current user
            shares = await nc.ocs("GET", "/ocs/v2.php/apps/files_sharing/api/v1/shares")
            shares_data = shares.get("ocs", {}).get("data", [])

            # Group by share type
            user_shares = [s for s in shares_data if s.get("share_type") == 0]
            group_shares = [s for s in shares_data if s.get("share_type") == 1]
            link_shares = [s for s in shares_data if s.get("share_type") == 3]

            return {
                "type": "directory",
                "name": "Shares",
                "uri": "nextcloud://shares/",
                "children": [
                    {
                        "type": "directory",
                        "name": "User Shares",
                        "uri": "nextcloud://shares/users/",
                        "count": len(user_shares),
                    },
                    {
                        "type": "directory",
                        "name": "Group Shares",
                        "uri": "nextcloud://shares/groups/",
                        "count": len(group_shares),
                    },
                    {
                        "type": "directory",
                        "name": "Public Links",
                        "uri": "nextcloud://shares/links/",
                        "count": len(link_shares),
                    },
                ],
            }
        elif path.startswith("users/"):
            # List user shares
            shares = await nc.ocs("GET", "/ocs/v2.php/apps/files_sharing/api/v1/shares", params={"share_type": 0})
            shares_data = shares.get("ocs", {}).get("data", [])
            return {
                "type": "directory",
                "name": "User Shares",
                "uri": "nextcloud://shares/users/",
                "children": [
                    {
                        "type": "share",
                        "name": s.get("share_with_displayname", s.get("share_with", f"Share {s.get('id')}")),
                        "uri": f"nextcloud://shares/users/{s.get('id')}",
                        "id": s.get("id"),
                        "path": s.get("path"),
                        "permissions": s.get("permissions"),
                    }
                    for s in shares_data
                ],
            }
        elif path.startswith("groups/"):
            # List group shares
            shares = await nc.ocs("GET", "/ocs/v2.php/apps/files_sharing/api/v1/shares", params={"share_type": 1})
            shares_data = shares.get("ocs", {}).get("data", [])
            return {
                "type": "directory",
                "name": "Group Shares",
                "uri": "nextcloud://shares/groups/",
                "children": [
                    {
                        "type": "share",
                        "name": s.get("share_with_displayname", s.get("share_with", f"Share {s.get('id')}")),
                        "uri": f"nextcloud://shares/groups/{s.get('id')}",
                        "id": s.get("id"),
                        "path": s.get("path"),
                        "permissions": s.get("permissions"),
                    }
                    for s in shares_data
                ],
            }
        elif path.startswith("links/"):
            # List public link shares
            shares = await nc.ocs("GET", "/ocs/v2.php/apps/files_sharing/api/v1/shares", params={"share_type": 3})
            shares_data = shares.get("ocs", {}).get("data", [])
            return {
                "type": "directory",
                "name": "Public Links",
                "uri": "nextcloud://shares/links/",
                "children": [
                    {
                        "type": "share",
                        "name": s.get("path", f"Link {s.get('id')}"),
                        "uri": f"nextcloud://shares/links/{s.get('id')}",
                        "id": s.get("id"),
                        "path": s.get("path"),
                        "token": s.get("token"),
                        "url": s.get("url"),
                        "permissions": s.get("permissions"),
                    }
                    for s in shares_data
                ],
            }
        else:
            # Get specific share info
            share_id = path
            share = await nc.ocs("GET", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}")
            share_data = share.get("ocs", {}).get("data", {})
            return {
                "type": "share",
                "name": share_data.get("path", f"Share {share_id}"),
                "uri": f"nextcloud://shares/{share_id}",
                **share_data,
            }
    except Exception as e:
        raise ValueError(f"Failed to read shares: {e}")


async def _read_files_resource(nc: AsyncNextcloudApp, path: str) -> dict[str, Any]:
    """Read files resource."""
    try:
        if path == "":
            # List root directory
            files = await nc.files.list("/")
            return {
                "type": "directory",
                "name": "Files",
                "uri": "nextcloud://files/",
                "path": "/",
                "children": [
                    {
                        "type": "directory" if file.type == "dir" else "file",
                        "name": file.name,
                        "uri": f"nextcloud://files/{file.path}",
                        "path": file.path,
                        "size": getattr(file, "size", 0),
                        "mtime": getattr(file, "mtime", None),
                    }
                    for file in files
                ],
            }
        else:
            # List specific directory
            files = await nc.files.list(path)
            return {
                "type": "directory",
                "name": path.split("/")[-1] or "/",
                "uri": f"nextcloud://files/{path}",
                "path": path,
                "children": [
                    {
                        "type": "directory" if file.type == "dir" else "file",
                        "name": file.name,
                        "uri": f"nextcloud://files/{file.path}",
                        "path": file.path,
                        "size": getattr(file, "size", 0),
                        "mtime": getattr(file, "mtime", None),
                    }
                    for file in files
                ],
            }
    except Exception as e:
        raise ValueError(f"Failed to read files: {e}")


async def _read_calendars_resource(nc: AsyncNextcloudApp, path: str) -> dict[str, Any]:
    """Read calendars resource."""
    try:
        if path == "":
            # List all calendars
            calendars = await nc.calendar.get_calendars()
            return {
                "type": "directory",
                "name": "Calendars",
                "uri": "nextcloud://calendars/",
                "children": [
                    {
                        "type": "directory",
                        "name": cal.display_name,
                        "uri": f"nextcloud://calendars/{cal.id}",
                        "id": cal.id,
                        "color": getattr(cal, "color", None),
                    }
                    for cal in calendars
                ],
            }
        else:
            # List events in a specific calendar
            calendar_id = path
            events = await nc.calendar.get_events(calendar_id)
            return {
                "type": "directory",
                "name": "Events",
                "uri": f"nextcloud://calendars/{calendar_id}",
                "calendarId": calendar_id,
                "children": [
                    {
                        "type": "event",
                        "name": event.summary,
                        "uri": f"nextcloud://calendars/{calendar_id}/{event.uid}",
                        "id": event.uid,
                        "start": event.begin,
                        "end": event.end,
                        "description": event.description,
                        "location": event.location,
                    }
                    for event in events
                ],
            }
    except Exception as e:
        raise ValueError(f"Failed to read calendars: {e}")


async def _read_contacts_resource(nc: AsyncNextcloudApp, path: str) -> dict[str, Any]:
    """Read contacts resource."""
    try:
        if path == "":
            # List all contacts
            contacts = await nc.contacts.get_all(limit=100)
            return {
                "type": "directory",
                "name": "Contacts",
                "uri": "nextcloud://contacts/",
                "children": [
                    {
                        "type": "contact",
                        "name": contact.display_name,
                        "uri": f"nextcloud://contacts/{contact.id}",
                        "id": contact.id,
                        "email": getattr(contact, "email", None),
                    }
                    for contact in contacts
                ],
            }
        else:
            # Get specific contact
            contact_id = path
            contacts = await nc.contacts.get_all(limit=100)
            contact = next((c for c in contacts if c.id == contact_id), None)
            if contact is None:
                raise ValueError(f"Contact not found: {contact_id}")
            return {
                "type": "contact",
                "name": contact.display_name,
                "uri": f"nextcloud://contacts/{contact.id}",
                "id": contact.id,
                "email": getattr(contact, "email", None),
                "phone": getattr(contact, "phone", None),
                "address": getattr(contact, "address", None),
            }
    except Exception as e:
        raise ValueError(f"Failed to read contacts: {e}")


async def _read_mail_resource(nc: AsyncNextcloudApp, path: str) -> dict[str, Any]:
    """Read mail resource."""
    try:
        if path == "":
            # List all mail accounts
            accounts = await nc.ocs("GET", "/ocs/v2.php/apps/mail/account/list")
            return {
                "type": "directory",
                "name": "Mail Accounts",
                "uri": "nextcloud://mail/",
                "children": [
                    {
                        "type": "directory",
                        "name": account.get("name", account.get("email", f"Account {i}")),
                        "uri": f"nextcloud://mail/{account.get('id')}",
                        "id": account.get("id"),
                    }
                    for i, account in enumerate(accounts.get("ocs", {}).get("data", []))
                ],
            }
        else:
            # List mailboxes in a specific account
            account_id = path
            mailboxes = await nc.ocs("GET", "/ocs/v2.php/apps/mail/ocs/mailboxes", json={"accountId": account_id})
            return {
                "type": "directory",
                "name": "Mailboxes",
                "uri": f"nextcloud://mail/{account_id}",
                "accountId": account_id,
                "children": [
                    {
                        "type": "directory",
                        "name": mb.get("name", mb.get("displayname", "Unknown")),
                        "uri": f"nextcloud://mail/{account_id}/{mb.get('id')}",
                        "id": mb.get("id"),
                    }
                    for mb in mailboxes.get("ocs", {}).get("data", [])
                ],
            }
    except Exception as e:
        raise ValueError(f"Failed to read mail: {e}")


async def _read_talk_resource(nc: AsyncNextcloudApp, path: str) -> dict[str, Any]:
    """Read Talk resource."""
    try:
        if path == "":
            # List all conversations
            conversations = await nc.talk.get_user_conversations()
            return {
                "type": "directory",
                "name": "Conversations",
                "uri": "nextcloud://talk/",
                "children": [
                    {
                        "type": "directory",
                        "name": conv.display_name,
                        "uri": f"nextcloud://talk/{conv.token}",
                        "token": conv.token,
                    }
                    for conv in conversations
                ],
            }
        else:
            # Get specific conversation
            conversation_token = path
            conversations = await nc.talk.get_user_conversations()
            conversation = next((c for c in conversations if c.token == conversation_token), None)
            if conversation is None:
                raise ValueError(f"Conversation not found: {conversation_token}")

            messages = await nc.talk.receive_messages(conversation, False, 50)
            return {
                "type": "conversation",
                "name": conversation.display_name,
                "uri": f"nextcloud://talk/{conversation.token}",
                "token": conversation.token,
                "messages": [
                    {
                        "timestamp": m.timestamp,
                        "actor": m.actor_display_name,
                        "message": m.message,
                    }
                    for m in messages
                ],
            }
    except Exception as e:
        raise ValueError(f"Failed to read talk: {e}")


def register_resources(mcp: FastMCP):
    """Register all Nextcloud resources with the MCP server."""

    # Register resource listing
    @mcp.resource("nextcloud://")
    async def list_nextcloud_resources() -> list[dict[str, Any]]:
        return await list_resources()

    # Register resource reading
    @mcp.resource("nextcloud://{path:path}")
    async def read_nextcloud_resource(path: str) -> dict[str, Any]:
        return await read_resource(f"nextcloud://{path}")
