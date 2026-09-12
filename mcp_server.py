"""
Epicenter's MCP server: codebase impact analysis for AI coding assistants.

The value here is precision. An assistant working without this has to guess at
structure from text search; these tools answer from a parsed call graph, so
"what calls this" is an actual answer rather than a grep that misses renames,
indirect calls, and inheritance.

Run directly for stdio transport:
    .venv/bin/python mcp_server.py
"""

import os
import sqlite3

from mcp.server.mcpserver import MCPServer

from epicenter import CodeGraph
from pipeline import ingest_codebase

DB_PATH = os.environ.get("EPICENTER_DB", "epicenter.db")

mcp = MCPServer(
    "epicenter",
    instructions=(
        "Precise dependency analysis for Python codebases, answered from a "
        "parsed call graph rather than text search. Call impact_of before "
        "editing a symbol to find everything that could break, including "
        "indirect callers that grep would miss."
    ),
)

# Graphs are rebuilt from SQLite on every call rather than cached, so results
# stay correct after a re-index. Loads are cheap at this scale; revisit with an
# mtime check if large repos make it hurt.


def _realms():
    try:
        conn = sqlite3.connect(DB_PATH)
        found = [r[0] for r in conn.execute("SELECT DISTINCT realm FROM nodes") if r[0]]
        conn.close()
        return found
    except Exception:
        return []


def _resolve_realm(codebase):
    """Picks which indexed codebase to query. With exactly one indexed, the
    caller can omit it entirely."""
    realms = _realms()
    if codebase:
        if codebase in realms:
            return codebase
        absolute = os.path.abspath(codebase)
        if absolute in realms:
            return absolute
        matches = [r for r in realms if codebase in r]
        if len(matches) == 1:
            return matches[0]
        raise ValueError(
            f"No indexed codebase matching {codebase!r}. Indexed: {realms or 'none'}"
        )
    if not realms:
        raise ValueError("No codebase has been indexed yet. Call index_codebase first.")
    if len(realms) > 1:
        raise ValueError(f"Several codebases indexed, pass one of: {realms}")
    return realms[0]


def _graph(codebase=None):
    return CodeGraph(db_path=DB_PATH, realm=_resolve_realm(codebase))


def _pick(graph, symbol):
    """Resolves a possibly-partial symbol name, reporting ambiguity rather than
    silently guessing when the alternatives are unrelated."""
    matches = graph.find_symbol(symbol)
    if not matches:
        raise ValueError(f"No symbol matching {symbol!r} in this codebase.")
    return matches[0], matches[1:]


# ─── Tools ──────────────────────────────────────────────────────────────────


@mcp.tool()
def list_codebases() -> str:
    """List the codebases that have been parsed and indexed into the graph."""
    realms = _realms()
    if not realms:
        return "No codebases indexed yet. Use index_codebase(path) to add one."
    return "Indexed codebases:\n" + "\n".join(f"  {r}" for r in realms)


@mcp.tool()
def index_codebase(path: str) -> str:
    """Parse a Python codebase and build its dependency graph.

    Run this once per codebase, and again after significant code changes, so
    that impact and dependency queries reflect current source.

    Args:
        path: Directory containing Python source files.
    """
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(target):
        return f"Not a directory: {target}"

    edges = ingest_codebase(target, db_path=DB_PATH)
    if not edges:
        return f"No Python files or no relationships found in {target}."

    graph = CodeGraph(db_path=DB_PATH, realm=target)
    stats = graph.stats()
    return (
        f"Indexed {target}\n"
        f"  {stats['symbols']} local symbols\n"
        f"  {stats['dependency_edges']} dependency edges\n"
        f"  {stats['containment_edges']} containment edges"
    )


@mcp.tool()
def impact_of(symbol: str, codebase: str = "", max_depth: int = 3) -> str:
    """Find everything that could break if a function, method, or class changes.

    Use this BEFORE editing or refactoring a symbol, and when assessing the
    risk of a change. Walks the call graph backwards, so it finds indirect
    callers that text search would miss. For a class, it also accounts for
    callers of that class's methods.

    Args:
        symbol: Name to analyse. Bare (`save_user`) or qualified (`db.save_user`).
        codebase: Which indexed codebase; omit if only one is indexed.
        max_depth: How many hops of indirect impact to follow.
    """
    graph = _graph(codebase)
    target, alternatives = _pick(graph, symbol)

    results = graph.impact_of(target, max_depth=max_depth)

    lines = [f"Impact analysis for: {target} ({graph.node_types.get(target, 'unknown')})"]
    if alternatives:
        lines.append(f"(other symbols matched {symbol!r}: {', '.join(alternatives[:5])})")
    lines.append("")

    if not results:
        lines.append("Nothing in this codebase depends on it. Safe to change freely.")
        return "\n".join(lines)

    direct = sum(1 for r in results if r.distance == 1)
    lines.append(f"{len(results)} symbol(s) affected — {direct} directly.")
    lines.append("")

    # With no tests at all, every symbol is trivially uncovered. Tagging them
    # would dress up an absence of information as a finding.
    has_tests = bool(graph.tests)
    current = None
    for item in results:
        if item.distance != current:
            current = item.distance
            header = "Direct callers" if current == 1 else f"Indirect, {current} hops away"
            lines.append(f"{header}:")
        risk = "  [HIGH FAN-IN] " if item.fanin >= 5 else "  "
        cover = "  [UNTESTED]" if has_tests and not graph.is_covered(item.symbol) else ""
        lines.append(f"{risk}{item.symbol} ({item.node_type}, {item.fanin} dependents){cover}")
        if item.distance > 1:
            lines.append(f"      reached via: {' <- '.join(reversed(item.path))}")

    lines.append("")
    untested = [i for i in results if not graph.is_covered(i.symbol)]
    if not graph.tests:
        lines.append("No tests detected in this codebase, so coverage is unknown.")
    elif untested:
        lines.append(
            f"{len(untested)} of {len(results)} affected symbol(s) have no test reaching them — "
            "the riskiest part of this change."
        )
    else:
        lines.append("Every affected symbol is reached by some test.")

    return "\n".join(lines)


