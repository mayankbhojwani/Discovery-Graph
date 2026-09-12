"""Impact queries: what breaks, and the chain of blame that explains why."""

CHAIN = {
    "store.py": """
        def save(row): ...
    """,
    "api.py": """
        from store import save

        def create(row):
            save(row)
    """,
    "web.py": """
        from api import create

        def signup(row):
            create(row)
    """,
}


def symbols(results):
    return {r.symbol for r in results}


def test_finds_direct_and_indirect_callers(graph):
    g = graph(CHAIN)
    found = symbols(g.impact_of("store.save"))
    assert "api.create" in found
    assert "web.signup" in found


def test_distance_reflects_hops(graph):
    g = graph(CHAIN)
    by_symbol = {r.symbol: r.distance for r in g.impact_of("store.save")}
    assert by_symbol["api.create"] == 1
    assert by_symbol["web.signup"] == 2


def test_path_records_chain_of_blame(graph):
    g = graph(CHAIN)
    signup = next(r for r in g.impact_of("store.save") if r.symbol == "web.signup")
    assert signup.path == ["store.save", "api.create", "web.signup"]


def test_max_depth_limits_traversal(graph):
    g = graph(CHAIN)
    found = symbols(g.impact_of("store.save", max_depth=1))
    assert "api.create" in found
    assert "web.signup" not in found


def test_containment_does_not_propagate_impact(graph):
    """The core invariant. Two functions in one module do not depend on each
    other merely by sharing a file - if containment edges were left in the
    dependency graph, reachability would leak through the module and connect
    everything to everything."""
    g = graph({
        "mod.py": """
            def alpha(): ...

            def beta(): ...
        """,
    })
    assert "mod.beta" not in symbols(g.impact_of("mod.alpha"))


def test_changing_a_class_implicates_callers_of_its_methods(graph):
    g = graph({
        "store.py": """
            class Database:
                def save(self, row): ...
        """,
        "api.py": """
            from store import Database

            def create(row):
                db = Database()
                db.save(row)
        """,
    })
    assert "api.create" in symbols(g.impact_of("store.Database"))


def test_unreferenced_symbol_has_no_impact(graph):
    g = graph({"mod.py": "def lonely(): ...\n"})
    assert g.impact_of("mod.lonely") == []


def test_dependencies_are_the_inverse_direction(graph):
    g = graph(CHAIN)
    deps = {r.symbol for r in g.dependencies_of("api.create")}
    assert "store.save" in deps
    assert "web.signup" not in deps


def test_find_symbol_prefers_exact_leaf_match(graph):
    g = graph({
        "mod.py": """
            def save(): ...

            def save_all(): ...
        """,
    })
    assert g.find_symbol("save")[0] == "mod.save"
