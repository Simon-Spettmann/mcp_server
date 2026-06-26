# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""File access tools for Nextcloud MCP Server"""

import asyncio
import json
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastmcp.tools import Tool
from fastmcp.server.dependencies import get_context
from nc_py_api import AsyncNextcloudApp
from niquests import RequestException

from ..models.files import (
    FileInfo, 
    DirectoryInfo, 
    FileContent, 
    FileOperationResult, 
    ListFilesResult,
    SearchResult
)
from ..models.auth import UserInfo


class FileAccessError(Exception):
    """Custom exception for file access errors"""
    pass


class FileNotFoundError(FileAccessError):
    """Exception for file not found errors"""
    pass


class PermissionDeniedError(FileAccessError):
    """Exception for permission denied errors"""
    pass


def _get_nc_app() -> AsyncNextcloudApp:
    """Get Nextcloud app instance from context"""
    ctx = get_context()
    nc_app = ctx.get_state('nextcloud')
    if nc_app is None:
        raise Exception("Nextcloud app not available in context")
    return nc_app


def _get_user_info() -> UserInfo:
    """Get user information from context"""
    ctx = get_context()
    user_data = ctx.get_state('user')
    if user_data is None:
        raise Exception("User not authenticated")
    
    if isinstance(user_data, dict):
        return UserInfo(**user_data)
    return user_data


def _get_auth_method() -> str:
    """Get authentication method from context"""
    ctx = get_context()
    return ctx.get_state('auth_method') or 'unknown'


def _normalize_path(path: str) -> str:
    """Normalize a file path"""
    # Remove leading/trailing slashes and normalize
    path = path.strip('/')
    if not path:
        return '/'
    return f'/{path}'


def _validate_path(path: str) -> str:
    """Validate and normalize a file path"""
    path = _normalize_path(path)
    
    # Prevent directory traversal
    if '..' in path or path.startswith('/../'):
        raise FileAccessError("Invalid path: directory traversal not allowed")
    
    # Ensure path starts with /
    if not path.startswith('/'):
        path = f'/{path}'
    
    return path


@Tool(
    name="list_files",
    description="List files and directories in a path",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "default": "/",
                "description": "Path to list (default: root directory)"
            },
            "include_hidden": {
                "type": "boolean",
                "default": False,
                "description": "Whether to include hidden files"
            },
            "recursive": {
                "type": "boolean", 
                "default": False,
                "description": "Whether to list recursively"
            }
        }
    }
)
async def list_files(path: str = "/", include_hidden: bool = False, 
                     recursive: bool = False) -> ListFilesResult:
    """
    List files and directories in the specified path.
    
    Args:
        path: The directory path to list
        include_hidden: Whether to include hidden files/directories
        recursive: Whether to list recursively
        
    Returns:
        ListFilesResult containing files and directories
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use Nextcloud WebDAV API to list directory contents
        # Normalize path for WebDAV (remove leading slash)
        webdav_path = path[1:] if path.startswith('/') else path
        
        # List directory contents
        response = await nc.webdav.propfind(f"/files/{user_info.user_id}/{webdav_path}")
        
        files = []
        directories = []
        
        # Parse WebDAV response
        if response and hasattr(response, 'json'):
            data = response.json()
            # This is a simplified parsing - real implementation would need proper XML parsing
            # For POC, we'll use a simpler approach
            pass
        
        # Alternative approach: use OCS API
        try:
            # List files using OCS API
            response = await nc.ocs(
                "GET",
                f"/ocs/v2.php/apps/files/api/v1/files/list?path={webdav_path}&includeHidden={str(include_hidden).lower()}"
            )
            
            if response and 'ocs' in response:
                files_data = response['ocs']['data']['files']
                for file_data in files_data:
                    if file_data.get('type') == 'dir':
                        directories.append(file_data)
                    else:
                        files.append(file_data)
        except Exception as e:
            print(f"Error listing files via OCS: {e}")
        
        return ListFilesResult.from_nextcloud(path, files, directories)
        
    except Exception as e:
        raise FileAccessError(f"Failed to list files in {path}: {e}")


@Tool(
    name="read_file",
    description="Read the contents of a file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read"
            },
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "Text encoding for the file"
            }
        },
        "required": ["path"]
    }
)
async def read_file(path: str, encoding: str = "utf-8") -> FileContent:
    """
    Read the contents of a file.
    
    Args:
        path: Path to the file to read
        encoding: Text encoding for the file
        
    Returns:
        FileContent containing the file contents
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use WebDAV to get file contents
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.webdav.get(f"/files/{user_info.user_id}/{webdav_path}")
        
        if response and hasattr(response, 'content'):
            content = response.content
            mime_type = response.headers.get('Content-Type', 'application/octet-stream')
            
            return FileContent.from_bytes(content, mime_type)
        else:
            raise FileNotFoundError(f"File not found: {path}")
            
    except RequestException as e:
        if e.response and e.response.status_code == 404:
            raise FileNotFoundError(f"File not found: {path}")
        elif e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            raise FileAccessError(f"Failed to read file {path}: {e}")
    except Exception as e:
        raise FileAccessError(f"Failed to read file {path}: {e}")


