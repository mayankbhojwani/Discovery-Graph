import networkx as nx
from database import fetch_graph_data

class CuriosityEngine:
    def __init__(self, db_path="curiosity.db", realm=None):
        self.db_path = db_path
        self.realm = realm
        self.graph = nx.DiGraph()
        self.node_summaries = {}
        
        # Topological metrics
        self.degrees = {}
        self.betweenness = {}
        self.clustering = {}
        
        self.load_graph()

    def enrich_node_profile(self, title, summary):
        """Generates a structured dictionary containing B2B multi-dimensional profiles from the raw summary."""
        sentences = [s.strip() for s in summary.split(".") if s.strip()]
        
        # 1. Core Mechanism
        if len(sentences) > 0:
            core = sentences[0] + "."
        else:
            core = f"The functional operating architecture and execution engine of {title}."
            
        # 2. Cross-Over Application
        if len(sentences) > 1:
            cross_over = f"Adapting the structural logic of {title} (such as {sentences[1].lower()}) to optimize unrelated domains like high-frequency financial modeling, digital twin city simulations, or supply chain resilience."
        else:
            cross_over = f"Cross-domain deployment of {title} principles to stabilize and scale decentralized machine learning nodes or telemetry networks."
            
        # 3. Open Innovation Question
        if len(sentences) > 2:
            ref_idea = sentences[2].lower()
            if len(ref_idea) > 100:
                ref_idea = ref_idea[:100] + "..."
            question = f"How can we scale the operational constraints of {title} to bypass computational bottlenecks, particularly concerning {ref_idea}?"
        else:
            question = f"What security and consensus bottlenecks must be resolved to deploy the core dynamics of {title} in zero-trust, real-time edge environments?"
            
        return {
            "core_mechanism": core,
            "cross_over_application": cross_over,
            "open_innovation_question": question
        }

    def load_graph(self):
        """Loads nodes and edges from SQLite, populating the DiGraph, enriching profiles, and computing metrics."""
        nodes, edges = fetch_graph_data(self.db_path, self.realm)
        for node in nodes:
            title = node['title']
            self.node_summaries[title] = self.enrich_node_profile(title, node['summary'])
            self.graph.add_node(title)
        
        for edge in edges:
            self.graph.add_edge(edge['source'], edge['target'], weight=edge['weight'])
            
        # Compute network-wide metrics if graph is not empty
        if self.graph.number_of_nodes() > 0:
            self.degrees = dict(self.graph.degree())
            self.betweenness = nx.betweenness_centrality(self.graph)
            self.clustering = nx.clustering(self.graph.to_undirected())
        else:
            self.degrees = {}
            self.betweenness = {}
            self.clustering = {}

    def get_critical_system_bridges(self):
        """Identifies the top 3 nodes acting as bottlenecks in the active network."""
        if not self.betweenness:
            return []
        sorted_nodes = sorted(self.betweenness.items(), key=lambda x: x[1], reverse=True)
        return [node for node, score in sorted_nodes[:3]]

    def generate_discovery_horizons(self, seed_topic, max_depth=4, alpha=0.7, top_k=4):
        """
        Extracts multiple diverse paths branching out from the seed node.
        Applies a topological ranking matrix and an overlap penalty to guarantee diversity.
        """
        if seed_topic not in self.graph:
            return []

        # 1. Collect all paths starting from the seed_topic up to max_depth deep
        paths = []
        limit = 1000  # Safety threshold for dense sub-graphs
        
        def dfs(node, current_path):
            if len(paths) >= limit:
                return
            if len(current_path) >= 3:  # Interesting paths have at least 3 nodes (2 steps)
                paths.append(list(current_path))
            if len(current_path) - 1 < max_depth:
                for neighbor in self.graph.successors(node):
                    if neighbor not in current_path:
                        current_path.append(neighbor)
                        dfs(neighbor, current_path)
                        current_path.pop()

        dfs(seed_topic, [seed_topic])

        if not paths:
            return []

        # 2. Score each path using topological ranking matrix (inverse-degree & local clustering)
        def score_path(path):
            score = 0.0
            for node in path:
                deg = self.degrees.get(node, 0)
                clust = self.clustering.get(node, 0.0)
                # Inverse-degree penalty combined with low-clustering coefficient boost
                node_score = 1.0 / (((deg + 1.0) ** alpha) * (clust + 0.05))
                score += node_score
            return score / len(path)  # Normalize by path length

        scored_paths = [(p, score_path(p)) for p in paths]
        scored_paths.sort(key=lambda x: x[1], reverse=True)

        # 3. Diverse selection loop with shared node penalty
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

        return selected_paths
