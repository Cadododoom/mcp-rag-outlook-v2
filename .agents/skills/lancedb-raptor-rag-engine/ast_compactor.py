#!/usr/bin/env python3
import os
import sys
import re
import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser

# Load languages
PY_LANG = Language(tree_sitter_python.language())
JS_LANG = Language(tree_sitter_javascript.language())
TS_LANG = Language(tree_sitter_typescript.language_typescript())

def get_parser_for_ext(ext):
    parser = Parser()
    if ext == '.py':
        parser.language = PY_LANG
        return parser, 'py'
    elif ext in ('.js', '.jsx'):
        parser.language = JS_LANG
        return parser, 'js'
    elif ext in ('.ts', '.tsx'):
        parser.language = TS_LANG
        return parser, 'ts'
    return None, None

def find_function_bodies(node, lang_type):
    bodies = []
    if lang_type == 'py':
        if node.type == 'function_definition':
            for child in node.children:
                if child.type == 'block':
                    bodies.append((child.start_byte, child.end_byte, 'py'))
                    return bodies # Do not recurse inside bypassed function bodies
    elif lang_type in ('js', 'ts'):
        # Target function declarations, method definitions, arrow functions and function expressions
        if node.type in ('function_declaration', 'method_definition', 'arrow_function', 'function', 'generator_function', 'function_expression'):
            for child in node.children:
                if child.type == 'statement_block':
                    bodies.append((child.start_byte, child.end_byte, 'js'))
                    return bodies # Do not recurse inside bypassed function bodies
                    
    for child in node.children:
        bodies.extend(find_function_bodies(child, lang_type))
    return bodies

def detect_language(code):
    if re.search(r'def\s+\w+\s*\(.*?\)\s*:|import\s+\w+|from\s+\w+\s+import', code):
        return '.py'
    if re.search(r'\b(const|let|var)\s+\w+|import\s+.*?from\s+[\'"]|export\s+(const|default|let|var|class|function|interface|type)\b|=>', code):
        return '.js'
    return '.txt'

def compress_code(code, file_path=None):
    if file_path is None:
        # Try to find file path/name header
        path_match = re.search(r'(?:[Ff]ile|[Pp]ath):\s*([^\s\n]+)|---\s*([^\s\n]+?)\s*---', code)
        if path_match:
            matched_path = path_match.group(1) or path_match.group(2)
            ext = os.path.splitext(matched_path)[1].lower()
        else:
            ext = detect_language(code)
    elif file_path.startswith('.') and '/' not in file_path and '\\' not in file_path:
        ext = file_path.lower()
    else:
        ext = os.path.splitext(file_path)[1].lower()
        
    parser, lang_type = get_parser_for_ext(ext)
    if not parser:
        return code # Fallback for unsupported formats (txt, md, cpp, etc.)
        
    code_bytes = code.encode('utf8')
    tree = parser.parse(code_bytes)
    
    bodies = find_function_bodies(tree.root_node, lang_type)
    # Sort by start_byte descending to replace from back to front
    bodies.sort(key=lambda x: x[0], reverse=True)
    
    modified_bytes = bytearray(code_bytes)
    for start, end, l_type in bodies:
        if l_type == 'py':
            replacement = "pass".encode('utf8')
        else:
            replacement = "{ /* bypassed */ }".encode('utf8')
        modified_bytes[start:end] = replacement
        
    return modified_bytes.decode('utf8')
