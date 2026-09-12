import os
import ast
import builtins
from database import save_code_graph_to_db

# Extract standard Python built-in names
BUILTIN_NAMES = set(dir(builtins))

# Decorators that only modify a function in place, rather than handing it to
# something that will call it later. Everything NOT on this list is treated as
# registration — `@app.route`, `@mcp.tool`, `@pytest.fixture`, `@celery.task`
# and every framework's equivalent all mean "something outside this codebase
# holds a reference to this function and will invoke it". Enumerating inert
# decorators is tractable; enumerating every framework's registering ones is
# not.
INERT_DECORATORS = {
    "staticmethod", "classmethod", "abstractmethod", "abstractproperty",
    "override", "overload", "final", "wraps", "lru_cache", "cache",
    "dataclass", "total_ordering", "contextmanager", "asynccontextmanager",
    "singledispatch", "singledispatchmethod", "runtime_checkable",
}

# Decorators making a function reachable by attribute access rather than a
# call, so no call edge will ever point at it.
DESCRIPTOR_DECORATORS = {
    "property", "cached_property", "setter", "getter", "deleter",
}

# Names that conventionally mean "this is where execution starts". Applied
# only to module-level functions: `run` as a method is far too common to treat
# as an entrypoint.
ENTRYPOINT_FUNCTION_NAMES = {"main", "cli"}

class DefinitionVisitor(ast.NodeVisitor):
    """
    Pass 1 Visitor: Extracts all local symbols (classes, methods, functions)
    defined within a module to build the codebase symbol table.
    """
    def __init__(self, module_name):
        self.module_name = module_name
        self.current_class = None
        self.current_function = None
        self.symbols = set()

    def visit_ClassDef(self, node):
        class_fqn = f"{self.module_name}.{node.name}"
        self.symbols.add(class_fqn)

        old_class = self.current_class
        self.current_class = class_fqn
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        self.visit_any_function(node)

    def visit_AsyncFunctionDef(self, node):
        self.visit_any_function(node)

    def visit_any_function(self, node):
        # Nested functions are qualified by the function enclosing them.
        # Naming them after the enclosing class instead collapses every
        # same-named closure in that class into one symbol.
        parent = self.current_function or self.current_class or self.module_name
        func_name = f"{parent}.{node.name}"
        self.symbols.add(func_name)

        old_func = self.current_function
        self.current_function = func_name
        self.generic_visit(node)
        self.current_function = old_func

