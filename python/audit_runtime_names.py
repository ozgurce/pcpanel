# Best-effort static audit for common split-module mistakes.
# Run: py audit_runtime_names.py
import ast, builtins, os
BUILTINS = set(dir(builtins))
IGNORE = {"__name__", "__file__", "__package__"}
for fn in sorted(f for f in os.listdir('.') if f.endswith('.py')):
    try:
        src = open(fn, encoding='utf-8-sig').read()
        tree = ast.parse(src, filename=fn)
    except Exception as e:
        print(f"SYNTAX {fn}: {e}")
        continue
    assigned = set()
    used = set()
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            assigned.add(node.name)
            for arg in getattr(node, 'args', ast.arguments()).args:
                assigned.add(arg.arg)
        elif isinstance(node, ast.Import):
            for a in node.names: imports.add((a.asname or a.name.split('.')[0]))
        elif isinstance(node, ast.ImportFrom):
            for a in node.names: imports.add(a.asname or a.name)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load): used.add(node.id)
            elif isinstance(node.ctx, (ast.Store, ast.Param)): assigned.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            assigned.add(node.name)
    missing = sorted(n for n in (used - assigned - imports - BUILTINS - IGNORE) if not n.startswith('__'))
    if missing:
        print(fn + ': ' + ', '.join(missing[:40]))
