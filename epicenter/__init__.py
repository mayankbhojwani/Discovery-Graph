"""
Epicenter: name a symbol, see everything that shakes.

Impact analysis over a parsed Python dependency graph. The public surface is
the CodeGraph class; the CLI lives in `epicenter.cli` and the MCP server in
`epicenter.mcp_server`.
"""

from .graph import CodeGraph, Impacted

__all__ = ["CodeGraph", "Impacted"]
__version__ = "0.1.0"
