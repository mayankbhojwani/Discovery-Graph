import os
import ast
from database import save_code_graph_to_db

class CodeASTVisitor(ast.NodeVisitor):
    def __init__(self, module_name):
        self.module_name = module_name
        self.current_class = None
        self.current_function = None
        
        self.nodes = [] # List of dicts: {"title": ..., "summary": ..., "node_type": ...}
        self.edges = [] # List of dicts: {"source": ..., "target": ..., "edge_type": ...}
        
        # Local imports mapping name -> fully_qualified_target
        self.imports = {}
        
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
            name = alias.asname or alias.name
            target = f"{module}.{alias.name}" if module else alias.name
            self.imports[name] = target
            self.edges.append({
                "source": self.module_name,
                "target": target,
                "edge_type": "imports"
            })
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        class_name = f"{self.module_name}.{node.name}"
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                if isinstance(base.value, ast.Name):
                    bases.append(f"{base.value.id}.{base.attr}")
        
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
        
    def visit_Call(self, node):
        if not self.current_function:
            self.generic_visit(node)
            return
            
        called_name = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                called_name = f"{node.func.value.id}.{node.func.attr}"
                
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

def parse_repository(root_dir):
    """
    Traverses the codebase directory, extracts module/class/function/method nodes,
    constructs static containment/inheritance/call edges, and ignores config/temp directories.
    """
    all_nodes = []
    all_edges = []
    
    exclude_dirs = {".git", "__pycache__", "venv", ".venv", "env", ".agents", "scratch"}
    
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
                    visitor = CodeASTVisitor(module_name)
                    visitor.visit(tree)
                    
                    all_nodes.extend(visitor.nodes)
                    all_edges.extend(visitor.edges)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
                    
    # Generate nodes for unresolved calls/imports (mark as external)
    local_titles = {node["title"] for node in all_nodes}
    external_nodes = set()
    for edge in all_edges:
        target = edge["target"]
        if target not in local_titles:
            external_nodes.add(target)
            
    for ext in external_nodes:
        if ext.startswith("self."):
            continue
        all_nodes.append({
            "title": ext,
            "summary": f"External dependency or library import",
            "node_type": "external"
        })
        
    return all_nodes, all_edges

def ingest_codebase(repo_path, db_path="curiosity.db"):
    """Parses a local codebase and commits the structural graph database to SQLite."""
    nodes, edges = parse_repository(repo_path)
    if not nodes:
        return 0
    save_code_graph_to_db(repo_path, nodes, edges, db_path)
    return len(edges)
