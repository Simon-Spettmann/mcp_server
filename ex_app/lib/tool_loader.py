# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Tool loader for Nextcloud MCP Server.

Dynamically loads tool modules and registers them with the MCP server.
Each tool module should provide:
- get_tools(nc: AsyncNextcloudApp) -> list of tool functions
- get_category_name() -> str (optional)
- is_available(nc: AsyncNextcloudApp) -> bool (optional)
"""
import importlib
import inspect
import os
import pathlib
from os.path import dirname
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context
from nc_py_api import AsyncNextcloudApp


def get_nextcloud_from_context() -> AsyncNextcloudApp:
    """Get the Nextcloud instance from the FastMCP context."""
    ctx = get_context()
    nc = ctx.get_state("nextcloud")
    if nc is None:
        raise Exception("Nextcloud instance not found in context")
    return nc


async def load_tools_from_module(module_name: str, module_path: str, mcp: FastMCP):
    """Load tools from a single module and register them with MCP."""
    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        print(f"Could not load module {module_name} from {module_path}")
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Check if the module has get_tools function
    if not hasattr(module, "get_tools"):
        print(f"Module {module_name} does not have get_tools function")
        return

    get_tools_func = getattr(module, "get_tools")
    if not callable(get_tools_func):
        print(f"get_tools in {module_name} is not callable")
        return

    # Check availability if the module has is_available
    if hasattr(module, "is_available"):
        is_available_func = getattr(module, "is_available")
        if callable(is_available_func):
            try:
                nc = get_nextcloud_from_context()
                if not await is_available_func(nc):
                    print(f"Module {module_name} is not available")
                    return
            except Exception as e:
                print(f"Error checking availability for {module_name}: {e}")
                return

    # Get the tools from the module
    try:
        nc = get_nextcloud_from_context()
        tools = await get_tools_func(nc)
    except Exception as e:
        print(f"Error loading tools from {module_name}: {e}")
        return

    # Register each tool with MCP
    for tool in tools:
        await _register_tool_with_mcp(tool, mcp, module_name)


async def _register_tool_with_mcp(tool: Any, mcp: FastMCP, module_name: str):
    """Register a single tool with the MCP server."""
    # Get tool metadata
    tool_name = getattr(tool, "name", None)
    tool_description = getattr(tool, "description", "")
    tool_func = getattr(tool, "coroutine", None) or getattr(tool, "func", None)

    # If it's a langchain tool, extract the function
    if tool_func is None and hasattr(tool, "_run"):
        tool_func = tool._run

    if tool_func is None:
        # Maybe it's a regular function
        if callable(tool):
            tool_func = tool
            tool_name = getattr(tool, "__name__", f"tool_{id(tool)}")
            tool_description = getattr(tool, "__doc__", "") or ""
        else:
            print(f"Tool from {module_name} has no callable function")
            return

    if tool_name is None:
        tool_name = getattr(tool_func, "__name__", f"tool_{id(tool_func)}")

    # For langchain tools, get the actual function to call
    if hasattr(tool, "_run"):
        actual_func = tool._run
    else:
        actual_func = tool_func

    # Create a wrapper that handles the Nextcloud instance
    async def create_tool_wrapper(func: callable, nc_param_name: str = None) -> callable:
        """Create a wrapper that injects the Nextcloud instance."""
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Check if the function expects nc as a parameter
        has_nc_param = any(p in params for p in ["nc", "self"])

        async def wrapper(*args, **kwargs):
            nc = get_nextcloud_from_context()

            if has_nc_param:
                # Insert nc as first argument if it's expected
                if params and params[0] in ["nc", "self"]:
                    return await func(nc, *args, **kwargs)
                else:
                    # Find nc parameter position
                    for i, param in enumerate(params):
                        if param in ["nc", "self"]:
                            new_args = list(args)
                            new_args.insert(i, nc)
                            return await func(*new_args, **kwargs)

            # No nc parameter, just call with provided args
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper

    # Register with MCP
    wrapper_func = await create_tool_wrapper(actual_func)

    # Set better metadata
    if hasattr(tool, "name"):
        tool_name = tool.name
    if hasattr(tool, "description"):
        tool_description = tool.description

    mcp.tool(name=tool_name, description=tool_description)(wrapper_func)
    print(f"Registered tool: {tool_name} from {module_name}")


async def load_all_tools(mcp: FastMCP):
    """Load all tools from the tools directory."""
    directory = dirname(__file__) + "/tools"

    if not os.path.exists(directory):
        print(f"Tools directory not found: {directory}")
        return

    py_files = [f for f in os.listdir(directory) if f.endswith(".py") and f != "__init__.py"]

    for file in py_files:
        module_name = pathlib.Path(file).stem
        module_path = os.path.join(directory, file)
        await load_tools_from_module(module_name, module_path, mcp)


async def setup_mcp_server(mcp: FastMCP):
    """Set up the MCP server by loading all available tools."""
    await load_all_tools(mcp)
    print("MCP server setup complete")
