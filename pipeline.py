import requests
import sqlite3
import re

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "SynapseHorizon/1.0 (contact@synapsehorizon.com) Python-requests/2.0"

def get_wikidata_entity(label):
    """Resolves a human label to a Wikidata Qid and normalized label."""
    params = {
        "action": "wbsearchentities",
        "search": label,
        "language": "en",
        "format": "json"
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(WIKIDATA_API_URL, params=params, headers=headers, timeout=10)
        data = r.json()
        if data.get("search"):
            # Return Qid, normalized label, and description
            first_match = data["search"][0]
            return first_match["id"], first_match["label"], first_match.get("description", "A semantic Wikidata concept.")
    except Exception as e:
        print(f"Error searching Wikidata entity: {e}")
    return None, None, None

def fetch_wikidata_2hop(seed_keyword):
    """
    Queries Wikidata via SPARQL to construct a 2-hop semantic network.
    Returns:
      edges: list of tuples (source_label, target_label, relationship_type)
      node_descriptions: dict mapping node_label -> description
    """
    qid, seed_label, seed_desc = get_wikidata_entity(seed_keyword)
    if not qid:
        return [], {}
    
    node_descriptions = {seed_label: seed_desc}
    edges = []
    
    # ─── Hop 1 Query ───
    # Find all direct claims from the seed entity
    hop1_query = f"""
    SELECT ?propLabel ?targetLabel ?target ?targetDescription WHERE {{
      VALUES ?item {{ wd:{qid} }}
      ?item ?p ?target .
      ?property wikibase:directClaim ?p .
      ?property rdfs:label ?propLabel .
      FILTER(LANG(?propLabel) = "en") .
      ?target rdfs:label ?targetLabel .
      FILTER(LANG(?targetLabel) = "en") .
      OPTIONAL {{
        ?target schema:description ?targetDescription .
        FILTER(LANG(?targetDescription) = "en") .
      }}
    }} LIMIT 50
    """
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json"
    }
    
    target_qids = []
    try:
        r = requests.get(WIKIDATA_SPARQL_URL, params={"query": hop1_query, "format": "json"}, headers=headers, timeout=15)
        res_data = r.json()
        bindings = res_data.get("results", {}).get("bindings", [])
        
        for b in bindings:
            prop_label = b["propLabel"]["value"]
            target_label = b["targetLabel"]["value"]
            target_url = b["target"]["value"]
            target_desc = b.get("targetDescription", {}).get("value", f"A Wikidata concept related to {target_label}.")
            
            # Extract Qid from URL
            m = re.search(r"Q\d+", target_url)
            if m:
                target_qid = m.group(0)
                target_qids.append(target_qid)
                
            edges.append((seed_label, target_label, prop_label))
            node_descriptions[target_label] = target_desc
            
    except Exception as e:
        print(f"Error in Wikidata Hop 1 SPARQL query: {e}")
        return [], {}

    if not target_qids:
        return edges, node_descriptions

    # ─── Hop 2 Query ───
    # Batch query top 12 targets to get Hop 2 connections
    batch_qids = target_qids[:12]
    values_clause = " ".join([f"wd:{q}" for q in batch_qids])
    
    hop2_query = f"""
    SELECT ?itemLabel ?propLabel ?targetLabel ?targetDescription WHERE {{
      VALUES ?item {{ {values_clause} }}
      ?item ?p ?target .
      ?property wikibase:directClaim ?p .
      ?property rdfs:label ?propLabel .
      FILTER(LANG(?propLabel) = "en") .
      ?target rdfs:label ?targetLabel .
      FILTER(LANG(?targetLabel) = "en") .
      OPTIONAL {{
        ?target schema:description ?targetDescription .
        FILTER(LANG(?targetDescription) = "en") .
      }}
      ?item rdfs:label ?itemLabel .
      FILTER(LANG(?itemLabel) = "en") .
    }} LIMIT 100
    """
    
    try:
        r = requests.get(WIKIDATA_SPARQL_URL, params={"query": hop2_query, "format": "json"}, headers=headers, timeout=15)
        res_data = r.json()
        bindings = res_data.get("results", {}).get("bindings", [])
        
        for b in bindings:
            source_label = b["itemLabel"]["value"]
            prop_label = b["propLabel"]["value"]
            target_label = b["targetLabel"]["value"]
            target_desc = b.get("targetDescription", {}).get("value", f"A Wikidata concept related to {target_label}.")
            
            edges.append((source_label, target_label, prop_label))
            node_descriptions[target_label] = target_desc
            
    except Exception as e:
        print(f"Error in Wikidata Hop 2 SPARQL query: {e}")

    # Sanitize labels: remove URIs, strip whitespace, remove duplicates
    sanitized_edges = []
    seen_edges = set()
    for src, tgt, rel in edges:
        # Simple cleanup
        src_clean = src.replace("http://www.wikidata.org/entity/", "").strip()
        tgt_clean = tgt.replace("http://www.wikidata.org/entity/", "").strip()
        rel_clean = rel.replace("http://www.wikidata.org/prop/direct/", "").strip()
        
        if (src_clean, tgt_clean) not in seen_edges and src_clean != tgt_clean:
            seen_edges.add((src_clean, tgt_clean))
            sanitized_edges.append((src_clean, tgt_clean, rel_clean))
            
    return sanitized_edges, node_descriptions

def ingest_horizon_data(seed_keyword, db_path="curiosity.db"):
    """
    Fetches Wikidata 2-hop edges and ingests them into the SQLite database.
    Wipes existing context for this seed_keyword workspace.
    """
    edges, node_descriptions = fetch_wikidata_2hop(seed_keyword)
    if not edges:
        return 0
    
    # Identify the actual normalized seed label to clear the correct workspace
    # Or just use the original seed_keyword as the workspace realm name
    workspace_realm = seed_keyword
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Clear stale cache for this specific workspace
    cursor.execute("""
        DELETE FROM edges 
        WHERE source IN (SELECT title FROM nodes WHERE realm = ?) 
           OR target IN (SELECT title FROM nodes WHERE realm = ?)
    """, (workspace_realm, workspace_realm))
    
    cursor.execute("DELETE FROM nodes WHERE realm = ?", (workspace_realm,))
    
    # 2. Insert nodes
    nodes_batch = []
    for title, desc in node_descriptions.items():
        nodes_batch.append((title, desc, workspace_realm))
        
    cursor.executemany("""
        INSERT OR IGNORE INTO nodes (title, summary, realm) 
        VALUES (?, ?, ?)
    """, nodes_batch)
    
    # 3. Insert edges
    edges_batch = []
    for src, tgt, rel in edges:
        edges_batch.append((src, tgt, 1.0))
        
    cursor.executemany("""
        INSERT OR IGNORE INTO edges (source, target, weight) 
        VALUES (?, ?, ?)
    """, edges_batch)
    
    conn.commit()
    conn.close()
    
    return len(edges)
