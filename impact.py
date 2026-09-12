"""
Impact analysis over the parsed codebase graph.

Answers the question a developer actually asks before editing something:
"if I change this, what breaks?"

The core distinction this module makes is between *dependency* edges and
*structural* edges. An edge `A --calls--> B` means A depends on B, so a change
to B propagates back to A. An edge `module --contains--> class` means no such
thing: containment describes where code lives, not what relies on what.
Mixing the two (as a single combined DiGraph does) makes reachability leak
through containment until every symbol appears to depend on every other.
"""

import networkx as nx
from database import fetch_graph_data

# Edges along which a change propagates, mapped to how strongly it does so.
# Reading `A --edge--> B` as "A depends on B", a change to B reaches A.
DEPENDENCY_EDGES = {
    "calls": 1.0,
    "inherits": 1.0,
    "imports": 0.4,
}

# Structural edges: used for grouping and lookup, never for propagation.
STRUCTURAL_EDGES = {"contains"}

LOCAL_TYPES = {"module", "class", "method", "function"}


class Impacted:
    """One symbol affected by a change, plus how the change reaches it."""

    def __init__(self, symbol, distance, path, node_type, fanin):
        self.symbol = symbol
        self.distance = distance      # hops from the changed symbol
        self.path = path              # [changed, ..., this] chain of blame
        self.node_type = node_type
        self.fanin = fanin            # how many things depend on *this* in turn

    def __repr__(self):
        return f"<Impacted {self.symbol} d={self.distance} fanin={self.fanin}>"


class CodeGraph:
    """
    Loads a parsed realm out of SQLite and exposes dependency queries over it.

    Two graphs are maintained deliberately:
      * `deps`     — A -> B meaning "A depends on B" (calls/inherits/imports)
      * `contains` — parent -> child (module -> class -> method)
    """

    def __init__(self, db_path="curiosity.db", realm=None, include_external=False):
        self.db_path = db_path
        self.realm = realm
        self.include_external = include_external

        self.deps = nx.DiGraph()
        self.contains = nx.DiGraph()
        self.node_types = {}
        self.summaries = {}

        self._load()

    # ─── Loading ────────────────────────────────────────────────────────────

    def _is_local(self, symbol):
        return self.node_types.get(symbol, "unknown") in LOCAL_TYPES

    def _keep(self, symbol):
        return self.include_external or self._is_local(symbol)

    def _load(self):
        nodes, edges = fetch_graph_data(self.db_path, self.realm)

        for node in nodes:
            title = node["title"]
            self.node_types[title] = node.get("node_type", "unknown")
            self.summaries[title] = node.get("summary", "")

        for node in nodes:
            title = node["title"]
            if self._keep(title):
                self.deps.add_node(title)
                self.contains.add_node(title)

        for edge in edges:
            src, tgt = edge["source"], edge["target"]
            etype = edge.get("edge_type", "calls")

            if not (self._keep(src) and self._keep(tgt)):
                continue
            if src == tgt:
                continue

            if etype in STRUCTURAL_EDGES:
                self.contains.add_edge(src, tgt)
            elif etype in DEPENDENCY_EDGES:
                # Keep the strongest edge type if a pair is connected twice.
                weight = DEPENDENCY_EDGES[etype]
                existing = self.deps.get_edge_data(src, tgt)
                if existing is None or weight > existing.get("weight", 0):
                    self.deps.add_edge(src, tgt, weight=weight, edge_type=etype)

    # ─── Symbol lookup ──────────────────────────────────────────────────────

    def find_symbol(self, query, limit=10):
        """
        Resolves a user-typed name to real symbols, most specific match first.
        Accepts a bare name (`save_code_graph_to_db`), a partial dotted path
        (`database.save_code_graph_to_db`), or a fully-qualified one.
        """
        query = query.strip()
        if query in self.node_types and self._keep(query):
            return [query]

        candidates = [s for s in self.deps.nodes() if self._keep(s)]
        lowered = query.lower()

        exact_leaf = [s for s in candidates if s.split(".")[-1] == query]
        suffix = [s for s in candidates if s.endswith("." + query) and s not in exact_leaf]
        partial = [
            s for s in candidates
            if lowered in s.lower() and s not in exact_leaf and s not in suffix
        ]

        ordered = exact_leaf + suffix + sorted(partial, key=len)
        return ordered[:limit]

    def members_of(self, symbol):
        """All symbols structurally nested under `symbol` (a module's classes,
        a class's methods), transitively. Used to expand a coarse query."""
        if symbol not in self.contains:
            return set()
        return set(nx.descendants(self.contains, symbol))

    # ─── The core query ─────────────────────────────────────────────────────

    def impact_of(self, symbol, max_depth=None, expand_members=True):
        """
        Everything that could break if `symbol` changes.

        Walks the dependency graph *backwards* (breadth-first, so the recorded
        path is the shortest chain of blame) from `symbol` and, when
        `expand_members` is set, from everything nested inside it — changing a
        class means changing its methods, so its methods' callers are affected
        too.

        Returns Impacted records sorted by distance, then by fan-in: a nearby
        symbol that many other things depend on is the more dangerous one.
        """
        if symbol not in self.node_types:
            raise KeyError(f"unknown symbol: {symbol}")

        seeds = {symbol}
        if expand_members:
            seeds |= self.members_of(symbol)
        seeds = {s for s in seeds if s in self.deps}

        if not seeds:
            return []

        reverse = self.deps.reverse(copy=False)

        # Multi-source BFS. `origin` records which seed a symbol was reached
        # from so the blame path can be reconstructed.
        distance = {s: 0 for s in seeds}
        parent = {}
        queue = list(seeds)
        order = []

        while queue:
            nxt = []
            for node in queue:
                if max_depth is not None and distance[node] >= max_depth:
                    continue
                for dependent in reverse.successors(node):
                    if dependent in distance:
                        continue
                    distance[dependent] = distance[node] + 1
                    parent[dependent] = node
                    order.append(dependent)
                    nxt.append(dependent)
            queue = nxt

        results = []
        for node in order:
            path = [node]
            cur = node
            while cur in parent:
                cur = parent[cur]
                path.append(cur)
            path.reverse()

            results.append(
                Impacted(
                    symbol=node,
                    distance=distance[node],
                    path=path,
                    node_type=self.node_types.get(node, "unknown"),
                    fanin=self.deps.in_degree(node),
                )
            )

        results.sort(key=lambda i: (i.distance, -i.fanin, i.symbol))
        return results

    def dependencies_of(self, symbol, max_depth=1):
        """The inverse direction: what `symbol` itself relies on. This is the
        raw material for assembling reading context around a symbol."""
        if symbol not in self.deps:
            return []

        distance = {symbol: 0}
        queue = [symbol]
        order = []

        while queue:
            nxt = []
            for node in queue:
                if distance[node] >= max_depth:
                    continue
                for dep in self.deps.successors(node):
                    if dep in distance:
                        continue
                    distance[dep] = distance[node] + 1
                    order.append(dep)
                    nxt.append(dep)
            queue = nxt

        return [
            Impacted(
                symbol=n,
                distance=distance[n],
                path=[],
                node_type=self.node_types.get(n, "unknown"),
                fanin=self.deps.in_degree(n),
            )
            for n in order
        ]

    def stats(self):
        return {
            "realm": self.realm,
            "symbols": self.deps.number_of_nodes(),
            "dependency_edges": self.deps.number_of_edges(),
            "containment_edges": self.contains.number_of_edges(),
        }