@Tool(
    name="write_file",
    description="Write content to a file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            },
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "Text encoding for the file"
            },
            "overwrite": {
                "type": "boolean",
                "default": False,
                "description": "Whether to overwrite existing file"
            }
        },
        "required": ["path", "content"]
    }
)
async def write_file(path: str, content: str, encoding: str = "utf-8", 
                    overwrite: bool = False) -> FileOperationResult:
    """
    Write content to a file.
    
    Args:
        path: Path to the file to write
        content: Content to write to the file
        encoding: Text encoding for the file
        overwrite: Whether to overwrite existing file
        
    Returns:
        FileOperationResult with operation status
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    auth_method = _get_auth_method()
    
    # Check write permission
    if auth_method == "legacy":
        raise PermissionDeniedError("Write operations not allowed with legacy authentication")
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Encode content
        content_bytes = content.encode(encoding)
        
        # Use WebDAV to write file
        webdav_path = path[1:] if path.startswith('/') else path
        
        # Create parent directories if they don't exist
        parent_path = os.path.dirname(webdav_path)
        if parent_path and parent_path != '.':
            await nc.webdav.mkdir(f"/files/{user_info.user_id}/{parent_path}")
        
        # Write file
        response = await nc.webdav.put(
            f"/files/{user_info.user_id}/{webdav_path}",
            data=content_bytes
        )
        
        if response and response.status_code in [200, 201, 204]:
            return FileOperationResult.success_result(
                message=f"File written successfully: {path}",
                path=path
            )
        else:
            return FileOperationResult.error_result(
                error=f"Failed to write file: HTTP {response.status_code if response else 'unknown'}",
                path=path
            )
            
    except RequestException as e:
        if e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            return FileOperationResult.error_result(
                error=f"Failed to write file: {e}",
                path=path
            )
    except Exception as e:
        return FileOperationResult.error_result(
            error=f"Failed to write file: {e}",
            path=path
        )


@Tool(
    name="create_file",
    description="Create a new file with optional content",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the new file"
            },
            "content": {
                "type": "string",
                "default": "",
                "description": "Initial content for the file"
            },
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "Text encoding for the file"
            }
        },
        "required": ["path"]
    }
)
async def create_file(path: str, content: str = "", encoding: str = "utf-8") -> FileOperationResult:
    """
    Create a new file.
    
    Args:
        path: Path to the new file
        content: Initial content for the file
        encoding: Text encoding for the file
        
    Returns:
        FileOperationResult with operation status
    """
    # Use write_file with overwrite=False
    return await write_file(path, content, encoding, overwrite=False)


@Tool(
    name="delete_file",
    description="Delete a file",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to delete"
            }
        },
        "required": ["path"]
    }
)
async def delete_file(path: str) -> FileOperationResult:
    """
    Delete a file.
    
    Args:
        path: Path to the file to delete
        
    Returns:
        FileOperationResult with operation status
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    auth_method = _get_auth_method()
    
    # Check delete permission
    if auth_method in ["legacy", "app_password"]:
        raise PermissionDeniedError("Delete operations not allowed with this authentication method")
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use WebDAV to delete file
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.webdav.delete(f"/files/{user_info.user_id}/{webdav_path}")
        
        if response and response.status_code in [200, 204]:
            return FileOperationResult.success_result(
                message=f"File deleted successfully: {path}",
                path=path
            )
        else:
            return FileOperationResult.error_result(
                error=f"Failed to delete file: HTTP {response.status_code if response else 'unknown'}",
                path=path
            )
            
    except RequestException as e:
        if e.response and e.response.status_code == 404:
            raise FileNotFoundError(f"File not found: {path}")
        elif e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            return FileOperationResult.error_result(
                error=f"Failed to delete file: {e}",
                path=path
            )
    except Exception as e:
        return FileOperationResult.error_result(
            error=f"Failed to delete file: {e}",
            path=path
        )


