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


def test_return_annotation_types_the_variable(parsed):
    """`trace = get_current_trace()` is only resolvable by reading the
    getter's return annotation."""
    nodes, edges = parsed({
        "obs.py": """
            from typing import Optional

            class TraceManager:
                def log(self, msg): ...

            def get_current_trace() -> Optional[TraceManager]:
                return None
        """,
        "svc.py": """
            from obs import get_current_trace

            def work():
                trace = get_current_trace()
                trace.log("hello")
        """,
    })
    assert ("svc.work", "obs.TraceManager.log") in call_edges(edges)


def test_function_call_is_not_mistaken_for_a_constructor(parsed):
    """Typing the variable as the *function* makes every method on it
    unresolvable, so a call is only a constructor when it names a class."""
    nodes, edges = parsed({
        "obs.py": """
            def make_thing():
                return None
        """,
        "svc.py": """
            from obs import make_thing

            def work():
                thing = make_thing()
                thing.run()
        """,
    })
    assert ("svc.work", "obs.make_thing.run") not in call_edges(edges)


def test_class_qualified_call_resolves(parsed):
    nodes, edges = parsed({
        "mod.py": """
            class Orchestrator:
                @staticmethod
                def detect(msg): ...

                def process(self, msg):
                    Orchestrator.detect(msg)
        """,
    })
    assert ("mod.Orchestrator.process", "mod.Orchestrator.detect") in call_edges(edges)


def test_function_passed_as_callback_is_a_reference(parsed):
    """`render(handle_login)` never calls handle_login, but changing it still
    breaks the caller - and without this every callback reads as dead."""
    nodes, edges = parsed({
        "ui.py": """
            def render(callback): ...

            def handle_login(): ...

            def setup():
                render(handle_login)
        """,
    })
    refs = {(e["source"], e["target"]) for e in edges if e["edge_type"] == "references"}
    assert ("ui.setup", "ui.handle_login") in refs


def test_bound_method_passed_as_argument_is_a_reference(parsed):
    """How agent tools and signal handlers get registered."""
    nodes, edges = parsed({
        "tools.py": """
            class AgentTools:
                def authenticate(self): ...

            class Manager:
                def __init__(self):
                    self.tools = AgentTools()

                def wire(self, register):
                    register(fn=self.tools.authenticate)
        """,
    })
    refs = {(e["source"], e["target"]) for e in edges if e["edge_type"] == "references"}
    assert ("tools.Manager.wire", "tools.AgentTools.authenticate") in refs


def test_ordinary_variables_do_not_become_references(parsed):
    """Every name passes through the reference visitor; only ones resolving to
    real local symbols may produce edges."""
    nodes, edges = parsed({
        "mod.py": """
            def work(payload):
                total = payload
                return total
        """,
    })
    refs = [e for e in edges if e["edge_type"] == "references"]
    assert refs == []


def test_pep604_union_annotation(parsed):
    """`Cache | None` is the modern spelling of Optional[Cache] and parses as
    a BinOp rather than a Subscript. Typed code uses it everywhere."""
    nodes, edges = parsed({
        "store.py": """
            class Cache:
                def read(self, k): ...
        """,
        "svc.py": """
            from store import Cache

            def work(cache: Cache | None, k):
                cache.read(k)
        """,
    })
    assert ("svc.work", "store.Cache.read") in call_edges(edges)


def test_class_body_annotation_types_the_attribute(parsed):
    """Dataclasses, pydantic models and attrs classes declare their state as
    class-body annotations and never write `self.x = ...` at all."""
    nodes, edges = parsed({
        "store.py": """
            class Cache:
                def read(self, k): ...
        """,
        "svc.py": """
            from store import Cache

            class Client:
                cache: Cache

                def fetch(self, k):
                    self.cache.read(k)
        """,
    })
    assert ("svc.Client.fetch", "store.Cache.read") in call_edges(edges)


def test_attribute_read_into_a_local_keeps_its_type(parsed):
    """`cache = self.cache` - the type is known, and must survive the hop
    through a local or every call on it goes unresolved."""
    nodes, edges = parsed({
        "store.py": """
            class Cache:
                def read(self, k): ...
        """,
        "svc.py": """
            from store import Cache

            class Client:
                cache: Cache | None = None

                def fetch(self, k):
                    cache = self.cache
                    return cache.read(k)
        """,
    })
    assert ("svc.Client.fetch", "store.Cache.read") in call_edges(edges)


def test_async_methods_and_awaited_calls_resolve(parsed):
    """Async code was never exercised until an async-heavy codebase was
    analysed; `await x.method()` must resolve like any other call."""
    nodes, edges = parsed({
        "store.py": """
            class Cache:
                async def read(self, k): ...
        """,
        "svc.py": """
            from store import Cache

            class Client:
                def __init__(self):
                    self.cache = Cache()

                async def fetch(self, k):
                    return await self.cache.read(k)
        """,
    })
    assert ("svc.Client.fetch", "store.Cache.read") in call_edges(edges)
    assert "svc.Client.fetch" in {n["title"] for n in nodes}


def test_calling_the_instance_itself_does_not_crash(parsed):
    """`self(...)` runs the class's __call__. It once raised IndexError deep
    in resolve_call, and the exception was caught per-file - so every symbol
    in any file containing this pattern vanished from the graph silently."""
    nodes, edges = parsed({
        "mod.py": """
            class Handler:
                def __call__(self, x): ...

                def run(self, x):
                    return self(x)
        """,
    })
    titles = {n["title"] for n in nodes}
    assert "mod.Handler.run" in titles
    assert "mod.Handler.__call__" in titles
    assert ("mod.Handler.run", "mod.Handler") in call_edges(edges)


def test_a_file_that_fails_to_parse_is_reported(parsed, project):
    """A dropped file takes all its symbols with it, so the failure must be
    visible rather than swallowed."""
    from epicenter.pipeline import parse_repository

    root = project({
        "good.py": "def works(): ...\n",
        "broken.py": "def oops(:\n",
    })
    nodes, _ = parse_repository(str(root))

    # A syntax error trips both passes, so the file appears once per pass.
    failed_files = {path for path, _phase, _message in parse_repository.last_failures}
    assert len(failed_files) == 1
    assert "broken.py" in failed_files.pop()
    assert "good.works" in {n["title"] for n in nodes}


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
