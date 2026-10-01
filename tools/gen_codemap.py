#!/usr/bin/env python3
"""Génère CODEMAP.md : carte compacte du projet pour les agents IA."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = {"__pycache__", ".venv", "venv", ".git", "pv_projects", "node_modules", "tools"}
OUT = ROOT / "CODEMAP.md"
BIG = 500  # au-delà, le fichier est signalé comme gros


def first_line(doc, n=80):
    if not doc:
        return ""
    line = doc.strip().splitlines()[0]
    return " — " + (line[:n] + "…" if len(line) > n else line)


def args_of(fn):
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs if x.arg not in ("self", "cls")]
    return ", ".join(names)


def fmt_func(fn, indent=""):
    return f"{indent}- `{fn.name}({args_of(fn)})` L{fn.lineno}-{fn.end_lineno}{first_line(ast.get_docstring(fn))}"


def internal_imports(tree, modules):
    found = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in modules:
                    found.add(a.name)
        elif isinstance(n, ast.ImportFrom):
            name = "." * n.level + (n.module or "")
            if n.level > 0 or (n.module and n.module.split(".")[0] in modules):
                found.add(name)
    return sorted(found)


def describe(path, modules):
    text = path.read_text(encoding="utf-8")
    n_lines = len(text.splitlines())
    rel = path.relative_to(ROOT)
    flag = " ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes" if n_lines > BIG else ""
    out = [f"### {rel} ({n_lines} lignes){flag}"]
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return out + [f"- erreur de syntaxe ligne {e.lineno}", ""]

    out_doc = ast.get_docstring(tree)
    if out_doc:
        out.append(out_doc.strip().splitlines()[0])
    imps = internal_imports(tree, modules)
    if imps:
        out.append("Imports internes : " + ", ".join(imps))

    consts = [t.id for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and t.id.isupper()]
    if consts:
        out.append("Constantes : " + ", ".join(consts[:40]) + (" …" if len(consts) > 40 else ""))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            out.append(f"- **class {node.name}** L{node.lineno}-{node.end_lineno}{first_line(ast.get_docstring(node))}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(fmt_func(sub, "  "))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(fmt_func(node))
    out.append("")
    return out


def main():
    files = sorted(p for p in ROOT.rglob("*.py")
                   if not IGNORE & set(p.relative_to(ROOT).parts))
    modules = {p.stem for p in files} | {p.parent.name for p in files if p.parent != ROOT}
    lines = [
        "# CODEMAP (généré par tools/gen_codemap.py, ne pas éditer à la main)",
        "Utilisation : lis cette carte AVANT d'explorer. Lis ensuite uniquement la plage de lignes utile.",
        "",
    ]
    for p in files:
        lines += describe(p, modules)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"CODEMAP.md régénéré ({len(files)} fichiers)")


if __name__ == "__main__":
    main()
