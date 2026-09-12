"""
Roles, coverage, and reachability.

Most of these guard against a framework calling code with no call edge to
show for it - the failure mode that made the first dead-code run report 46
symbols, nearly all of them alive.
"""

from tests.conftest import roles_of


def test_main_guard_makes_module_an_entrypoint(parsed):
    nodes, _ = parsed({
        "cli.py": """
            def main(): ...

            if __name__ == "__main__":
                main()
        """,
    })
    assert "entrypoint" in roles_of(nodes, "cli")


def test_registering_decorator_is_an_entrypoint(parsed):
    nodes, _ = parsed({
        "web.py": """
            app = object()

            @app.route("/health")
            def health(): ...
        """,
    })
    assert "entrypoint" in roles_of(nodes, "web.health")


def test_inert_decorator_is_not_an_entrypoint(parsed):
    nodes, _ = parsed({
        "util.py": """
            from functools import lru_cache

            @lru_cache
            def compute(): ...
        """,
    })
    assert "entrypoint" not in roles_of(nodes, "util.compute")


def test_property_is_marked_implicit(parsed):
    nodes, _ = parsed({
        "mod.py": """
            class Thing:
                @property
                def name(self): ...
        """,
    })
    assert "implicit" in roles_of(nodes, "mod.Thing.name")


def test_external_base_class_is_flagged(parsed):
    """A base defined outside the codebase hides its contract, so any method
    here may be an override the framework invokes."""
    nodes, _ = parsed({
        "visit.py": """
            import ast

            class Walker(ast.NodeVisitor):
                def visit_Call(self, node): ...
        """,
    })
    assert "external_base" in roles_of(nodes, "visit.Walker")


def test_tests_detected_in_test_modules(parsed):
    nodes, _ = parsed({
        "tests/test_thing.py": """
            def test_works(): ...

            class TestThing:
                def test_roundtrip(self): ...
        """,
    })
    assert "test" in roles_of(nodes, "tests.test_thing.test_works")
    assert "test" in roles_of(nodes, "tests.test_thing.TestThing.test_roundtrip")


def test_test_prefixed_function_outside_a_test_module_is_not_a_test(parsed):
    """Regression: a tool function named test_coverage was classified as a
    test, which made everything it touched report as covered when nothing
    tested it at all."""
    nodes, _ = parsed({
        "server.py": """
            def test_coverage(symbol): ...
        """,
    })
    assert "test" not in roles_of(nodes, "server.test_coverage")


# ─── Reachability ───────────────────────────────────────────────────────────

APP = {
    "core.py": """
        class Database:
            def save(self, row): ...
            def orphaned(self): ...

        def never_used(): ...
    """,
    "cli.py": """
        from core import Database

        def main():
            db = Database()
            db.save(1)

        if __name__ == "__main__":
            main()
    """,
    "tests/test_core.py": """
        from core import Database

        def test_save():
            db = Database()
            db.save(1)
    """,
}


def test_dead_code_finds_unreferenced_symbols(graph):
    dead = graph(APP).unreachable()
    assert "core.Database.orphaned" in dead
    assert "core.never_used" in dead


def test_dead_code_spares_reachable_symbols(graph):
    dead = graph(APP).unreachable()
    assert "core.Database.save" not in dead
    assert "cli.main" not in dead


def test_constructor_callees_are_not_dead(graph):
    """Foo() links to Foo, never to Foo.__init__, so without a fixpoint the
    constructor stays dead and drags everything it calls down with it."""
    g = graph({
        "core.py": """
            class Engine:
                def __init__(self):
                    self.warm_up()

                def warm_up(self): ...
        """,
        "cli.py": """
            from core import Engine

            def main():
                Engine()

            if __name__ == "__main__":
                main()
        """,
    })
    assert "core.Engine.warm_up" not in g.unreachable()


def test_script_module_counts_as_a_root(graph):
    """A Streamlit app has no __main__ guard; nothing imports it either. If it
    is not treated as a root, everything it calls looks dead."""
    g = graph({
        "helpers.py": "def render(): ...\n",
        "dashboard.py": """
            from helpers import render

            render()
        """,
    })
    assert "helpers.render" not in g.unreachable()


def test_framework_invoked_methods_are_not_dead(graph):
    g = graph({
        "visit.py": """
            import ast

            class Walker(ast.NodeVisitor):
                def visit_Call(self, node): ...
        """,
        "cli.py": """
            from visit import Walker

            def main():
                Walker()

            if __name__ == "__main__":
                main()
        """,
    })
    assert "visit.Walker.visit_Call" not in g.unreachable()


def test_closures_inside_live_functions_are_not_dead(graph):
    """A closure is returned or passed, and the call that eventually runs it
    is invisible statically - a pytest fixture returning an inner builder is
    the everyday case."""
    g = graph({
        "factory.py": """
            def make():
                def build(): ...
                return build
        """,
        "cli.py": """
            from factory import make

            def main():
                make()

            if __name__ == "__main__":
                main()
        """,
    })
    assert "factory.make.build" not in g.unreachable()


def test_coverage_names_the_tests_that_reach_a_symbol(graph):
    g = graph(APP)
    assert g.tests_covering("core.Database.save") == ["tests.test_core.test_save"]


def test_uncovered_symbol_reports_no_tests(graph):
    g = graph(APP)
    assert g.tests_covering("core.Database.orphaned") == []
    assert not g.is_covered("core.Database.orphaned")
