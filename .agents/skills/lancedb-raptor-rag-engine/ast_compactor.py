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
    
    structural_keywords = {
        'class', 'struct', 'namespace', 'enum', 'union', 
        'interface', 'template', 'import', 'const', 'let', 'var'
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

def strip_js_comments(code):
    pattern = re.compile(
        r'//[^\r\n]*|/\*[\s\S]*?\*/|\'(?:\\.|[^\\\'])\'|"(?:\\.|[^\\"])*"|`(?:\\.|[^\\`])*`',
        re.DOTALL | re.MULTILINE
    )
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return ""
        else:
            return s
    return pattern.sub(replacer, code)

def tokenize_js_ts(code):
    token_spec = [
        ('STRING', r'\'(?:\\.|[^\\\'])\'|"(?:\\.|[^\\"])*"|`(?:\\.|[^\\`])*`'),
        ('ARROW', r'=>'),
        ('KEYWORD', r'\b(function|class|import|export|const|let|var|if|for|while|switch|catch|try|else|finally|do|get|set|async|type|interface|enum|namespace)\b'),
        ('IDENTIFIER', r'[a-zA-Z_$][a-zA-Z0-9_$]*'),
        ('BRACE_OPEN', r'\{'),
        ('BRACE_CLOSE', r'\}'),
        ('PAREN_OPEN', r'\('),
        ('PAREN_CLOSE', r'\)'),
        ('BRACKET_OPEN', r'\['),
        ('BRACKET_CLOSE', r'\]'),
        ('COLON', r':'),
        ('SEMICOLON', r';'),
        ('EQ', r'='),
        ('WHITESPACE', r'\s+'),
        ('OTHER', r'[^\s\w]+'),
    ]
    tok_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in token_spec)
    
    tokens = []
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group(kind)
        tokens.append((kind, value, mo.start(), mo.end()))
    return tokens

def is_function_body(tokens, idx):
    prev_tokens = []
    paren_depth = 0
    bracket_depth = 0
    
    for j in range(idx - 1, -1, -1):
        tok_type, tok_val, _, _ = tokens[j]
        if tok_type == 'WHITESPACE':
            continue
            
        if tok_type == 'SEMICOLON':
            break
            
        if tok_type == 'PAREN_OPEN':
            if paren_depth == 0:
                return False
            paren_depth -= 1
        elif tok_type == 'PAREN_CLOSE':
            paren_depth += 1
            
        if tok_type == 'BRACKET_OPEN':
            if bracket_depth == 0:
                return False
            bracket_depth -= 1
        elif tok_type == 'BRACKET_CLOSE':
            bracket_depth += 1
            
        prev_tokens.append(tokens[j])
        if len(prev_tokens) > 30:
            break
            
    if not prev_tokens:
        return False
        
    if prev_tokens[0][0] == 'ARROW':
        return True
        
    first_tok_type, first_tok_val = prev_tokens[0][0], prev_tokens[0][1]
    if first_tok_type == 'KEYWORD' and first_tok_val in ('try', 'else', 'finally', 'do', 'class', 'interface', 'import', 'export'):
        return False
    if first_tok_type in ('EQ', 'COLON'):
        return False
        
    paren_close_idx = -1
    for i, tok in enumerate(prev_tokens):
        if tok[0] == 'PAREN_CLOSE':
            paren_close_idx = i
            break
            
    if paren_close_idx != -1:
        depth = 1
        token_before_paren_open = None
        for k in range(paren_close_idx + 1, len(prev_tokens)):
            tok = prev_tokens[k]
            if tok[0] == 'PAREN_CLOSE':
                depth += 1
            elif tok[0] == 'PAREN_OPEN':
                depth -= 1
                if depth == 0:
                    if k + 1 < len(prev_tokens):
                        token_before_paren_open = prev_tokens[k + 1]
                    break
        if token_before_paren_open:
            if token_before_paren_open[0] == 'KEYWORD' and token_before_paren_open[1] in ('if', 'for', 'while', 'switch', 'catch'):
                return False
            return True
            
    return False

def compress_js_or_ts(code):
    code_clean = strip_js_comments(code)
    tokens = tokenize_js_ts(code_clean)
    output = []
    i = 0
    n = len(tokens)
    while i < n:
        tok_type, tok_val, _, _ = tokens[i]
        if tok_type == 'BRACE_OPEN':
            if is_function_body(tokens, i):
                output.append("{ /* bypassed */ }")
                brace_count = 1
                i += 1
                while i < n and brace_count > 0:
                    t_type, t_val, _, _ = tokens[i]
                    if t_type == 'BRACE_OPEN':
                        brace_count += 1
                    elif t_type == 'BRACE_CLOSE':
                        brace_count -= 1
                    i += 1
                continue
            else:
                output.append(tok_val)
        else:
            output.append(tok_val)
        i += 1
    result = "".join(output)
    result = re.sub(r'\n\s*\n', '\n', result)
    return result.strip()

def detect_language(code):
    # Detect C++ / Java / Python / JS signatures
    if re.search(r'#include|std::|#define|#ifndef|class\s+\w+\s*:\s*public|void\s+\w+::', code):
        return '.cpp'
    if re.search(r'def\s+\w+\s*\(.*?\)\s*:|import\s+\w+|from\s+\w+\s+import', code):
        return '.py'
    if re.search(r'public\s+class\s+\w+|import\s+java\.', code):
        return '.java'
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
        
    if ext in ('.cc', '.cpp', '.cxx', '.c', '.h', '.hpp', '.java'):
        return compress_cpp_or_java(code)
    elif ext in ('.js', '.ts'):
        return compress_js_or_ts(code)
    elif ext == '.py':
        return compress_python(code)
    else:
        # General file format
        return code
