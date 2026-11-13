import ast
import re
from pathlib import Path

excluded = {".venv", "__pycache__", ".git", "node_modules"}

def included(p):
    return not any(x in excluded for x in p.parts)

files = [p for p in Path(".").rglob("*.py") if included(p)]
text_files = [
    p for p in Path(".").rglob("*")
    if p.is_file() and p.suffix.lower() in {".html", ".js", ".css"}
    and included(p)
]

print("========== PROJECT FILES ==========")
for p in sorted(Path(".").rglob("*")):
    if p.is_file() and included(p):
        print(p)

print("\n========== PYTHON MODULES ==========")
trees = {}

for p in files:
    try:
        src = p.read_text(encoding="utf-8-sig")
        tree = ast.parse(src)
        trees[p] = tree
        print(f"\n--- {p} ---")
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                print(type(n).__name__, n.name, n.lineno, n.end_lineno)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                print("IMPORT", ast.unparse(n))
    except Exception as e:
        print("PARSE ERROR:", p, e)

print("\n========== FLASK ROUTES ==========")
for p, tree in trees.items():
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.decorator_list:
                s = ast.unparse(d)
                if any(x in s for x in (".route(", ".get(", ".post(", ".errorhandler(")):
                    print(p, n.name, "->", s)

print("\n========== CROSS-MODULE REFERENCES ==========")
definitions = {}
for p, tree in trees.items():
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(n.name, []).append(str(p))

for p, tree in trees.items():
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            name = n.func.id
            owners = definitions.get(name, [])
            if owners and str(p) not in owners:
                print(f"{p}:{n.lineno} -> {name}: {owners}")

print("\n========== FRONTEND API REFERENCES ==========")
pattern = re.compile(r"""(?:fetch|axios\.[a-z]+)\s*\(\s*['"`]([^'"`]+)""")
for p in text_files:
    try:
        src = p.read_text(encoding="utf-8-sig")
        for m in pattern.finditer(src):
            print(f"{p}:{src.count(chr(10), 0, m.start()) + 1} -> {m.group(1)}")
    except Exception:
        pass

print("\n========== ROUTES PACKAGE ==========")
for p in sorted(Path("routes").rglob("*.py")):
    print(p, p.stat().st_size, "bytes")

print("\n========== AUDIT COMPLETE ==========")