@mcp.tool()
def test_coverage(symbol: str, codebase: str = "") -> str:
    """Find which tests exercise a symbol.

    Use when deciding whether a change is safe, or what test to run after
    making one. Reports reachability — a test that reaches this code may not
    assert anything about it.

    Args:
        symbol: Name to check.
        codebase: Which indexed codebase; omit if only one is indexed.
    """
    graph = _graph(codebase)
    target, _ = _pick(graph, symbol)

    if not graph.tests:
        return f"No tests detected in this codebase, so coverage of {target} is unknown."

    covering = graph.tests_covering(target)
    if not covering:
        return (
            f"No test reaches {target}. Changes to it are unverified by the "
            f"existing suite."
        )

    lines = [f"{target} is reached by {len(covering)} test(s):"]
    lines += [f"  {t}" for t in covering]
    lines.append("")
    lines.append("Reachability only — reaching a symbol is not the same as asserting on it.")
    return "\n".join(lines)


@mcp.tool()
def dead_code(codebase: str = "") -> str:
    """List symbols that no entrypoint and no test can reach.

    Use when looking for code to remove. Results are candidates for review,
    not confirmed dead code: call resolution is heuristic, so a symbol whose
    only caller could not be resolved will appear here wrongly.

    Args:
        codebase: Which indexed codebase; omit if only one is indexed.
    """
    graph = _graph(codebase)

    if not (graph.entrypoints or graph.tests):
        return (
            "No entrypoints or tests detected, so every symbol would appear dead. "
            "Reachability needs roots: a __main__ guard, a route decorator, or tests."
        )

    dead = graph.unreachable()
    if not dead:
        return "Every symbol is reachable from an entrypoint or a test."

    lines = [
        f"{len(dead)} symbol(s) unreachable from "
        f"{len(graph.entrypoints)} entrypoint(s) and {len(graph.tests)} test(s):"
    ]
    lines += [f"  {s} ({graph.node_types.get(s, 'unknown')})" for s in dead]
    lines.append("")
    lines.append("Candidates for review — verify before deleting. Unresolved calls "
                 "can make live code look dead.")
    return "\n".join(lines)


@mcp.tool()
def dependencies_of(symbol: str, codebase: str = "", max_depth: int = 1) -> str:
    """List what a symbol itself relies on — the code you need to read to
    understand or safely modify it.

    Use this to gather focused context about an unfamiliar function instead of
    reading whole files.

    Args:
        symbol: Name to analyse.
        codebase: Which indexed codebase; omit if only one is indexed.
        max_depth: 1 for immediate dependencies, higher to follow the chain.
    """
    graph = _graph(codebase)
    target, _ = _pick(graph, symbol)

    results = graph.dependencies_of(target, max_depth=max_depth)
    summary = graph.summaries.get(target, "")

    lines = [f"{target} ({graph.node_types.get(target, 'unknown')})"]
    if summary:
        lines.append(f"  {summary}")
    lines.append("")

    if not results:
        lines.append("Depends on nothing else in this codebase — it is self-contained.")
        return "\n".join(lines)

    lines.append(f"Depends on {len(results)} symbol(s):")
    for item in results:
        sig = graph.summaries.get(item.symbol, "")
        detail = f" — {sig}" if sig and not sig.startswith("Local codebase") else ""
        lines.append(f"  {item.symbol} ({item.node_type}){detail}")

    return "\n".join(lines)


@mcp.tool()
def find_symbol(query: str, codebase: str = "") -> str:
    """Search the graph for symbols matching a name.

    Use this when unsure of a symbol's exact qualified name before calling
    impact_of or dependencies_of.

    Args:
        query: Partial or full name to search for.
        codebase: Which indexed codebase; omit if only one is indexed.
    """
    graph = _graph(codebase)
    matches = graph.find_symbol(query, limit=25)
    if not matches:
        return f"No symbol matching {query!r}."

    lines = [f"{len(matches)} match(es) for {query!r}:"]
    for m in matches:
        lines.append(
            f"  {m} ({graph.node_types.get(m, 'unknown')}, "
            f"{graph.deps.in_degree(m)} dependents)"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
