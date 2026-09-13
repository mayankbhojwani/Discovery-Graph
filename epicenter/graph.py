"""
Epicenter: impact analysis over a parsed codebase graph.

Name a symbol — the epicenter — and this reports everything that shakes.
The question a developer actually asks before editing something:
"if I change this, what breaks?"

The core distinction this module makes is between *dependency* edges and
*structural* edges. An edge `A --calls--> B` means A depends on B, so a change
to B propagates back to A. An edge `module --contains--> class` means no such
thing: containment describes where code lives, not what relies on what.
Mixing the two (as a single combined DiGraph does) makes reachability leak
through containment until every symbol appears to depend on every other.
"""

import networkx as nx
from .database import fetch_graph_data

# Edges along which a change propagates, mapped to how strongly it does so.
# Reading `A --edge--> B` as "A depends on B", a change to B reaches A.
DEPENDENCY_EDGES = {
    "calls": 1.0,
    "inherits": 1.0,
    # A function handed to something else — a callback, a dispatch table
    # entry — is a real dependency: change its signature and the code passing
    # it around breaks.
    "references": 0.8,
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

    def __init__(self, db_path="epicenter.db", realm=None, include_external=False):
        self.db_path = db_path
        self.realm = realm
        self.include_external = include_external

        self.deps = nx.DiGraph()
        self.contains = nx.DiGraph()
        self.node_types = {}
        self.summaries = {}
        self.roles = {}
        self.subclasses = {}    # base class -> classes directly inheriting it

        self._covered = None      # lazily computed, see covered_symbols()
        self._cochange = None     # lazily loaded, see _load_cochange()
        self._symbol_commits = {}

        self._load()

    # ─── Role sets ──────────────────────────────────────────────────────────

    @property
    def dispatched_method_names(self):
        """
        Method names appearing in calls whose receiver could not be typed —
        `C.solve()` where C came out of a registry dict.

        Used only to hold such methods off the dead list, never to create an
        edge: the call is real but its destination is genuinely unknown, and
        inventing a dependency would corrupt impact analysis to tidy up a
        different report.
        """
        return {
            title.rsplit(".", 1)[-1]
            for title, kind in self.node_types.items()
            if kind == "unresolved" and "." in title
        }

    @property
    def tests(self):
        return {s for s, r in self.roles.items() if "test" in r}

    @property
    def entrypoints(self):
        return {s for s, r in self.roles.items() if "entrypoint" in r}

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
            raw_roles = node.get("roles") or ""
            self.roles[title] = {r for r in raw_roles.split(",") if r}

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

            if etype == "inherits":
                # Indexed separately so overrides can be found: calling a base
                # method may execute any subclass's version of it.
                self.subclasses.setdefault(tgt, set()).add(src)

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

    # ─── Coverage and reachability ──────────────────────────────────────────

    def _reachable_from(self, seeds):
        """Everything the given symbols can reach by following dependencies
        forwards. Multi-source, so the whole set costs one traversal."""
        seen = {s for s in seeds if s in self.deps}
        queue = list(seen)
        while queue:
            node = queue.pop()
            for dep in self.deps.successors(node):
                if dep not in seen:
                    seen.add(dep)
                    queue.append(dep)
        return seen

    def covered_symbols(self):
        """Symbols some test can reach. This is reachability, not line
        coverage — it says a test exercises a path to this code, not that it
        asserts anything useful about it."""
        if self._covered is None:
            self._covered = self._reachable_from(self.tests)
        return self._covered

    def is_covered(self, symbol):
        return symbol in self.covered_symbols()

    def tests_covering(self, symbol):
        """
        The specific tests whose dependencies reach `symbol`.

        Test modules carry the test role too, since they serve as reachability
        roots, but naming a module as one of the tests covering a symbol is
        noise — only the callable tests are reported.
        """
        if symbol not in self.deps:
            return []
        tests = self.tests
        return sorted(
            item.symbol
            for item in self.impact_of(symbol, max_depth=None)
            if item.symbol in tests and self.node_types.get(item.symbol) != "module"
        )

    def _parent_of(self, symbol):
        parents = list(self.contains.predecessors(symbol)) if symbol in self.contains else []
        return parents[0] if parents else None

    def script_modules(self):
        """
        Modules nothing imports, yet which have module-level dependencies of
        their own — they exist to be executed directly. Streamlit apps and
        plain scripts qualify without ever writing a `__main__` guard, and
        treating them as roots keeps everything below them off the dead list.
        """
        roots = set()
        for symbol in self.deps.nodes():
            if self.node_types.get(symbol) != "module":
                continue
            if self.deps.in_degree(symbol) == 0 and self.deps.out_degree(symbol) > 0:
                roots.add(symbol)
        return roots

    def reachability_roots(self):
        return self.entrypoints | self.tests | self.script_modules()

    def _framework_invoked(self, symbol):
        """
        True when something outside the codebase may call this without leaving
        a call edge behind. These are the cases static analysis cannot see, so
        they are excluded from the dead list rather than reported wrongly.
        """
        roles = self.roles.get(symbol, set())
        # Properties and other descriptors are reached by attribute access.
        if "implicit" in roles:
            return True

        leaf = symbol.split(".")[-1]
        parent = self._parent_of(symbol)

        # Dunders are invoked by the interpreter: `Foo()` yields an edge to
        # Foo, never to Foo.__init__.
        if leaf.startswith("__") and leaf.endswith("__"):
            return True

        # A method of a class whose base lies outside this codebase may be an
        # override the base calls itself.
        if parent and "external_base" in self.roles.get(parent, set()):
            return True

        # A closure defined inside a live function is typically returned or
        # passed somewhere, and the call that eventually runs it is not
        # visible statically. pytest fixtures returning inner builders are the
        # everyday case.
        if parent and self.node_types.get(parent) in {"function", "method"}:
            return True

        return False

    def live_symbols(self):
        """
        Everything reachable from the roots, computed to a fixpoint.

        One pass is not enough. A live class pulls in its framework-invoked
        members — `Foo()` links to Foo, not Foo.__init__ — and those members
        call further code, which may make yet more classes live. Iterating
        until nothing new appears is what keeps a constructor's callees off
        the dead list.
        """
        live = set()
        frontier = set(self.reachability_roots())

        while frontier:
            discovered = (frontier | self._reachable_from(frontier)) - live
            if not discovered:
                break
            live |= discovered

            dispatched = self.dispatched_method_names
            implicit = set()
            for symbol in discovered:
                if symbol in self.contains:
                    for child in self.contains.successors(symbol):
                        if child not in live:
                            # A method on a live class whose name is called
                            # somewhere on a receiver that could not be typed.
                            # Treated as live rather than merely hidden from
                            # the report, so whatever it calls is reached too.
                            if (
                                self._framework_invoked(child)
                                or (
                                    self.node_types.get(symbol) == "class"
                                    and child.rsplit(".", 1)[-1] in dispatched
                                )
                            ):
                                implicit.add(child)
                implicit |= self._overrides_of(symbol) - live
            frontier = implicit

        return live

    def _overrides_of(self, symbol):
        """
        Subclass versions of a method that just became live.

        `self.init_solver(L)` in a base __init__ resolves to the base's own
        method, but the instance is usually a subclass and the subclass's
        override is what actually runs. Walks the inheritance tree downwards,
        so overrides of overrides are found too.
        """
        parent = self._parent_of(symbol)
        if parent is None or self.node_types.get(parent) != "class":
            return set()

        leaf = symbol.rsplit(".", 1)[-1]
        found = set()
        pending = list(self.subclasses.get(parent, ()))
        seen = set()

        while pending:
            sub = pending.pop()
            if sub in seen:
                continue
            seen.add(sub)
            candidate = f"{sub}.{leaf}"
            if candidate in self.deps:
                found.add(candidate)
            pending.extend(self.subclasses.get(sub, ()))

        return found

    def unreachable(self):
        """
        Symbols no entrypoint, test, or script module can reach — dead code
        candidates.

        Candidates, not conclusions. Call resolution under-reports, so an
        unreferenced symbol may simply be one whose caller could not be
        resolved. Treat this as a list to review, never to delete from.
        """
        live = self.live_symbols()

        dead = []
        for symbol in self.deps.nodes():
            if symbol in live:
                continue
            if self.node_types.get(symbol) == "module":
                continue  # modules are containers, judged by their contents
            if self._framework_invoked(symbol):
                continue
            dead.append(symbol)

        return sorted(dead)

    # ─── Change coupling ────────────────────────────────────────────────────

    def _load_cochange(self):
        if self._cochange is None:
            from .database import fetch_cochange_data
            self._cochange, self._symbol_commits = fetch_cochange_data(
                self.db_path, self.realm
            )
        return self._cochange

    @property
    def has_history(self):
        return bool(self._load_cochange())

    def coupled_with(self, symbol, min_together=2, min_confidence=0.3):
        """
        Symbols that historically change alongside `symbol`.

        Reported as confidence — of the commits touching `symbol`, the share
        that also touched the other. A raw count alone flatters whatever
        changes most often, so both a floor on the count and on the share are
        applied.

        This is correlation drawn from history, not a dependency. It catches
        real coupling with no code path between the two ends — a config key
        and its reader, an encoder and its decoder — and it will also happily
        pair things that merely moved through the same commits.
        """
        pairs = self._load_cochange()
        own_commits = self._symbol_commits.get(symbol, 0)
        if not own_commits:
            return []

        results = []
        for a, b, together in pairs:
            if a == symbol:
                other = b
            elif b == symbol:
                other = a
            else:
                continue
            if together < min_together:
                continue
            confidence = together / own_commits
            if confidence < min_confidence:
                continue
            results.append({
                "symbol": other,
                "together": together,
                "confidence": confidence,
                "of_commits": own_commits,
                # Coupling that structure already explains is far less
                # interesting than coupling it cannot.
                "structural": self.deps.has_edge(symbol, other)
                or self.deps.has_edge(other, symbol),
            })

        results.sort(key=lambda r: (-r["confidence"], -r["together"], r["symbol"]))
        return results

    def stats(self):
        local = [s for s in self.deps.nodes() if self.node_types.get(s) != "module"]
        return {
            "realm": self.realm,
            "symbols": self.deps.number_of_nodes(),
            "dependency_edges": self.deps.number_of_edges(),
            "containment_edges": self.contains.number_of_edges(),
            "entrypoints": len(self.entrypoints),
            "tests": len(self.tests),
            "covered_by_tests": sum(1 for s in local if self.is_covered(s)),
            "unreachable": len(self.unreachable()),
            # How many call sites the parser could not tie to a symbol. The
            # honest measure of how much of the graph is missing.
            "unresolved_calls": sum(
                1 for t in self.node_types.values() if t == "unresolved"
            ),
        }
