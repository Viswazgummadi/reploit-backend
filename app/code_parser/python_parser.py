# backend/app/code_parser/python_parser.py
import ast
from flask import current_app

def parse_python_file(file_content: str):
    """
    Parses the content of a Python file.
    
    Now returns the function's raw source code in addition to other details.
    """
    functions_data = []
    try:
        tree = ast.parse(file_content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                docstring = ast.get_docstring(node) or ""
                # Use ast.get_source_segment to get the exact source code of the function.
                # This requires Python 3.8+
                try:
                    source_code = ast.get_source_segment(file_content, node)
                except Exception:
                    # Fallback for complex cases, though less likely needed
                    source_code = "# Could not extract source code."

                functions_data.append({
                    "name": node.name,
                    "args": args,
                    "docstring": docstring.strip(),
                    "source_code": source_code 
                })
    except SyntaxError as e:
        current_app.logger.warning(f"Could not parse Python file due to SyntaxError: {e}")
        return None
    
    return {"functions": functions_data}