# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from typing import Optional, Union

from nc_py_api import AsyncNextcloudApp


async def get_tools(nc: AsyncNextcloudApp):
	async def list_files(path: str = "/") -> list[dict]:
		"""
		List files in a directory
		:param path: The path to list files from (default: root directory)
		:return: List of files with their metadata
		"""
		files = await nc.files.list(path)
		return [
			{
				"name": file.name,
				"path": file.path,
				"type": "directory" if file.type == "dir" else "file",
				"size": getattr(file, "size", 0),
				"mtime": getattr(file, "mtime", None),
				"etag": getattr(file, "etag", None),
				"permissions": getattr(file, "permissions", None),
				"mimetype": getattr(file, "mimetype", None),
			}
			for file in files
		]

	async def get_file_info(path: str) -> dict:
		"""
		Get detailed information about a file or directory
		:param path: The path to the file or directory
		:return: File information
		"""
		files = await nc.files.list(os.path.dirname(path) or "/")
		for file in files:
			if file.path == path:
				return {
					"name": file.name,
					"path": file.path,
					"type": "directory" if file.type == "dir" else "file",
					"size": getattr(file, "size", 0),
					"mtime": getattr(file, "mtime", None),
					"etag": getattr(file, "etag", None),
					"permissions": getattr(file, "permissions", None),
					"mimetype": getattr(file, "mimetype", None),
				}
		raise ValueError(f"File not found: {path}")

	async def create_file(path: str, content: str = "") -> bool:
		"""
		Create a new file
		:param path: The path where to create the file
		:param content: The content of the file
		:return: True if successful
		"""
		return await nc.files.create(path, content)

	async def create_directory(path: str) -> bool:
		"""
		Create a new directory
		:param path: The path where to create the directory
		:return: True if successful
		"""
		return await nc.files.create_dir(path)

	async def delete_file(path: str) -> bool:
		"""
		Delete a file or directory
		:param path: The path of the file or directory to delete
		:return: True if successful
		"""
		return await nc.files.delete(path)

	async def read_file(path: str) -> str:
		"""
		Read the content of a file
		:param path: The path of the file to read
		:return: The content of the file
		"""
		return await nc.files.read(path)

	async def read_file_binary(path: str) -> bytes:
		"""
		Read the binary content of a file
		:param path: The path of the file to read
		:return: The binary content of the file
		"""
		content = await nc.files.read(path, binary=True)
		return content if isinstance(content, bytes) else content.encode('utf-8')

	async def write_file(path: str, content: Union[str, bytes]) -> bool:
		"""
		Write content to a file (create or overwrite)
		:param path: The path of the file to write to
		:param content: The content to write (string or bytes)
		:return: True if successful
		"""
		if isinstance(content, bytes):
			content = content.decode('utf-8', errors='replace')
		return await nc.files.create(path, content)

	async def upload_file(path: str, content: bytes) -> bool:
		"""
		Upload a file
		:param path: The path where to upload the file
		:param content: The binary content of the file
		:return: True if successful
		"""
		return await nc.files.upload(path, content)

	async def copy_file(source_path: str, destination_path: str) -> bool:
		"""
		Copy a file or directory
		:param source_path: The path of the file or directory to copy
		:param destination_path: The destination path
		:return: True if successful
		"""
		return await nc.files.copy(source_path, destination_path)

	async def move_file(source_path: str, destination_path: str) -> bool:
		"""
		Move or rename a file or directory
		:param source_path: The path of the file or directory to move
		:param destination_path: The destination path
		:return: True if successful
		"""
		return await nc.files.move(source_path, destination_path)

	async def search_files(query: str, path: str = "/") -> list[dict]:
		"""
		Search for files by name
		:param query: The search query
		:param path: The path to search in (default: root directory)
		:return: List of matching files
		"""
		all_files = []

		async def _search_in_directory(dir_path: str):
			try:
				files = await nc.files.list(dir_path)
				for file in files:
					if file.type == "dir":
						if query.lower() in file.name.lower():
							all_files.append({
								"name": file.name,
								"path": file.path,
								"type": "directory",
							})
						await _search_in_directory(file.path)
					elif query.lower() in file.name.lower():
						all_files.append({
							"name": file.name,
							"path": file.path,
							"type": "file",
							"size": getattr(file, "size", 0),
						})
				except Exception:
					pass

		await _search_in_directory(path)
		return all_files

	return [
		list_files,
		get_file_info,
		create_file,
		create_directory,
		delete_file,
		read_file,
		read_file_binary,
		write_file,
		upload_file,
		copy_file,
		move_file,
		search_files,
	]

def get_category_name():
	return "Files"

async def is_available(nc: AsyncNextcloudApp):
	return True
