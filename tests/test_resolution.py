"""Call resolution: turning `db.save()` into the symbol it actually reaches."""

from tests.conftest import call_edges

STORE = """
    class Database:
        def save(self, row): ...
        def close(self): ...
"""


def test_resolves_self_attribute_assigned_in_init(parsed):
    nodes, edges = parsed({
        "store.py": STORE,
        "svc.py": """
            from store import Database

            class Service:
                def __init__(self):
                    self.db = Database()

                def run(self, row):
                    self.db.save(row)
        """,
    })
    assert ("svc.Service.run", "store.Database.save") in call_edges(edges)


def test_resolves_self_attribute_used_before_init_is_defined(parsed):
    """A method may appear above the __init__ that creates what it uses, so
    attribute types cannot be learned in traversal order alone."""
    nodes, edges = parsed({
        "store.py": STORE,
        "svc.py": """
            from store import Database

            class Service:
                def run(self, row):
                    self.db.save(row)

                def __init__(self):
                    self.db = Database()
        """,
    })
    assert ("svc.Service.run", "store.Database.save") in call_edges(edges)


def test_resolves_local_variable(parsed):
    nodes, edges = parsed({
        "store.py": STORE,
        "svc.py": """
            from store import Database

            def handler(row):
                local = Database()
                local.save(row)
        """,
    })
    assert ("svc.handler", "store.Database.save") in call_edges(edges)


def test_resolves_annotated_parameter(parsed):
    nodes, edges = parsed({
        "store.py": STORE,
        "svc.py": """
            from store import Database

            def handler(db: Database, row):
                db.save(row)
        """,
    })
    assert ("svc.handler", "store.Database.save") in call_edges(edges)


def test_resolves_optional_annotation(parsed):
    nodes, edges = parsed({
        "store.py": STORE,
        "svc.py": """
            from typing import Optional
            from store import Database

            def handler(db: Optional[Database], row):
                db.save(row)
        """,
    })
    assert ("svc.handler", "store.Database.save") in call_edges(edges)


def test_unresolvable_call_is_marked_unresolved_not_external(parsed):
    """`mystery.save()` on an unannotated parameter cannot be tied to a real
    symbol. Filing it as an external library would claim knowledge we do not
    have and hide the parser's blind spot; it is recorded as unresolved so the
    gap stays countable."""
    nodes, edges = parsed({
        "svc.py": """
            def handler(mystery):
                mystery.save(1)
        """,
    })
    node = next(n for n in nodes if n["title"] == "mystery.save")
    assert node["node_type"] == "unresolved"


def test_unresolved_targets_stay_out_of_the_dependency_graph(graph):
    """They must never be mistaken for real dependencies."""
    g = graph({
        "svc.py": """
            def handler(mystery):
                mystery.save(1)
        """,
    })
    assert "mystery.save" not in g.deps


def test_module_level_calls_attributed_to_module(parsed):
    """Script-style files - Streamlit apps, main.py - put nearly all their
    logic at module level. Skipping those calls makes the file look inert."""
    nodes, edges = parsed({
        "store.py": STORE,
        "script.py": """
            from store import Database

            db = Database()
            db.save(1)
        """,
    })
    assert ("script", "store.Database.save") in call_edges(edges)


def test_recursion_does_not_create_a_self_loop(parsed):
    nodes, edges = parsed({
        "walk.py": """
            def descend(n):
                if n:
                    descend(n - 1)
        """,
    })
    assert ("walk.descend", "walk.descend") not in call_edges(edges)


def test_nested_functions_are_qualified_by_their_enclosing_function(parsed):
    """Two closures with the same name in one class are different functions.
    Naming them after the class collapses them into a single node and merges
    their callers."""
    nodes, _ = parsed({
        "mod.py": """
            class Factory:
                def alpha(self):
                    def build(): ...
                    return build

                def beta(self):
                    def build(): ...
                    return build
        """,
    })
    titles = {n["title"] for n in nodes}
    assert "mod.Factory.alpha.build" in titles
    assert "mod.Factory.beta.build" in titles


def test_closure_called_by_bare_name_resolves_to_the_closure(parsed):
    nodes, edges = parsed({
        "mod.py": """
            def outer(items):
                def walk(node): ...
                walk(items)
        """,
    })
    assert ("mod.outer", "mod.outer.walk") in call_edges(edges)


def test_recursive_closure_resolves_to_itself_without_an_edge(parsed):
    """The name must resolve to the closure rather than a phantom module
    symbol, while the self-loop itself is still dropped."""
    nodes, edges = parsed({
        "mod.py": """
            def outer(items):
                def walk(node):
                    walk(node)
                walk(items)
        """,
    })
    titles = {n["title"] for n in nodes}
    assert "mod.walk" not in titles
    assert ("mod.outer.walk", "mod.outer.walk") not in call_edges(edges)


def test_same_class_method_call(parsed):
    nodes, edges = parsed({
        "svc.py": """
            class Service:
                def run(self):
                    self.helper()

                def helper(self): ...
        """,
    })
    assert ("svc.Service.run", "svc.Service.helper") in call_edges(edges)
