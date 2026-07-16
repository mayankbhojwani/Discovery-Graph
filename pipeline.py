import os
import ast
import builtins
from database import save_code_graph_to_db

# Extract standard Python built-in names
BUILTIN_NAMES = set(dir(builtins))

class DefinitionVisitor(ast.NodeVisitor):
    """
    Pass 1 Visitor: Extracts all local symbols (classes, methods, functions)
    defined within a module to build the codebase symbol table.
    """
    def __init__(self, module_name):
        self.module_name = module_name
        self.current_class = None
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
        if self.current_class:
            self.symbols.add(f"{self.current_class}.{node.name}")
        else:
            self.symbols.add(f"{self.module_name}.{node.name}")
        self.generic_visit(node)

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

    def visit_ClassDef(self, node):
        class_name = f"{self.module_name}.{node.name}"
        bases = []
        for base in node.bases:
            base_name = self.get_base_class_name(base)
            if base_name:
                bases.append(base_name)
        
        summary = f"class {node.name}(" + ", ".join(bases) + "):"
        self.nodes.append({
            "title": class_name,
            "summary": summary,
            "node_type": "class"
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
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        self.visit_any_function(node)
        
    def visit_AsyncFunctionDef(self, node):
        self.visit_any_function(node)
        
    def visit_any_function(self, node):
        if self.current_class:
            func_name = f"{self.current_class}.{node.name}"
            node_type = "method"
        else:
            func_name = f"{self.module_name}.{node.name}"
            node_type = "function"
            
        args_list = [arg.arg for arg in node.args.args]
        summary = f"def {node.name}(" + ", ".join(args_list) + "):"
        
        self.nodes.append({
            "title": func_name,
            "summary": summary,
            "node_type": node_type
        })
        
        parent = self.current_class or self.module_name
        self.edges.append({
            "source": parent,
            "target": func_name,
            "edge_type": "contains"
        })
        
        old_func = self.current_function
        self.current_function = func_name
        self.generic_visit(node)
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
        if not self.current_function:
            self.generic_visit(node)
            return
            
        called_name = self.get_full_attr_name(node.func)
        if called_name:
            resolved = self.resolve_call(called_name)
            if resolved:
                self.edges.append({
                    "source": self.current_function,
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
            
        if name.startswith("self.") and self.current_class:
            method_name = name.split(".")[1]
            return f"{self.current_class}.{method_name}"
            
        if "." in name:
            return name
            
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
                    
                    all_nodes.append({
                        "title": module_name,
                        "summary": f"module {file}",
                        "node_type": "module"
                    })
                    
                    tree = ast.parse(source, filename=file_path)
                    visitor = CodeASTVisitor(module_name, local_symbols)
                    visitor.visit(tree)
                    
                    all_nodes.extend(visitor.nodes)
                    all_edges.extend(visitor.edges)
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
            else:
                node_type = "external_library"
                summary = "External dependency or package import reference"
                
            final_nodes.append({
                "title": target,
                "summary": summary,
                "node_type": node_type
            })
            
    return final_nodes, all_edges

def ingest_codebase(repo_path, db_path="curiosity.db"):
    """Parses codebase using 2-pass AST parsing and saves the architecture graph to SQLite."""
    nodes, edges = parse_repository(repo_path)
    if not nodes:
        return 0
    save_code_graph_to_db(repo_path, nodes, edges, db_path)
    return len(edges)