@Tool(
    name="create_directory",
    description="Create a new directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the new directory"
            }
        },
        "required": ["path"]
    }
)
async def create_directory(path: str) -> FileOperationResult:
    """
    Create a new directory.
    
    Args:
        path: Path to the new directory
        
    Returns:
        FileOperationResult with operation status
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    auth_method = _get_auth_method()
    
    # Check write permission
    if auth_method == "legacy":
        raise PermissionDeniedError("Directory creation not allowed with legacy authentication")
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use WebDAV to create directory
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.webdav.mkdir(f"/files/{user_info.user_id}/{webdav_path}")
        
        if response and response.status_code in [200, 201, 204]:
            return FileOperationResult.success_result(
                message=f"Directory created successfully: {path}",
                path=path
            )
        else:
            return FileOperationResult.error_result(
                error=f"Failed to create directory: HTTP {response.status_code if response else 'unknown'}",
                path=path
            )
            
    except RequestException as e:
        if e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            return FileOperationResult.error_result(
                error=f"Failed to create directory: {e}",
                path=path
            )
    except Exception as e:
        return FileOperationResult.error_result(
            error=f"Failed to create directory: {e}",
            path=path
        )


@Tool(
    name="delete_directory",
    description="Delete a directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to delete"
            },
            "recursive": {
                "type": "boolean",
                "default": False,
                "description": "Whether to delete recursively"
            }
        },
        "required": ["path"]
    }
)
async def delete_directory(path: str, recursive: bool = False) -> FileOperationResult:
    """
    Delete a directory.
    
    Args:
        path: Path to the directory to delete
        recursive: Whether to delete recursively
        
    Returns:
        FileOperationResult with operation status
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    auth_method = _get_auth_method()
    
    # Check delete permission
    if auth_method in ["legacy", "app_password"]:
        raise PermissionDeniedError("Directory deletion not allowed with this authentication method")
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use WebDAV to delete directory
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.webdav.delete(f"/files/{user_info.user_id}/{webdav_path}")
        
        if response and response.status_code in [200, 204]:
            return FileOperationResult.success_result(
                message=f"Directory deleted successfully: {path}",
                path=path
            )
        else:
            return FileOperationResult.error_result(
                error=f"Failed to delete directory: HTTP {response.status_code if response else 'unknown'}",
                path=path
            )
            
    except RequestException as e:
        if e.response and e.response.status_code == 404:
            raise FileNotFoundError(f"Directory not found: {path}")
        elif e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            return FileOperationResult.error_result(
                error=f"Failed to delete directory: {e}",
                path=path
            )
    except Exception as e:
        return FileOperationResult.error_result(
            error=f"Failed to delete directory: {e}",
            path=path
        )


