# ast_parser.py
import ast
import json
import os

class ArchitectureVisitor(ast.NodeVisitor):
    """
    An object-oriented AST visitor that cleanly extracts imports, 
    functions, and Flask/FastAPI routes from a syntax tree.
    """
    def __init__(self):
        # Using a set() automatically prevents duplicate imports
        self.imports = set() 
        self.functions = []
        self.api_routes = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.functions.append(node.name)
        
        # Check decorators for API routes (e.g., @app.route('/api'))
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                # We added 'get', 'post', etc., to make it more robust!
                if decorator.func.attr in ['route', 'get', 'post', 'put', 'delete']:
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        self.api_routes.append(decorator.args[0].value)
                        
        self.generic_visit(node)

def extract_architecture(file_path):
    """
    Reads a Python file and returns a JSON blueprint of its architecture.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Target file '{file_path}' does not exist.")

    with open(file_path, "r", encoding="utf-8") as source:
        tree = ast.parse(source.read())

    # Initialize and run our optimized visitor
    visitor = ArchitectureVisitor()
    visitor.visit(tree)

    architecture_data = {
        "file_analyzed": file_path,
        "imports": sorted(list(visitor.imports)), # Sort alphabetically for clean output
        "functions": visitor.functions,
        "api_routes": visitor.api_routes
    }

    return json.dumps(architecture_data, indent=2)

# --- Testing Block ---
if __name__ == "__main__":
    test_file = "legacy_app.py"
    print(f" Analyzing '{test_file}' with AST NodeVisitor...\n")
    try:
        result = extract_architecture(test_file)
        print(" Extraction Successful! Here is the JSON blueprint:\n")
        print(result)
    except Exception as e:
        print(f" Error: {e}")