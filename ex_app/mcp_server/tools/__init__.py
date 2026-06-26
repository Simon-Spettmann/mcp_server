# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""File access tools for MCP Server."""

from .files import (
    list_files,
    read_file,
    write_file,
    create_file,
    delete_file,
    create_directory,
    delete_directory,
    get_file_info,
    search_files,
    file_exists,
)

# List of all file tools
file_tools = [
    list_files,
    read_file,
    write_file,
    create_file,
    delete_file,
    create_directory,
    delete_directory,
    get_file_info,
    search_files,
    file_exists,
]

__all__ = [
    "file_tools",
    "list_files",
    "read_file",
    "write_file",
    "create_file",
    "delete_file",
    "create_directory",
    "delete_directory",
    "get_file_info",
    "search_files",
    "file_exists",
]
