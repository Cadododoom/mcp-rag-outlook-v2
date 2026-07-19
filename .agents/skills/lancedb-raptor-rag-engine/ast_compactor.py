#!/usr/bin/env python3
import os
import sys
import re
import ast

def strip_cpp_comments(code):
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return ""
        else:
            return s
    return pattern.sub(replacer, code)

def compress_cpp_or_java(code):
    # Strip comments first
    code_clean = strip_cpp_comments(code)
    
    output = []
    i = 0
    n = len(code_clean)
    
    # Keywords indicating a structural declaration block
    structural_keywords = {
        'class', 'struct', 'namespace', 'enum', 'union', 
        'interface', 'template'
    }
    
    in_string = False
    in_char = False
    escape = False
    
    last_words = ""
    
    while i < n:
        c = code_clean[i]
        
        if in_string:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_string = False
            output.append(c)
            i += 1
            continue
            
        if in_char:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '\'':
                in_char = False
            output.append(c)
            i += 1
            continue
            
        if c == '"':
            in_string = True
            output.append(c)
            i += 1
            continue
        elif c == '\'':
            in_char = True
            output.append(c)
            i += 1
            continue
            
        if c == '{':
            recent_text = last_words.lower()
            is_structural = any(kw in recent_text for kw in structural_keywords)
            
            if is_structural:
                # Keep structural brace
                output.append(c)
                last_words = ""
                i += 1
            else:
                # Bypass this function/method block!
                output.append("{ /* bypassed */ }")
                # Skip to matching closing brace
                brace_count = 1
                i += 1
                while i < n and brace_count > 0:
                    bc = code_clean[i]
                    if bc == '"':
                        i += 1
                        while i < n:
                            if code_clean[i] == '"' and code_clean[i-1] != '\\':
                                break
                            i += 1
                    elif bc == '\'':
                        i += 1
                        while i < n:
                            if code_clean[i] == '\'' and code_clean[i-1] != '\\':
                                break
                            i += 1
                    elif bc == '{':
                        brace_count += 1
                    elif bc == '}':
                        brace_count -= 1
                    i += 1
                last_words = ""
            continue
            
        output.append(c)
        if c.isalnum() or c in ' _<>,:':
            last_words += c
            if len(last_words) > 100:
                last_words = last_words[-100:]
        elif c in ';()=':
            last_words = ""
            
        i += 1
        
    # Clean up empty lines and multi-line whitespaces
    result = "".join(output)
    result = re.sub(r'\n\s*\n', '\n', result)
    return result.strip()

class PythonASTCompactor(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        # Keep name, args, decorator_list, returns, but bypass body with pass
        node.body = [ast.Pass()]
        return node
        
    def visit_AsyncFunctionDef(self, node):
        node.body = [ast.Pass()]
        return node

def compress_python(code):
    import textwrap
    dedented_code = textwrap.dedent(code)
    try:
        tree = ast.parse(dedented_code)
        compactor = PythonASTCompactor()
        modified_tree = compactor.visit(tree)
        # Fix line numbers
        ast.fix_missing_locations(modified_tree)
        return ast.unparse(modified_tree)
    except Exception as e:
        # Fallback to simple line-based comment stripping if parsing fails
        lines = []
        for line in code.splitlines():
            clean = re.sub(r'#.*$', '', line).rstrip()
            if clean:
                lines.append(clean)
        return "\n".join(lines)

def detect_language(code):
    # Detect C++ / Java / Python signatures
    if re.search(r'#include|std::|#define|#ifndef|class\s+\w+\s*:\s*public|void\s+\w+::', code):
        return '.cpp'
    if re.search(r'def\s+\w+\s*\(.*?\)\s*:|import\s+\w+|from\s+\w+\s+import', code):
        return '.py'
    if re.search(r'public\s+class\s+\w+|import\s+java\.', code):
        return '.java'
    return '.txt'

def compress_code(code, file_path=None):
    if file_path is None:
        ext = detect_language(code)
    elif file_path.startswith('.') and '/' not in file_path and '\\' not in file_path:
        ext = file_path.lower()
    else:
        ext = os.path.splitext(file_path)[1].lower()
        
    if ext in ('.cc', '.cpp', '.cxx', '.c', '.h', '.hpp', '.java'):
        return compress_cpp_or_java(code)
    elif ext == '.py':
        return compress_python(code)
    else:
        # General file format
        return code