# ─── CLI ────────────────────────────────────────────────────────────────────

def _default_realm(db_path):
    """Uses the only indexed realm if there is exactly one, so the common case
    needs no --realm flag."""
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        realms = [r[0] for r in conn.execute("SELECT DISTINCT realm FROM nodes") if r[0]]
        conn.close()
    except Exception:
        return None
    return realms[0] if len(realms) == 1 else None


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Ask what breaks if you change something.")
    parser.add_argument("--db", default="curiosity.db")
    parser.add_argument("--realm", default=None, help="indexed codebase path")
    parser.add_argument("--external", action="store_true", help="include builtins and third-party symbols")

    sub = parser.add_subparsers(dest="command", required=True)

    p_impact = sub.add_parser("impact", help="what breaks if this changes")
    p_impact.add_argument("symbol")
    p_impact.add_argument("--depth", type=int, default=None)

    p_deps = sub.add_parser("deps", help="what this relies on")
    p_deps.add_argument("symbol")
    p_deps.add_argument("--depth", type=int, default=1)

    p_find = sub.add_parser("find", help="look up a symbol name")
    p_find.add_argument("query")

    sub.add_parser("stats", help="graph size")

    args = parser.parse_args()

    realm = args.realm or _default_realm(args.db)
    graph = CodeGraph(db_path=args.db, realm=realm, include_external=args.external)

    if args.command == "stats":
        for key, value in graph.stats().items():
            print(f"{key:20} {value}")
        return

    if args.command == "find":
        matches = graph.find_symbol(args.query)
        if not matches:
            print(f"no symbol matching {args.query!r}")
            sys.exit(1)
        for m in matches:
            print(f"{m}  ({graph.node_types.get(m, 'unknown')})")
        return

    matches = graph.find_symbol(args.symbol)
    if not matches:
        print(f"no symbol matching {args.symbol!r}")
        sys.exit(1)
    if len(matches) > 1:
        print(f"{args.symbol!r} is ambiguous, using {matches[0]}")
        print("  other matches: " + ", ".join(matches[1:5]))
        print()
    target = matches[0]

    if args.command == "impact":
        results = graph.impact_of(target, max_depth=args.depth)
        if not results:
            print(f"Nothing depends on {target}. Safe to change.")
            return

        print(f"Changing {target} could affect {len(results)} symbol(s):\n")
        current = None
        for item in results:
            if item.distance != current:
                current = item.distance
                label = "directly" if current == 1 else f"{current} hops away"
                print(f"  ── {label} ──")
            flag = "  ⚠" if item.fanin >= 5 else "   "
            print(f"{flag} {item.symbol}  ({item.node_type}, {item.fanin} dependents)")
            if item.distance > 1:
                print(f"      via {' <- '.join(reversed(item.path))}")
        print()

    elif args.command == "deps":
        results = graph.dependencies_of(target, max_depth=args.depth)
        if not results:
            print(f"{target} depends on nothing local.")
            return
        print(f"{target} depends on {len(results)} symbol(s):\n")
        for item in results:
            print(f"   {item.symbol}  ({item.node_type})")
        print()


if __name__ == "__main__":
    main()
