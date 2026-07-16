import sqlite3
import os

DB_NAME = "curiosity.db"

def get_db_connection(db_path=DB_NAME):
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db(db_path=DB_NAME):
    """Creates tables for the Code Understanding Engine."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check schema and recreate tables if they are using the old Wikidata/Wikipedia schemas
    try:
        cursor.execute("PRAGMA table_info(nodes)")
        columns = [col[1] for col in cursor.fetchall()]
        # If 'node_type' is missing, recreate tables
        if columns and "node_type" not in columns:
            cursor.execute("DROP TABLE IF EXISTS edges")
            cursor.execute("DROP TABLE IF EXISTS nodes")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nodes (
        title TEXT PRIMARY KEY,
        summary TEXT NOT NULL,
        realm TEXT NOT NULL,
        node_type TEXT NOT NULL DEFAULT 'unknown'
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS edges (
        source TEXT,
        target TEXT,
        weight REAL DEFAULT 1.0,
        edge_type TEXT NOT NULL DEFAULT 'calls',
        PRIMARY KEY (source, target),
        FOREIGN KEY (source) REFERENCES nodes (title),
        FOREIGN KEY (target) REFERENCES nodes (title)
    )
    """)
    
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
    
    # 1. Clear existing records for this realm
    cursor.execute("""
        DELETE FROM edges 
        WHERE source IN (SELECT title FROM nodes WHERE realm = ?) 
           OR target IN (SELECT title FROM nodes WHERE realm = ?)
    """, (realm, realm))
    
    cursor.execute("DELETE FROM nodes WHERE realm = ?", (realm,))
    
    # 2. Insert nodes
    nodes_batch = []
    for node in nodes:
        nodes_batch.append((node["title"], node["summary"], realm, node.get("node_type", "unknown")))
        
    cursor.executemany("""
        INSERT OR IGNORE INTO nodes (title, summary, realm, node_type) 
        VALUES (?, ?, ?, ?)
    """, nodes_batch)
    
    # 3. Insert edges
    edges_batch = []
    for edge in edges:
        edges_batch.append((edge["source"], edge["target"], edge.get("weight", 1.0), edge.get("edge_type", "calls")))
        
    cursor.executemany("""
        INSERT OR IGNORE INTO edges (source, target, weight, edge_type) 
        VALUES (?, ?, ?, ?)
    """, edges_batch)
    
    conn.commit()
    conn.close()

def fetch_graph_data(db_path=DB_NAME, realm=None):
    """Queries nodes and edges from the SQLite database, optionally filtered by realm."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    if realm:
        cursor.execute("SELECT title, summary, node_type FROM nodes WHERE realm = ?", (realm,))
        nodes = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT source, target, weight, edge_type FROM edges 
            WHERE source IN (SELECT title FROM nodes WHERE realm = ?) 
              AND target IN (SELECT title FROM nodes WHERE realm = ?)
        """, (realm, realm))
        edges = [dict(row) for row in cursor.fetchall()]
    else:
        cursor.execute("SELECT title, summary, node_type FROM nodes")
        nodes = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT source, target, weight, edge_type FROM edges")
        edges = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return nodes, edges
