"""
Dynamic dispatch: the cases where a call's destination is decided at runtime.

Static analysis cannot follow these, so the question is not "which symbol does
this reach" but "could it reach here at all" - and reporting live code as dead
is the more damaging error.
"""

from tests.conftest import roles_of

REGISTRY = {
    "solvers.py": """
        class BaseSolver:
            def solve(self, x): ...
            def teardown(self): ...

        class FastSolver(BaseSolver):
            def solve(self, x): ...

        class SlowSolver(BaseSolver):
            def solve(self, x): ...
    """,
    "run.py": """
        from solvers import BaseSolver, FastSolver, SlowSolver

        def main():
            registry = {"fast": FastSolver, "slow": SlowSolver}
            chosen = registry["fast"](1)
            chosen.solve(2)

        if __name__ == "__main__":
            main()
    """,
}


def test_registry_selected_method_is_not_dead(graph):
    """`registry["fast"](...).solve()` - the receiver's type comes out of a
    dict, so the call cannot be resolved, but it plainly reaches a solver."""
    dead = graph(REGISTRY).unreachable()
    assert "solvers.BaseSolver.solve" not in dead


def test_subclass_overrides_of_a_live_method_are_not_dead(graph):
    """Calling a base method runs whichever override the instance has."""
    dead = graph(REGISTRY).unreachable()
    assert "solvers.FastSolver.solve" not in dead
    assert "solvers.SlowSolver.solve" not in dead


def test_unrelated_method_on_a_live_class_is_still_dead(graph):
    """The suppression is keyed on the method *name* being dispatched
    somewhere. A name nothing calls stays reportable, or the whole feature
    would collapse into never flagging anything."""
    assert "solvers.BaseSolver.teardown" in graph(REGISTRY).unreachable()


def test_method_called_on_a_subscript_receiver_is_not_dead(graph):
    """`graph[node].iter_neighbors()` - get_full_attr_name once returned None
    for a subscript, so the call was not even recorded as unresolved."""
    g = graph({
        "nodes.py": """
            class Node:
                def iter_neighbors(self): ...
        """,
        "run.py": """
            from nodes import Node

            def main(lookup):
                lookup[0].iter_neighbors()

            if __name__ == "__main__":
                main({})
        """,
    })
    assert "nodes.Node.iter_neighbors" not in g.unreachable()


def test_same_module_inheritance_is_resolved(parsed):
    """The base class edge was built from the import map alone, so a base in
    the same module produced an edge to a bare name matching no symbol."""
    nodes, edges = parsed({
        "solvers.py": """
            class Base:
                def run(self): ...

            class Child(Base):
                def run(self): ...
        """,
    })
    inherits = {(e["source"], e["target"]) for e in edges if e["edge_type"] == "inherits"}
    assert ("solvers.Child", "solvers.Base") in inherits
    assert "Base" not in {n["title"] for n in nodes}


def test_pytest_hooks_are_entrypoints(parsed):
    """pytest finds these by name and calls them itself."""
    nodes, _ = parsed({
        "conftest.py": """
            def pytest_configure(config): ...
        """,
    })
    assert "entrypoint" in roles_of(nodes, "conftest.pytest_configure")


def test_public_methods_of_exported_classes_are_public(parsed):
    nodes, _ = parsed({
        "pkg/__init__.py": "from .api import Engine\n",
        "pkg/api.py": """
            class Engine:
                def run(self): ...
                def _internal(self): ...
        """,
    })
    assert "entrypoint" in roles_of(nodes, "pkg.api.Engine.run")
    assert "entrypoint" not in roles_of(nodes, "pkg.api.Engine._internal")