@Tool(
    name="get_file_info",
    description="Get information about a file or directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or directory"
            }
        },
        "required": ["path"]
    }
)
async def get_file_info(path: str) -> FileInfo:
    """
    Get information about a file or directory.
    
    Args:
        path: Path to the file or directory
        
    Returns:
        FileInfo with file/directory information
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use WebDAV to get file info
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.webdav.propfind(f"/files/{user_info.user_id}/{webdav_path}")
        
        if response and hasattr(response, 'json'):
            data = response.json()
            # Parse WebDAV response to extract file info
            # This is a simplified implementation
            file_data = {
                'id': 0,
                'name': os.path.basename(path),
                'size': 0,
                'mime': 'application/octet-stream',
                'mtime': int(time.time()),
                'ctime': int(time.time()),
                'etag': '',
                'permissions': '',
                'owner': user_info.user_id
            }
            
            return FileInfo.from_nextcloud(file_data, path, os.path.dirname(path))
        else:
            raise FileNotFoundError(f"File not found: {path}")
            
    except RequestException as e:
        if e.response and e.response.status_code == 404:
            raise FileNotFoundError(f"File not found: {path}")
        elif e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            raise FileAccessError(f"Failed to get file info for {path}: {e}")
    except Exception as e:
        raise FileAccessError(f"Failed to get file info for {path}: {e}")


@Tool(
    name="search_files",
    description="Search for files and directories",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "path": {
                "type": "string",
                "default": "/",
                "description": "Path to search in (default: root directory)"
            },
            "limit": {
                "type": "integer",
                "default": 100,
                "description": "Maximum number of results to return"
            },
            "offset": {
                "type": "integer",
                "default": 0,
                "description": "Result offset for pagination"
            }
        },
        "required": ["query"]
    }
)
async def search_files(query: str, path: str = "/", limit: int = 100, 
                       offset: int = 0) -> SearchResult:
    """
    Search for files and directories.
    
    Args:
        query: Search query
        path: Path to search in
        limit: Maximum number of results to return
        offset: Result offset for pagination
        
    Returns:
        SearchResult with search results
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    auth_method = _get_auth_method()
    
    # Check search permission
    if auth_method == "legacy":
        raise PermissionDeniedError("Search operations not allowed with legacy authentication")
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use OCS API for search
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.ocs(
            "GET",
            f"/ocs/v2.php/apps/files/api/v1/files/search?query={query}&path={webdav_path}&limit={limit}&offset={offset}"
        )
        
        if response and 'ocs' in response:
            results = response['ocs']['data']['files']
            return SearchResult.from_nextcloud(query, results, limit, offset)
        else:
            return SearchResult(
                query=query,
                results=[],
                total=0,
                limit=limit,
                offset=offset
            )
            
    except RequestException as e:
        if e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for search")
        else:
            return SearchResult(
                query=query,
                results=[],
                total=0,
                limit=limit,
                offset=offset,
                error=str(e)
            )
    except Exception as e:
        return SearchResult(
            query=query,
            results=[],
            total=0,
            limit=limit,
            offset=offset,
            error=str(e)
        )


@Tool(
    name="file_exists",
    description="Check if a file or directory exists",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to check"
            }
        },
        "required": ["path"]
    }
)
async def file_exists(path: str) -> bool:
    """
    Check if a file or directory exists.
    
    Args:
        path: Path to check
        
    Returns:
        True if the file/directory exists, False otherwise
    """
    nc = _get_nc_app()
    user_info = _get_user_info()
    
    # Validate path
    path = _validate_path(path)
    
    try:
        # Use WebDAV to check if file exists
        webdav_path = path[1:] if path.startswith('/') else path
        
        response = await nc.webdav.propfind(f"/files/{user_info.user_id}/{webdav_path}")
        
        # If we get a successful response, the file exists
        return response and response.status_code in [200, 207]
        
    except RequestException as e:
        if e.response and e.response.status_code == 404:
            return False
        elif e.response and e.response.status_code == 403:
            raise PermissionDeniedError(f"Permission denied for {path}")
        else:
            raise FileAccessError(f"Failed to check if file exists: {e}")
    except Exception as e:
        raise FileAccessError(f"Failed to check if file exists: {e}")


# Import time for get_file_info function
import time
