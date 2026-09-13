"""
Storage behaviour.

Both cases here are regressions for bugs that lost data silently: no error,
no warning, just missing rows that made later analysis quietly wrong.
"""

from epicenter.database import fetch_graph_data
from epicenter.pipeline import ingest_codebase

SHARED_NAME = {
    "app.py": """
        def start():
            helper()

        def helper(): ...
    """,
}


def test_two_codebases_sharing_a_module_name_both_survive(tmp_path, project):
    """`nodes` was once keyed on title alone, so indexing a second project
    that also had an app.py silently discarded it via INSERT OR IGNORE.
    Module names like app, main, and utils collide constantly."""
    db = tmp_path / "shared.db"
    first = project(SHARED_NAME, name="first")
    second = project(SHARED_NAME, name="second")

    ingest_codebase(str(first), db_path=str(db))
    ingest_codebase(str(second), db_path=str(db))

    for realm in (first, second):
        nodes, _ = fetch_graph_data(str(db), str(realm))
        titles = {n["title"] for n in nodes}
        assert "app.start" in titles, f"{realm.name} lost its symbols"
        assert "app.helper" in titles


def test_reingest_leaves_other_codebases_alone(tmp_path, project):
    db = tmp_path / "shared.db"
    first = project(SHARED_NAME, name="first")
    second = project(SHARED_NAME, name="second")

    ingest_codebase(str(first), db_path=str(db))
    ingest_codebase(str(second), db_path=str(db))
    ingest_codebase(str(second), db_path=str(db))  # re-index one of them

    nodes, edges = fetch_graph_data(str(db), str(first))
    assert {n["title"] for n in nodes} >= {"app.start", "app.helper"}
    assert edges, "re-indexing another realm deleted this one's edges"


def test_contains_and_calls_edges_between_same_pair_coexist(tmp_path, project):
    """`edges` was keyed (source, target), so when a module both contained and
    called the same symbol, one edge overwrote the other."""
    db = tmp_path / "edges.db"
    root = project({
        "script.py": """
            def work(): ...

            work()
        """,
    })
    ingest_codebase(str(root), db_path=str(db))

    _, edges = fetch_graph_data(str(db), str(root))
    kinds = {
        e["edge_type"] for e in edges
        if e["source"] == "script" and e["target"] == "script.work"
    }
    assert kinds == {"contains", "calls"}


def test_schema_rebuilds_when_version_is_stale(tmp_path, project):
    """An old database on disk must be rebuilt rather than read with columns
    it does not have."""
    import sqlite3

    db = tmp_path / "stale.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nodes (title TEXT PRIMARY KEY, summary TEXT)")
    conn.execute("INSERT INTO nodes VALUES ('ancient', 'from an older schema')")
    conn.commit()
    conn.close()

    root = project(SHARED_NAME, name="fresh")
    ingest_codebase(str(root), db_path=str(db))

    nodes, _ = fetch_graph_data(str(db), str(root))
    titles = {n["title"] for n in nodes}
    assert "app.start" in titles
    assert "ancient" not in titles
