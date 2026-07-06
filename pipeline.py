import urllib.request
import urllib.parse
import json
import sqlite3
import networkx as nx
from concurrent.futures import ThreadPoolExecutor

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"

import time

def fetch_json(url, params):
    """Utility to fetch JSON from API with proper headers to avoid blocks, including rate-limit retry handling."""
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    headers = {
        'User-Agent': 'CuriosityEngineBot/3.0 (anita@example.com) Python-urllib/3.0'
    }
    
    req = urllib.request.Request(full_url, headers=headers)
    max_retries = 4
    for attempt in range(max_retries):
        try:
            # Subtle delay of 50ms before requests to prevent triggering rate limiters
            time.sleep(0.05)
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                # Exponential backoff: sleep 0.5s, 1.0s, 2.0s
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise e
        except Exception as e:
            raise e

def get_section0_links(title):
    """Fetches list of standard article links in Section 0 (introduction) of a page."""
    params = {
        "action": "parse",
        "page": title,
        "section": 0,
        "prop": "links",
        "format": "json",
        "redirects": 1
    }
    try:
        res = fetch_json(WIKI_API_URL, params)
        if "parse" in res and "links" in res["parse"]:
            links = res["parse"]["links"]
            # ns=0 indicates main article namespace, filtering templates/files/categories
            return [link["*"] for link in links if link.get("ns") == 0]
    except Exception as e:
        print(f"Error fetching section 0 links for '{title}': {e}")
    return []

def harvest_ego_network(seed_node, limit_hop1=15, progress_callback=None):
    """
    Builds a 2-hop ego network around the seed_node.
    - Hop 1: fetches links in seed_node's introduction.
    - Hop 2: fetches links in the introduction of top limit_hop1 Hop 1 pages in parallel.
    - Resolves all outbound intro links for the entire pool in parallel.
    - Prunes isolated nodes and dead-ends.
    - Returns (nodes, edges) lists.
    """
    if progress_callback:
        progress_callback(10, "Extracting core topic synapses: Locating seed node links...")

    # Hop 1
    hop1_links = get_section0_links(seed_node)
    seen = {seed_node.lower()}
    pool = [seed_node]
    
    unique_hop1 = []
    for link in hop1_links:
        if link.lower() not in seen:
            seen.add(link.lower())
            unique_hop1.append(link)
            pool.append(link)
            
    if not unique_hop1:
        unique_hop1 = [seed_node]
        
    hop1_subset = unique_hop1[:limit_hop1]
    total_hop2_tasks = len(hop1_subset)
    
    if progress_callback:
        progress_callback(33, f"Weaving alternative conceptual paths: Expanded {total_hop2_tasks} source nodes...")

    # Hop 2 - Fetch in parallel using ThreadPool (throttled to prevent rate limits)
    with ThreadPoolExecutor(max_workers=5) as executor:
        hop2_results = list(executor.map(get_section0_links, hop1_subset))
        
    for links in hop2_results:
        for link in links:
            if link.lower() not in seen:
                seen.add(link.lower())
                pool.append(link)
                
    # Keep only first 80 nodes to guarantee fast API responses and prevent rate limits
    pool = pool[:80]
    
    if progress_callback:
        progress_callback(66, f"Stabilizing the puzzle matrix: Processing intro relationships for {len(pool)} topics...")

    # Fetch summaries in batches of 20 (fast)
    summaries = {}
    batch_size = 20
    for i in range(0, len(pool), batch_size):
        batch = pool[i:i+batch_size]
        batch_str = "|".join(batch)
        extract_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "titles": batch_str,
            "format": "json"
        }
        try:
            ext_data = fetch_json(WIKI_API_URL, extract_params)
            if "query" in ext_data and "pages" in ext_data["query"]:
                for page_id, page_info in ext_data["query"]["pages"].items():
                    title = page_info.get("title")
                    extract = page_info.get("extract", "")
                    if title:
                        if extract:
                            summaries[title] = extract[:250] + "..." if len(extract) > 250 else extract
                        else:
                            summaries[title] = f"A Wikipedia article about {title}."
        except Exception:
            pass

    # Fetch introductory links for ALL pages in the pool in parallel using ThreadPool (extremely fast!)
    if progress_callback:
        progress_callback(80, "Stabilizing the puzzle matrix: Constructing directed graph links...")
        
    with ThreadPoolExecutor(max_workers=5) as executor:
        all_links_results = list(executor.map(get_section0_links, pool))
        
    outbound_links = {}
    for title, links in zip(pool, all_links_results):
        outbound_links[title] = links

    # Build NetworkX graph
    G = nx.DiGraph()
    for title in pool:
        G.add_node(title)
        
    pool_set_lower = {title.lower(): title for title in pool}
    for source, links in outbound_links.items():
        for link in links:
            if link.lower() in pool_set_lower and source.lower() != link.lower():
                target = pool_set_lower[link.lower()]
                G.add_edge(source, target, weight=1.0)
                
    # Iterative pruning to filter isolated nodes (degree < 2)
    changed = True
    while changed:
        changed = False
        to_remove = [node for node in G.nodes() if G.in_degree(node) + G.out_degree(node) < 2]
        if to_remove:
            G.remove_nodes_from(to_remove)
            changed = True
            
    # Iterative pruning to remove dead ends / sources, but keep at least 40 nodes
    changed = True
    while changed and G.number_of_nodes() > 50:
        changed = False
        to_remove = []
        for node in G.nodes():
            if G.in_degree(node) == 0 or G.out_degree(node) == 0:
                to_remove.append(node)
        if to_remove:
            if G.number_of_nodes() - len(to_remove) >= 40:
                G.remove_nodes_from(to_remove)
                changed = True
            else:
                break
                
    # Reinforce connectivity with a circular cycle chain
    remaining = list(G.nodes())
    if len(remaining) > 1:
        for i in range(len(remaining)):
            src = remaining[i]
            tgt = remaining[(i + 1) % len(remaining)]
            G.add_edge(src, tgt, weight=1.2)
            
    # Compile results
    final_nodes = []
    for title in G.nodes():
        summary = summaries.get(title, f"A Wikipedia article about {title}.")
        final_nodes.append((title, summary))
        
    final_edges = []
    for u, v in G.edges():
        weight = G[u][v].get('weight', 1.0)
        final_edges.append((u, v, weight))
        
    if progress_callback:
        progress_callback(100, f"Stabilizing the puzzle matrix: Realm created with {len(final_nodes)} nodes and {len(final_edges)} edges!")
        
    return final_nodes, final_edges

def save_realm_to_db(realm_name, nodes, edges, db_path="curiosity.db"):
    """Saves harvested nodes and edges into the database under the realm name."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Insert nodes
    nodes_data = [(title, summary, realm_name) for title, summary in nodes]
    cursor.executemany("INSERT OR REPLACE INTO nodes (title, summary, realm) VALUES (?, ?, ?)", nodes_data)
    
    # 2. Insert edges
    edges_data = []
    for edge in edges:
        if len(edge) == 3:
            src, tgt, w = edge
        else:
            src, tgt = edge
            w = 1.0
        edges_data.append((src, tgt, w))
        
    cursor.executemany("INSERT OR REPLACE INTO edges (source, target, weight) VALUES (?, ?, ?)", edges_data)
    
    conn.commit()
    conn.close()
