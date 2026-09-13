"""
Package-shaped projects: relative imports, public exports, and knowing what
not to walk into.

Every case here came from running Epicenter against a real library rather
than against flat single-directory samples.
"""

import os

from epicenter.pipeline import parse_repository
from tests.conftest import call_edges, roles_of


def test_relative_import_resolves(parsed):
    """`from .store import Database` names pkg.store, not "store"."""
    nodes, edges = parsed({
        "pkg/__init__.py": "",
        "pkg/store.py": """
            class Database:
                def save(self, row): ...
        """,
        "pkg/svc.py": """
            from .store import Database

            def work(row):
                db = Database()
                db.save(row)
        """,
    })
    assert ("pkg.svc.work", "pkg.store.Database.save") in call_edges(edges)


def test_parent_relative_import_resolves(parsed):
    """`from ..store import Database`, two levels up."""
    nodes, edges = parsed({
        "pkg/__init__.py": "",
        "pkg/store.py": """
            class Database:
                def save(self, row): ...
        """,
        "pkg/inner/__init__.py": "",
        "pkg/inner/svc.py": """
            from ..store import Database

            def work(row):
                db = Database()
                db.save(row)
        """,
    })
    assert ("pkg.inner.svc.work", "pkg.store.Database.save") in call_edges(edges)


def test_public_exports_are_entrypoints(project):
    """A library's callers live outside the codebase, so its __init__
    re-exports are where execution enters."""
    root = project({
        "pkg/__init__.py": "from .api import public_thing\n",
        "pkg/api.py": """
            def public_thing(): ...

            def _private_helper(): ...
        """,
    })
    nodes, _ = parse_repository(str(root))
    assert "entrypoint" in roles_of(nodes, "pkg.api.public_thing")
    assert "entrypoint" not in roles_of(nodes, "pkg.api._private_helper")


def test_star_export_publishes_the_whole_module(project):
    root = project({
        "pkg/__init__.py": "from .api import *\n",
        "pkg/api.py": "def exported(): ...\n",
    })
    nodes, _ = parse_repository(str(root))
    assert "entrypoint" in roles_of(nodes, "pkg.api.exported")


def test_indexing_a_package_directory_keeps_its_name(project, tmp_path):
    """Pointing at networkx/ or src/mypackage/ must not drop the package's own
    name, or its absolute self-imports match nothing."""
    project({
        "__init__.py": "",
        "core.py": "def work(): ...\n",
    }, name="mypackage")
    nodes, _ = parse_repository(str(tmp_path / "mypackage"))
    titles = {n["title"] for n in nodes}
    assert "mypackage.core.work" in titles


def test_pytest_lifecycle_hooks_count_as_tests(parsed):
    """setup_class is called by the runner, and lives on shared base classes
    that are not named Test* at all."""
    nodes, _ = parsed({
        "tests/base_test.py": """
            class BaseMixingSuite:
                def setup_class(cls): ...
        """,
    })
    assert "test" in roles_of(nodes, "tests.base_test.BaseMixingSuite.setup_class")


def test_environment_directories_are_not_walked(project, tmp_path):
    """A virtualenv named anything at all must be skipped; indexing one
    floods the graph with thousands of third-party symbols."""
    root = project({
        "main.py": "def go(): ...\n",
        "custom-env/pyvenv.cfg": "home = /usr/bin\n",
        "custom-env/lib/site.py": "def library_thing(): ...\n",
        "conda-style/conda-meta/history": "",
        "conda-style/lib/other.py": "def another_thing(): ...\n",
    })
    nodes, _ = parse_repository(str(root))
    titles = {n["title"] for n in nodes}
    assert any("go" in t for t in titles)
    assert not any("library_thing" in t for t in titles)
    assert not any("another_thing" in t for t in titles)
