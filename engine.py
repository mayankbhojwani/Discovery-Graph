import networkx as nx
from database import fetch_graph_data

class CuriosityEngine:
    def __init__(self, db_path="curiosity.db", realm=None):
        self.db_path = db_path
        self.realm = realm
        self.graph = nx.DiGraph()
        self.core_graph = nx.DiGraph()
        self.node_summaries = {}
        self.node_types = {}
        
        # Topological metrics
        self.degrees = {}
        self.betweenness = {}
        self.clustering = {}
        
        self.load_graph()

    def enrich_node_profile(self, title, summary, node_type):
        """Generates a structured dictionary containing architectural metrics and refactoring insights for the code node."""
        deg = self.degrees.get(title, 0)
        
        # 1. Core Mechanism
        core = f"A codebase {node_type} component. Definition/Signature: `{summary}`."
        
        # 2. Dependency Role & Coupling
        if deg > 5:
            coupling_desc = f"exhibits a high degree of coupling ({deg} connections), representing a major orchestrator or general utility module in the codebase graph."
        elif deg > 1:
            coupling_desc = f"maintains a moderate coupling level ({deg} connections), serving as a standard intermediate component."
        else:
            coupling_desc = f"is a specialized leaf component with minimal external dependencies, focusing on localized functionality."
        cross_over = f"This component {coupling_desc} When analyzing system flow, it functions as a target node for incoming dependency vectors."
        
        # 3. Architectural / Refactoring Question
        question = f"How can we isolate this {node_type} to enable modular unit testing, and what downstream dependencies would be affected if its implementation is modified?"
        
        return {
            "core_mechanism": core,
            "cross_over_application": cross_over,
            "open_innovation_question": question
        }

    def load_graph(self):
        """Loads codebase nodes and edges from SQLite, populating the DiGraph and calculating topological metrics."""
        nodes, edges = fetch_graph_data(self.db_path, self.realm)
        
        # Populate nodes & types
        for node in nodes:
            title = node['title']
            self.node_types[title] = node.get('node_type', 'unknown')
            self.graph.add_node(title)
            # Core graph includes only local codebase elements
            if self.node_types[title] in ["module", "class", "method", "function"]:
                self.core_graph.add_node(title)
        
        for edge in edges:
            src = edge['source']
            tgt = edge['target']
            weight = edge.get('weight', 1.0)
            etype = edge.get('edge_type', 'calls')
            
            # Add to full graph
            self.graph.add_edge(src, tgt, weight=weight, edge_type=etype)
            # Add to core graph if both nodes exist in the core graph
            if self.core_graph.has_node(src) and self.core_graph.has_node(tgt):
                self.core_graph.add_edge(src, tgt, weight=weight, edge_type=etype)
            
        # Compute network-wide metrics over the Core Architecture Graph by default
        active_metrics_graph = self.core_graph if self.core_graph.number_of_nodes() > 0 else self.graph
        
        self.degrees = dict(active_metrics_graph.degree())
        self.betweenness = nx.betweenness_centrality(active_metrics_graph)
        self.clustering = nx.clustering(active_metrics_graph.to_undirected())

        # Populate node descriptions using precomputed metrics
        for node in nodes:
            title = node['title']
            self.node_summaries[title] = self.enrich_node_profile(title, node['summary'], self.node_types[title])

    def get_critical_system_bridges(self):
        """Identifies the top 3 nodes acting as critical architectural bottlenecks in the active graph."""
        if not self.betweenness:
            return []
        sorted_nodes = sorted(self.betweenness.items(), key=lambda x: x[1], reverse=True)
        return [node for node, score in sorted_nodes[:3]]

    def generate_discovery_horizons(self, seed_topic, max_depth=4, alpha=0.7, top_k=4, include_external=False):
        """
        Extracts multiple diverse paths branching out from the seed code node.
        Applies a topological ranking matrix and a greedy overlap penalty to guarantee diversity.
        """
        # Determine the active graph to traverse
        active_graph = self.graph if include_external else self.core_graph
        if seed_topic not in active_graph:
            # Fallback to full graph if not in active graph
            active_graph = self.graph
            if seed_topic not in active_graph:
                return []

        paths = []
        limit = 1000  # Safety threshold for dense graphs
        
        def dfs(node, current_path):
            if len(paths) >= limit:
                return
            if len(current_path) >= 2:  # Paths of length >= 2 (at least 1 step) are useful for codebase traversal
                paths.append(list(current_path))
            if len(current_path) - 1 < max_depth:
                for neighbor in active_graph.successors(node):
                    if len(paths) >= limit:
                        break
                    if neighbor not in current_path:
                        current_path.append(neighbor)
                        dfs(neighbor, current_path)
                        current_path.pop()

        dfs(seed_topic, [seed_topic])

        if not paths:
            return []

        # Score paths using the B2B Code Understanding topological ranking matrix
        def score_path(path):
            score = 0.0
            for i, node in enumerate(path):
                deg = self.degrees.get(node, 0)
                clust = self.clustering.get(node, 0.0)
                between = self.betweenness.get(node, 0.0)
                node_type = self.node_types.get(node, "unknown")
                
                # 1. Hub Penalty: Penalize nodes with high degree (standard degree centrality penalty)
                hub_penalty = ((deg + 1.0) ** alpha)
                
                # Extra penalty for helper/utility names
                name_lower = node.lower()
                is_util = any(u in name_lower for u in ["util", "helper", "common", "base", "config", "sys", "os", "time"])
                if is_util:
                    hub_penalty *= 5.0
                if node_type == "external":
                    hub_penalty *= 2.0  # Encourage routing through codebase local files
                    
                # 2. Bridge Reward: Reward high betweenness centrality (highly connected bottlenecks)
                bridge_reward = 1.0 + (between * 50.0)
                
                # 3. Information Density: Boost local classes, methods, and functions relative to external dependencies
                type_boost = 1.2 if node_type in ["class", "method", "function"] else 0.8
                
                # Get contextual edge modifier from successor connection if available
                if i < len(path) - 1:
                    edge_data = active_graph.get_edge_data(node, path[i+1])
                    if edge_data:
                        edge_type = edge_data.get('edge_type', 'calls')
                        if edge_type == "inherits":
                            type_boost *= 1.5
                        elif edge_type == "calls":
                            type_boost *= 1.3
                        elif edge_type == "imports":
                            type_boost *= 0.7
                
                # Combined Node Score
                node_score = (bridge_reward * type_boost) / (hub_penalty * (clust + 0.05))
                score += node_score
                
            return score / len(path)  # Normalize by path length

        scored_paths = [(p, score_path(p)) for p in paths]
        scored_paths.sort(key=lambda x: x[1], reverse=True)

        # Diverse selection loop with shared node penalty
        selected_paths = []
        used_nodes = set()

        for _ in range(top_k):
            if not scored_paths:
                break
            
            best_path = None
            best_score = -1.0
            best_idx = -1
            
            for idx, (path, base_score) in enumerate(scored_paths):
                # Count nodes shared with already selected paths (excluding seed_topic)
                shared_count = sum(1 for n in path[1:] if n in used_nodes)
                # Penalty factor applied exponentially
                adjusted_score = base_score * (0.01 ** shared_count)
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_path = path
                    best_idx = idx
            
            if best_path:
                selected_paths.append(best_path)
                for n in best_path[1:]:
                    used_nodes.add(n)
                scored_paths.pop(best_idx)

        # ─── Data Science Telemetry Ingestion ───
        try:
            paths_metrics = []
            for idx, path in enumerate(selected_paths):
                metrics = self.evaluate_path_metrics(path)
                paths_metrics.append({
                    "track_index": idx + 1,
                    "path": path,
                    "metrics": metrics
                })
            self.log_session_telemetry(seed_topic, paths_metrics)
        except Exception as e:
            print(f"Telemetry logging error: {e}")

        return selected_paths

    def evaluate_path_metrics(self, path):
        """
        Calculates Serendipity (log-inverse degree) and Bridge Factor (betweenness centrality)
        for the intermediate nodes of the path, producing a Composite Discovery Score in [0, 1].
        """
        import math
        int_nodes = path[1:-1] if len(path) > 2 else path
        if not int_nodes:
            int_nodes = path
            
        # 1. Serendipity: average log-inverse degree
        serendipity_vals = []
        for v in int_nodes:
            deg = self.degrees.get(v, 0)
            serendipity_vals.append(1.0 / math.log(deg + 2.0))
            
        avg_serendipity = sum(serendipity_vals) / len(serendipity_vals) if serendipity_vals else 0.0
        norm_serendipity = min(1.0, avg_serendipity / 1.5)  # Scale to [0, 1]
        
        # 2. Bridge Factor: average betweenness centrality
        bridge_vals = [self.betweenness.get(v, 0.0) for v in int_nodes]
        avg_bridge = sum(bridge_vals) / len(bridge_vals) if bridge_vals else 0.0
        norm_bridge = min(1.0, avg_bridge * 5.0)  # Scale typical small centralities up
        
        # 3. Composite Discovery Score
        composite_score = (norm_serendipity * 0.5) + (norm_bridge * 0.5)
        
        return {
            "serendipity": avg_serendipity,
            "bridge_factor": avg_bridge,
            "composite_score": composite_score
        }

    def log_session_telemetry(self, seed_topic, paths_metrics):
        """Logs execution metrics to a local JSON file for session analysis."""
        import json
        import os
        from datetime import datetime
        
        log_file = "telemetry_logs.json"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "seed_topic": seed_topic,
            "realm": self.realm,
            "tracks": paths_metrics
        }
        
        data = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                     data = json.load(f)
            except Exception:
                 data = []
                 
        data.append(log_entry)
        
        try:
             with open(log_file, "w") as f:
                 json.dump(data, f, indent=2)
        except Exception as e:
             print(f"Error logging telemetry to file: {e}")
