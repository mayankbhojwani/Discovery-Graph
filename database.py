import sqlite3
import os

DB_NAME = "epicenter.db"

# Bumped whenever the table layout changes in a way old rows cannot satisfy.
# v2: nodes/edges became realm-scoped. Before this, `title` was the sole
# primary key on `nodes` and `(source, target)` on `edges`, so two indexed
# codebases sharing a module name (app, main, utils...) collided: the second
# ingest was silently swallowed by INSERT OR IGNORE.
# v3: nodes carry `roles` (test / entrypoint), the roots for coverage and
# reachability analysis.
SCHEMA_VERSION = 3

def get_db_connection(db_path=DB_NAME):
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db(db_path=DB_NAME):
    """Creates tables for the Code Understanding Engine."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Rebuild from scratch when the stored layout predates SCHEMA_VERSION. The
    # tables are a cache of parsed source, so dropping them costs only a
    # re-ingest of each realm.
    current_version = cursor.execute("PRAGMA user_version").fetchone()[0]
    if current_version < SCHEMA_VERSION:
        cursor.execute("DROP TABLE IF EXISTS edges")
        cursor.execute("DROP TABLE IF EXISTS nodes")
        cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nodes (
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        realm TEXT NOT NULL,
        node_type TEXT NOT NULL DEFAULT 'unknown',
        roles TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (title, realm)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS edges (
        source TEXT NOT NULL,
        target TEXT NOT NULL,
        realm TEXT NOT NULL,
        weight REAL DEFAULT 1.0,
        edge_type TEXT NOT NULL DEFAULT 'calls',
        PRIMARY KEY (source, target, edge_type, realm)
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_realm ON nodes (realm)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_realm ON edges (realm)")

    conn.commit()
    conn.close()

def save_code_graph_to_db(realm, nodes, edges, db_path=DB_NAME):
    """
    Clears out stale code graph cache for the specific realm (codebase path)
    and saves the new nodes and edges.
    """
    initialize_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 1. Clear existing records for this realm only. Matching on the edges'
    #    own realm column keeps a re-ingest from touching other codebases that
    #    happen to share symbol names.
    cursor.execute("DELETE FROM edges WHERE realm = ?", (realm,))
    cursor.execute("DELETE FROM nodes WHERE realm = ?", (realm,))

    # 2. Insert nodes
    nodes_batch = []
    for node in nodes:
        nodes_batch.append((
            node["title"],
            node["summary"],
            realm,
            node.get("node_type", "unknown"),
            ",".join(node.get("roles", [])),
        ))

    cursor.executemany("""
        INSERT OR IGNORE INTO nodes (title, summary, realm, node_type, roles)
        VALUES (?, ?, ?, ?, ?)
    """, nodes_batch)

    # 3. Insert edges
    edges_batch = []
    for edge in edges:
        edges_batch.append((
            edge["source"],
            edge["target"],
            realm,
            edge.get("weight", 1.0),
            edge.get("edge_type", "calls"),
        ))

    cursor.executemany("""
        INSERT OR IGNORE INTO edges (source, target, realm, weight, edge_type)
        VALUES (?, ?, ?, ?, ?)
    """, edges_batch)
    
    conn.commit()
    conn.close()

def fetch_graph_data(db_path=DB_NAME, realm=None):
    """Queries nodes and edges from the SQLite database, optionally filtered by realm."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    if realm:
        cursor.execute("SELECT title, summary, node_type, roles FROM nodes WHERE realm = ?", (realm,))
        nodes = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT source, target, weight, edge_type FROM edges WHERE realm = ?
        """, (realm,))
        edges = [dict(row) for row in cursor.fetchall()]
    else:
        cursor.execute("SELECT title, summary, node_type, roles FROM nodes")
        nodes = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT source, target, weight, edge_type FROM edges")
        edges = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return nodes, edges
