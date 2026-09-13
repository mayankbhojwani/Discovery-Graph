"""
Shared fixtures.

Sample projects are written into tmp_path rather than checked in under
tests/fixtures. A real Python package sitting in the repo would be picked up
whenever Epicenter indexes itself, quietly polluting its own graph and its
dead-code output.
"""

import textwrap

import pytest

from epicenter import CodeGraph
from epicenter.pipeline import ingest_codebase, parse_repository


def _write(root, files):
    for relpath, source in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source).lstrip())
    return root


@pytest.fixture
def project(tmp_path):
    """Writes a mapping of {relative path: source} into a temp directory."""
    def build(files, name="proj"):
        root = tmp_path / name
        root.mkdir(exist_ok=True)
        return _write(root, files)
    return build


@pytest.fixture
def parsed(project):
    """Parser output for a sample project, without touching SQLite."""
    def build(files, name="proj"):
        return parse_repository(str(project(files, name)))
    return build


@pytest.fixture
def graph(tmp_path, project):
    """A CodeGraph over a sample project, ingested through SQLite."""
    def build(files, name="proj"):
        root = project(files, name)
        db = tmp_path / f"{name}.db"
        ingest_codebase(str(root), db_path=str(db))
        return CodeGraph(db_path=str(db), realm=str(root))
    return build


# ─── Assertion helpers ──────────────────────────────────────────────────────


def call_edges(edges):
    return {(e["source"], e["target"]) for e in edges if e["edge_type"] == "calls"}


def roles_of(nodes, title):
    for node in nodes:
        if node["title"] == title:
            return set(node.get("roles", []))
    raise AssertionError(f"no node named {title!r} in {[n['title'] for n in nodes]}")
