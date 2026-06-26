# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""File system models for MCP server."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """File information model."""

    id: int = Field(..., description="File ID")
    name: str = Field(..., description="File name")
    path: str = Field(..., description="Full path to the file")
    parent_path: str = Field(..., description="Parent directory path")
    size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    created: datetime = Field(..., description="Creation timestamp")
    etag: str = Field(..., description="ETag for cache validation")
    permissions: str = Field(..., description="File permissions")
    owner: str = Field(..., description="File owner user ID")

    @classmethod
    def from_nextcloud(cls, nc_file: dict, path: str, parent_path: str) -> "FileInfo":
        """Create FileInfo from Nextcloud file data."""
        return cls(
            id=nc_file.get("id", 0),
            name=nc_file.get("name", ""),
            path=path,
            parent_path=parent_path,
            size=nc_file.get("size", 0),
            mime_type=nc_file.get("mime", "application/octet-stream"),
            last_modified=datetime.fromtimestamp(nc_file.get("mtime", 0)),
            created=datetime.fromtimestamp(nc_file.get("ctime", 0)),
            etag=nc_file.get("etag", ""),
            permissions=nc_file.get("permissions", ""),
            owner=nc_file.get("owner", ""),
        )


class DirectoryInfo(BaseModel):
    """Directory information model."""

    id: int = Field(..., description="Directory ID")
    name: str = Field(..., description="Directory name")
    path: str = Field(..., description="Full path to the directory")
    parent_path: str = Field(..., description="Parent directory path")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    created: datetime = Field(..., description="Creation timestamp")
    permissions: str = Field(..., description="Directory permissions")
    owner: str = Field(..., description="Directory owner user ID")
    file_count: int = Field(default=0, description="Number of files in directory")
    directory_count: int = Field(default=0, description="Number of subdirectories")

    @classmethod
    def from_nextcloud(cls, nc_dir: dict, path: str, parent_path: str) -> "DirectoryInfo":
        """Create DirectoryInfo from Nextcloud directory data."""
        return cls(
            id=nc_dir.get("id", 0),
            name=nc_dir.get("name", ""),
            path=path,
            parent_path=parent_path,
            last_modified=datetime.fromtimestamp(nc_dir.get("mtime", 0)),
            created=datetime.fromtimestamp(nc_dir.get("ctime", 0)),
            permissions=nc_dir.get("permissions", ""),
            owner=nc_dir.get("owner", ""),
            file_count=nc_dir.get("file_count", 0),
            directory_count=nc_dir.get("directory_count", 0),
        )


class FileContent(BaseModel):
    """File content model."""

    content: str = Field(..., description="File content as text")
    encoding: str = Field(default="utf-8", description="Text encoding")
    mime_type: str = Field(..., description="MIME type of the content")
    size: int = Field(..., description="Content size in bytes")

    @classmethod
    def from_bytes(cls, content: bytes, mime_type: str) -> "FileContent":
        """Create FileContent from bytes."""
        try:
            text_content = content.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text_content = content.decode("latin-1")
            encoding = "latin-1"

        return cls(
            content=text_content,
            encoding=encoding,
            mime_type=mime_type,
            size=len(content),
        )


class SearchResult(BaseModel):
    """Search result model."""

    query: str = Field(..., description="Search query")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="List of search results")
    total: int = Field(default=0, description="Total number of results")
    limit: int = Field(default=100, description="Maximum results returned")
    offset: int = Field(default=0, description="Result offset")

    @classmethod
    def from_nextcloud(
        cls, query: str, nc_results: list, limit: int = 100, offset: int = 0
    ) -> "SearchResult":
        """Create SearchResult from Nextcloud search data."""
        return cls(
            query=query,
            results=nc_results,
            total=len(nc_results),
            limit=limit,
            offset=offset,
        )


class FileOperationResult(BaseModel):
    """Result of a file operation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(default="", description="Operation result message")
    file_info: Optional[FileInfo] = Field(default=None, description="File information if applicable")
    path: str = Field(default="", description="Path of the affected file/directory")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")

    @classmethod
    def success_result(
        cls, message: str = "", file_info: Optional[FileInfo] = None, path: str = ""
    ) -> "FileOperationResult":
        """Create a successful operation result."""
        return cls(success=True, message=message, file_info=file_info, path=path)

    @classmethod
    def error_result(cls, error: str, path: str = "") -> "FileOperationResult":
        """Create a failed operation result."""
        return cls(success=False, error=error, path=path)


class ListFilesResult(BaseModel):
    """Result of listing files in a directory."""

    path: str = Field(..., description="Directory path")
    files: List[FileInfo] = Field(default_factory=list, description="List of files")
    directories: List[DirectoryInfo] = Field(
        default_factory=list, description="List of directories"
    )
    total_files: int = Field(default=0, description="Total number of files")
    total_directories: int = Field(default=0, description="Total number of directories")

    @classmethod
    def from_nextcloud(cls, path: str, nc_files: list, nc_dirs: list) -> "ListFilesResult":
        """Create ListFilesResult from Nextcloud data."""
        files = []
        for nc_file in nc_files:
            file_path = (
                f"{path}/{nc_file.get('name', '')}" if path != "/" else f"/{nc_file.get('name', '')}"
            )
            parent_path = path if path != "/" else "/"
            files.append(FileInfo.from_nextcloud(nc_file, file_path, parent_path))

        directories = []
        for nc_dir in nc_dirs:
            dir_path = (
                f"{path}/{nc_dir.get('name', '')}" if path != "/" else f"/{nc_dir.get('name', '')}"
            )
            parent_path = path if path != "/" else "/"
            directories.append(DirectoryInfo.from_nextcloud(nc_dir, dir_path, parent_path))

        return cls(
            path=path,
            files=files,
            directories=directories,
            total_files=len(files),
            total_directories=len(directories),
        )