class CodeASTVisitor(ast.NodeVisitor):
    """
    Pass 2 Visitor: Maps structural relationships (calls, containment, imports, inherits)
    and classifies nodes against the codebase symbol table.
    """
    def __init__(self, module_name, local_symbols):
        self.module_name = module_name
        self.local_symbols = local_symbols
        self.current_class = None
        self.current_function = None

        self.nodes = [] # List of dicts: {"title": ..., "summary": ..., "node_type": ...}
        self.edges = [] # List of dicts: {"source": ..., "target": ..., "edge_type": ...}

        self.imports = {}
        self.star_imports = []

        # ─── Local type environment ───
        # Without knowing what a variable holds, `db = Database()` followed by
        # `db.save()` yields no usable edge, which is most real Python. These
        # track the little that can be inferred from constructor calls and
        # annotations, which covers the common cases without a type checker.
        self.scope_stack = [{}]          # stack of {variable name: type FQN}
        self.class_attrs = {}            # class FQN -> {attribute name: type FQN}

        # ─── Roles ───
        # Which symbols are tests, and which are reachable from outside the
        # codebase. Together these give the graph its roots: anything no test
        # and no entrypoint can reach is a dead-code candidate.
        self.module_roles = set()
        self.is_test_module = self._looks_like_test_module(module_name)

        # Call targets this visitor could not tie to any known symbol.
        self.unresolved = set()

    @staticmethod
    def _looks_like_test_module(module_name):
        leaf = module_name.split(".")[-1]
        return (
            leaf.startswith("test_")
            or leaf.endswith("_test")
            or "tests" in module_name.split(".")
            or leaf == "conftest"
        )

    def decorator_names(self, node):
        """Final attribute of each decorator, e.g. `app.route` -> 'route'."""
        names = []
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            full = self.get_full_attr_name(target)
            if full:
                names.append(full.split(".")[-1])
        return names

    def function_roles(self, node, name, is_method):
        """Classifies a function as test and/or entrypoint."""
        roles = set()
        decorators = self.decorator_names(node)

        # Name-based detection is confined to test modules, matching what a
        # runner actually collects. Without that guard any ordinary function
        # named `test_coverage` is mistaken for a test, and its dependencies
        # are then reported as covered when nothing tests them at all.
        if self.is_test_module:
            if name.startswith("test"):
                roles.add("test")
            elif is_method and self.current_class and self.current_class.split(".")[-1].startswith("Test"):
                if name in {"setUp", "tearDown", "setup_method", "teardown_method"}:
                    roles.add("test")
        if "fixture" in decorators:
            roles.add("test")

        if any(d in DESCRIPTOR_DECORATORS for d in decorators):
            roles.add("implicit")
        elif any(d not in INERT_DECORATORS for d in decorators):
            # Decorated by something that is not purely a modifier, so a
            # framework is holding this function and will call it.
            roles.add("entrypoint")

        if not is_method and name in ENTRYPOINT_FUNCTION_NAMES:
            roles.add("entrypoint")

        return roles

    def visit_If(self, node):
        """Detects the `if __name__ == "__main__":` guard, which makes the
        enclosing module an execution entrypoint."""
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            self.module_roles.add("entrypoint")
        self.generic_visit(node)
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = alias.name
            self.edges.append({
                "source": self.module_name,
                "target": alias.name,
                "edge_type": "imports"
            })
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                self.star_imports.append(module)
                self.edges.append({
                    "source": self.module_name,
                    "target": module,
                    "edge_type": "imports"
                })
            else:
                name = alias.asname or alias.name
                target = f"{module}.{alias.name}" if module else alias.name
                self.imports[name] = target
                self.edges.append({
                    "source": self.module_name,
                    "target": target,
                    "edge_type": "imports"
                })
        self.generic_visit(node)
        
    def get_base_class_name(self, node):
        """Recursively resolves class inheritance parents."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val_str = self.get_base_class_name(node.value)
            if val_str:
                return f"{val_str}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return self.get_base_class_name(node.value)
        return None

    # ─── Type inference ─────────────────────────────────────────────────────

    def resolve_type_name(self, name):
        """
        Turns a type reference as written (`Database`, `nx.DiGraph`) into the
        fully-qualified name the graph uses. Returns None when the name cannot
        be tied to anything, so callers can skip recording a guess.
        """
        if not name:
            return None

        if name in self.imports:
            return self.imports[name]

        parts = name.split(".")
        if parts[0] in self.imports:
            return f"{self.imports[parts[0]]}.{'.'.join(parts[1:])}"

        # A class defined in this module.
        local_candidate = f"{self.module_name}.{name}"
        if local_candidate in self.local_symbols:
            return local_candidate

        if name in self.local_symbols:
            return name

        return None

    def infer_type(self, value):
        """Infers the type of an assigned expression, handling only the forms
        that are unambiguous: a constructor call, or a name already known to
        the local scope."""
        if isinstance(value, ast.Call):
            return self.resolve_type_name(self.get_full_attr_name(value.func))
        if isinstance(value, ast.Name):
            return self.lookup_variable(value.id)
        return None

    def annotation_type(self, annotation):
        """Resolves a type annotation, unwrapping subscripts so that
        `Optional[Database]` and `list[Database]` still name Database."""
        if annotation is None:
            return None
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            # Strings appear in forward references and `from __future__` files.
            return self.resolve_type_name(annotation.value)
        if isinstance(annotation, ast.Subscript):
            outer = self.get_full_attr_name(annotation.value)
            if outer and outer.split(".")[-1] in {"Optional", "List", "list", "Sequence", "Iterable", "Set", "set"}:
                inner = annotation.slice
                if isinstance(inner, ast.Tuple) and inner.elts:
                    inner = inner.elts[0]
                return self.annotation_type(inner)
            return self.resolve_type_name(outer)
        return self.resolve_type_name(self.get_full_attr_name(annotation))

    def lookup_variable(self, name):
        """Finds a variable's type in the innermost scope that defines it."""
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        return None

    def record_assignment(self, target, inferred):
        """Stores an inferred type against a simple name or a `self.attr`."""
        if inferred is None:
            return
        if isinstance(target, ast.Name):
            self.scope_stack[-1][target.id] = inferred
        elif (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and self.current_class
        ):
            self.class_attrs.setdefault(self.current_class, {})[target.attr] = inferred

    def visit_Assign(self, node):
        inferred = self.infer_type(node.value)
        if inferred:
            for target in node.targets:
                self.record_assignment(target, inferred)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        inferred = self.annotation_type(node.annotation) or self.infer_type(node.value)
        self.record_assignment(node.target, inferred)
        self.generic_visit(node)

    def collect_self_attributes(self, class_node):
        """
        Pre-scans a class body for `self.x = Thing()` before visiting its
        methods. A method that uses `self.x` may be defined above the
        `__init__` that creates it, so these cannot be learned in traversal
        order.
        """
        for child in ast.walk(class_node):
            if isinstance(child, ast.Assign):
                inferred = self.infer_type(child.value)
                targets = child.targets
            elif isinstance(child, ast.AnnAssign):
                inferred = self.annotation_type(child.annotation) or self.infer_type(child.value)
                targets = [child.target]
            else:
                continue

            if not inferred:
                continue
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    self.class_attrs.setdefault(self.current_class, {})[target.attr] = inferred

    def visit_ClassDef(self, node):
        class_name = f"{self.module_name}.{node.name}"
        bases = []
        for base in node.bases:
            base_name = self.get_base_class_name(base)
            if base_name:
                bases.append(base_name)
        
        summary = f"class {node.name}(" + ", ".join(bases) + "):"
        class_roles = set()
        if node.name.startswith("Test") or (self.is_test_module and node.name.endswith("Test")):
            class_roles.add("test")

        # A base class defined outside this codebase hides its own contract:
        # any method here may be an override the framework invokes, with no
        # call edge to show for it (ast.NodeVisitor dispatching to visit_Call
        # is the case in point). Recorded so reachability can allow for it.
        for base in bases:
            resolved = self.resolve_type_name(base)
            if resolved is None or resolved not in self.local_symbols:
                class_roles.add("external_base")
                break
        self.nodes.append({
            "title": class_name,
            "summary": summary,
            "node_type": "class",
            "roles": sorted(class_roles),
        })
        
        self.edges.append({
            "source": self.module_name,
            "target": class_name,
            "edge_type": "contains"
        })
        
        for base in bases:
            resolved_base = self.imports.get(base, base)
            self.edges.append({
                "source": class_name,
                "target": resolved_base,
                "edge_type": "inherits"
            })
            
        old_class = self.current_class
        self.current_class = class_name
        self.collect_self_attributes(node)
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        self.visit_any_function(node)
        
    def visit_AsyncFunctionDef(self, node):
        self.visit_any_function(node)
        
    def visit_any_function(self, node):
        if self.current_function:
            # A closure belongs to the function that defines it, not to the
            # enclosing class: two same-named closures in one class are
            # different functions and must not share a node.
            func_name = f"{self.current_function}.{node.name}"
            node_type = "function"
        elif self.current_class:
            func_name = f"{self.current_class}.{node.name}"
            node_type = "method"
        else:
            func_name = f"{self.module_name}.{node.name}"
            node_type = "function"
            
        args_list = [arg.arg for arg in node.args.args]
        summary = f"def {node.name}(" + ", ".join(args_list) + "):"

        roles = self.function_roles(node, node.name, is_method=bool(self.current_class))
        self.nodes.append({
            "title": func_name,
            "summary": summary,
            "node_type": node_type,
            "roles": sorted(roles),
        })
        
        parent = self.current_function or self.current_class or self.module_name
        self.edges.append({
            "source": parent,
            "target": func_name,
            "edge_type": "contains"
        })
        
        old_func = self.current_function
        self.current_function = func_name

        # Parameter annotations are the other reliable source of variable
        # types, and cost nothing to read.
        scope = {}
        for arg in list(node.args.args) + list(node.args.kwonlyargs):
            annotated = self.annotation_type(arg.annotation)
            if annotated:
                scope[arg.arg] = annotated
        self.scope_stack.append(scope)

        self.generic_visit(node)

        self.scope_stack.pop()
        self.current_function = old_func
        
    def get_full_attr_name(self, node):
        """Resolves nested attribute accesses (e.g. os.path.join)."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val_str = self.get_full_attr_name(node.value)
            if val_str:
                return f"{val_str}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self.get_full_attr_name(node.func)
        return None

    def visit_Call(self, node):
        # Calls made at module level belong to the module itself. Script-style
        # files — Streamlit apps, main.py, settings modules — put nearly all
        # their logic there, and skipping those calls makes such a file appear
        # to depend on nothing at all.
        caller = self.current_function or self.module_name

        called_name = self.get_full_attr_name(node.func)
        if called_name:
            resolved = self.resolve_call(called_name)
            if resolved and resolved != caller:
                self.edges.append({
                    "source": caller,
                    "target": resolved,
                    "edge_type": "calls"
                })

        self.generic_visit(node)
        
    def resolve_call(self, name):
        if name in self.imports:
            return self.imports[name]
        parts = name.split(".")
        if parts[0] in self.imports:
            resolved_module = self.imports[parts[0]]
            return f"{resolved_module}.{'.'.join(parts[1:])}"

        if parts[0] == "self" and self.current_class:
            if len(parts) == 2:
                return f"{self.current_class}.{parts[1]}"
            # `self.engine.run()` — resolve the attribute to its type first, so
            # the call lands on the owning class rather than being dropped.
            attr_type = self.class_attrs.get(self.current_class, {}).get(parts[1])
            if attr_type:
                return f"{attr_type}.{'.'.join(parts[2:])}"
            return f"{self.current_class}.{parts[1]}"

        # `db = Database()` ... `db.save()` — the case that string matching
        # alone can never see.
        if len(parts) > 1:
            var_type = self.lookup_variable(parts[0])
            if var_type:
                return f"{var_type}.{'.'.join(parts[1:])}"

        if "." in name:
            # An attribute call on something whose type could not be inferred:
            # `mystery.save()` where mystery is an unannotated parameter. The
            # call is real, so the edge is kept, but the target is recorded as
            # unresolved rather than dressed up as a module path. Counting
            # these is what makes the parser's blind spots measurable instead
            # of invisible.
            self.unresolved.add(name)
            return name

        # Bare, unqualified call (e.g. `print(x)`, or a nested closure like
        # `dfs(...)` invoked from inside a method). Check for a real Python
        # builtin first, then a same-class member (a function nested inside
        # a method belongs to the enclosing class's scope, not the module),
        # before falling back to assuming a module-level symbol.
        if is_builtin_name(name):
            return name

        # Walk outwards through the enclosing scopes: a closure calls its
        # sibling closure, or itself, by bare name, and those live under the
        # defining function rather than the module.
        scope = self.current_function
        while scope:
            candidate = f"{scope}.{name}"
            if candidate in self.local_symbols:
                return candidate
            scope = scope.rsplit(".", 1)[0] if "." in scope else None

        if self.current_class:
            class_candidate = f"{self.current_class}.{name}"
            if class_candidate in self.local_symbols:
                return class_candidate

        return f"{self.module_name}.{name}"

def is_builtin_name(name):
    """Determines if a resolved symbol name matches standard Python built-ins or properties."""
    if name in BUILTIN_NAMES:
        return True
    parts = name.split(".")
    if parts[0] in BUILTIN_NAMES:
        return True
        
    common_builtins_attrs = {
        "append", "extend", "insert", "pop", "remove", "clear", "copy", "count", "index",
        "get", "keys", "values", "items", "update", "split", "strip", "lower", "upper",
        "join", "replace", "find", "add", "difference", "intersection", "union", "discard",
        "read", "write", "close", "format", "encode", "decode", "startswith", "endswith"
    }
    if parts[-1] in common_builtins_attrs:
        return True
    return False

def parse_repository(root_dir):
    """
    Performs a two-pass static AST codebase parsing:
    1. Pass 1: Crawl all source files and compile a global local_symbols table.
    2. Pass 2: Traverse files to map architectural calls, resolve star-imports, and classify node types.
    """
    exclude_dirs = {".git", "__pycache__", "venv", ".venv", "env", ".agents", "scratch"}
    
    # ─── Pass 1: Collect Defined Symbols ───
    local_symbols = set()
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                
                rel_path = os.path.relpath(file_path, root_dir)
                module_parts = rel_path[:-3].replace(os.sep, ".").split(".")
                if module_parts[-1] == "__init__":
                    module_parts.pop()
                module_name = ".".join(module_parts)
                if not module_name:
                    module_name = file[:-3]
                    
                local_symbols.add(module_name)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=file_path)
                    visitor = DefinitionVisitor(module_name)
                    visitor.visit(tree)
                    local_symbols.update(visitor.symbols)
                except Exception as e:
                    print(f"Error in Pass 1 parsing for {file_path}: {e}")

    # ─── Pass 2: Map AST Structural Call Edges & Classify Nodes ───
    all_nodes = []
    all_edges = []
    star_imports_map = {}
    all_unresolved = set()
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                
                rel_path = os.path.relpath(file_path, root_dir)
                module_parts = rel_path[:-3].replace(os.sep, ".").split(".")
                if module_parts[-1] == "__init__":
                    module_parts.pop()
                module_name = ".".join(module_parts)
                if not module_name:
                    module_name = file[:-3]
                    
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        source = f.read()

                    tree = ast.parse(source, filename=file_path)
                    visitor = CodeASTVisitor(module_name, local_symbols)
                    visitor.visit(tree)

                    # Appended after the walk: the `__main__` guard that makes
                    # a module an entrypoint is only found during visiting.
                    module_roles = set(visitor.module_roles)
                    if visitor.is_test_module:
                        module_roles.add("test")
                    all_nodes.append({
                        "title": module_name,
                        "summary": f"module {file}",
                        "node_type": "module",
                        "roles": sorted(module_roles),
                    })

                    all_nodes.extend(visitor.nodes)
                    all_edges.extend(visitor.edges)
                    all_unresolved |= visitor.unresolved
                    if visitor.star_imports:
                        star_imports_map[module_name] = visitor.star_imports
                except Exception as e:
                    print(f"Error in Pass 2 parsing for {file_path}: {e}")
                    
    # Post-Parse Star Imports Resolution
    for edge in all_edges:
        target = edge["target"]
        if target not in local_symbols:
            parts = target.split(".")
            if len(parts) > 1:
                module_prefix = ".".join(parts[:-1])
                rel_name = parts[-1]
                if module_prefix in star_imports_map:
                    for star_mod in star_imports_map[module_prefix]:
                        possible_target = f"{star_mod}.{rel_name}"
                        if possible_target in local_symbols:
                            edge["target"] = possible_target
                            break

    # Dynamic Classification of Call Targets
    final_nodes = []
    added_titles = set()
    
    for node in all_nodes:
        if node["title"] not in added_titles:
            added_titles.add(node["title"])
            final_nodes.append(node)
            
    # Resolve node_type for target edges not yet defined in final_nodes
    for edge in all_edges:
        target = edge["target"]
        if target not in added_titles:
            added_titles.add(target)
            
            # Categorize the node type
            if target in local_symbols:
                # Local symbol that was parsed but node description wasn't created yet
                # E.g. class methods called dynamically
                node_type = "method" if "." in target else "function"
                summary = "Local codebase component definition"
            elif is_builtin_name(target):
                node_type = "builtin"
                summary = "Python runtime built-in function or collection method"
            elif target in all_unresolved:
                # A call on a value whose type could not be inferred. Recorded
                # so the gap is countable rather than misfiled as a dependency.
                node_type = "unresolved"
                summary = "Call target that static resolution could not identify"
            else:
                node_type = "external_library"
                summary = "External dependency or package import reference"
                
            final_nodes.append({
                "title": target,
                "summary": summary,
                "node_type": node_type,
                "roles": [],
            })
            
    return final_nodes, all_edges

def ingest_codebase(repo_path, db_path="epicenter.db"):
    """Parses codebase using 2-pass AST parsing and saves the architecture graph to SQLite."""
    nodes, edges = parse_repository(repo_path)
    if not nodes:
        return 0
    save_code_graph_to_db(repo_path, nodes, edges, db_path)
    return len(edges)
