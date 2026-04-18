#!/usr/bin/env python3
"""
clarity_mermaid.py — Genera un .md con diagramas Mermaid desde cualquier contrato Clarity
Cero dependencias externas.

Uso:
    python clarity_mermaid.py contract.clar
    python clarity_mermaid.py contract.clar --output report.md
"""

import argparse
import re
import sys
from pathlib import Path

# ── Builtins Clarity (filtrar del call-graph) ─────────────────────────────────
CLARITY_BUILTINS = {
    "let",
    "ok",
    "err",
    "if",
    "and",
    "or",
    "not",
    "begin",
    "when",
    "is-ok",
    "is-err",
    "is-some",
    "is-none",
    "is-eq",
    "is-standard",
    "unwrap!",
    "unwrap-panic",
    "unwrap-err!",
    "unwrap-err-panic",
    "asserts!",
    "try!",
    "map-get?",
    "map-set",
    "map-delete",
    "map-insert",
    "var-get",
    "var-set",
    "get",
    "merge",
    "tuple",
    "some",
    "none",
    "list",
    "map",
    "filter",
    "fold",
    "append",
    "concat",
    "len",
    "index-of",
    "default-to",
    "to-uint",
    "to-int",
    "contract-of",
    "as-contract",
    "contract-call?",
    "tx-sender",
    "contract-caller",
    "block-height",
    "stx-transfer?",
    "stx-get-balance",
    "hash160",
    "sha256",
    "keccak256",
    "to-consensus-buff?",
    "from-consensus-buff?",
    "print",
    "at-block",
    "get-block-info?",
    "define-public",
    "define-private",
    "define-read-only",
    "define-constant",
    "define-map",
    "define-data-var",
    "use-trait",
    "nft-mint?",
    "nft-transfer?",
    "nft-get-owner?",
    "nft-burn?",
    "ft-mint?",
    "ft-transfer?",
    "ft-get-balance?",
    "ft-burn?",
    "as-max-len?",
    "unwrap",
    "asserts",
}

# ── Parser ────────────────────────────────────────────────────────────────────


def strip_comments(code: str) -> str:
    return re.sub(r";;[^\n]*", "", code)


def extract_top_level_sexprs(code: str) -> list:
    exprs, depth, start = [], 0, None
    for i, ch in enumerate(code):
        if ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                exprs.append(code[start : i + 1])
                start = None
    return exprs


def parse_contract(code: str) -> dict:
    clean = strip_comments(code)
    exprs = extract_top_level_sexprs(clean)

    result = {
        "constants": [],
        "errors": [],
        "data_vars": [],
        "maps": [],  # list of (name, key_type, val_type)
        "traits_used": [],
        "traits_impl": [],
        "tokens": [],
        "functions": [],
    }

    for expr in exprs:
        # use-trait
        m = re.match(r"\(use-trait\s+(\S+)\s+(\S+)", expr)
        if m:
            result["traits_used"].append({"alias": m.group(1), "ref": m.group(2)})
            continue

        # impl-trait
        m = re.match(r"\(impl-trait\s+(\S+)", expr)
        if m:
            result["traits_impl"].append(m.group(1))
            continue

        # define-constant
        m = re.match(r"\(define-constant\s+(\S+)\s+(.+)", expr, re.DOTALL)
        if m:
            name, val = m.group(1), m.group(2).strip()
            if name.startswith("ERR_") or "(err " in val:
                result["errors"].append(name)
            else:
                result["constants"].append(name)
            continue

        # define-data-var
        m = re.match(r"\(define-data-var\s+(\S+)\s+(\S+)", expr)
        if m:
            result["data_vars"].append({"name": m.group(1), "type": m.group(2)})
            continue

        # define-map  (name key-type val-type)
        m = re.match(r"\(define-map\s+(\S+)\s*([\s\S]+)", expr)
        if m:
            name = m.group(1)
            rest = m.group(2).strip()
            # Intentar extraer key y value como s-exprs o palabras
            parts = extract_top_level_sexprs(rest)
            key_t = parts[0].strip() if len(parts) > 0 else "?"
            val_t = parts[1].strip() if len(parts) > 1 else "?"
            result["maps"].append({"name": name, "key": key_t, "val": val_t})
            continue

        # tokens
        m = re.match(r"\(define-(?:fungible|non-fungible)-token\s+(\S+)", expr)
        if m:
            result["tokens"].append(m.group(1))
            continue

        # funciones
        m = re.match(
            r"\((define-(public|private|read-only))\s+\((\S+)([\s\S]*?)\)", expr
        )
        if m:
            func_type = m.group(2)
            func_name = m.group(3)
            body = expr

            # Extraer parámetros (primer nivel tras el nombre)
            param_match = re.match(
                r"\(define-(?:public|private|read-only)\s+\("
                + re.escape(func_name)
                + r"(.*?)\)",
                expr,
                re.DOTALL,
            )
            raw_params = param_match.group(1).strip() if param_match else ""
            params = re.findall(r"\((\S+)\s+[^)]+\)", raw_params)

            map_reads = set(re.findall(r"\(map-get\?\s+(\S+)", body))
            map_writes = set(re.findall(r"\(map-set\s+(\S+)", body))
            map_deletes = set(re.findall(r"\(map-delete\s+(\S+)", body))
            var_reads = set(re.findall(r"\(var-get\s+(\S+)", body))
            var_writes = set(re.findall(r"\(var-set\s+(\S+)", body))
            errors_used = set(re.findall(r"(ERR_[A-Z_0-9]+)", body))
            has_asserts = len(re.findall(r"\(asserts!", body))
            has_try = len(re.findall(r"\(try!", body))

            raw_calls = set(re.findall(r"\(([a-z][a-z0-9\-!?]+)[\s\)]", body))
            calls = raw_calls - CLARITY_BUILTINS - {func_name}

            result["functions"].append(
                {
                    "name": func_name,
                    "type": func_type,
                    "params": params,
                    "map_reads": map_reads,
                    "map_writes": map_writes,
                    "map_deletes": map_deletes,
                    "var_reads": var_reads,
                    "var_writes": var_writes,
                    "errors_used": errors_used,
                    "calls": calls,
                    "asserts": has_asserts,
                    "trys": has_try,
                }
            )

    return result


# ── Sanitizar IDs Mermaid ─────────────────────────────────────────────────────


def mid(s: str) -> str:
    """Convierte un nombre Clarity en ID válido para Mermaid."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


# ── Generadores de diagramas ──────────────────────────────────────────────────


def diagram_architecture(p: dict) -> str:
    lines = ["graph LR"]

    # Subgraph: Traits
    if p["traits_used"]:
        lines.append("  subgraph TRAITS[🔗 Traits]")
        for t in p["traits_used"]:
            lines.append(f"    trait_{mid(t['alias'])}([{t['alias']}])")
        lines.append("  end")

    # Subgraph: Storage
    if p["maps"] or p["data_vars"] or p["tokens"]:
        lines.append("  subgraph STORAGE[💾 Storage]")
        for m in p["maps"]:
            lines.append(f"    map_{mid(m['name'])}[(🗺 {m['name']})]")
        for v in p["data_vars"]:
            lines.append(f"    var_{mid(v['name'])}([📦 {v['name']}]):::varStyle")
        for tok in p["tokens"]:
            lines.append(f"    tok_{mid(tok)}{{🪙 {tok}}}:::tokenStyle")
        lines.append("  end")

    # Subgraph: Constants / Errors
    if p["constants"] or p["errors"]:
        lines.append("  subgraph CONSTS[📌 Constants & Errors]")
        for c in p["constants"]:
            lines.append(f"    const_{mid(c)}[{c}]:::constStyle")
        for e in p["errors"]:
            lines.append(f"    err_{mid(e)}[{e}]:::errStyle")
        lines.append("  end")

    # Subgraph: Functions
    lines.append("  subgraph FUNCS[⚙️ Functions]")
    for f in p["functions"]:
        shape_l, shape_r = {
            "public": ("[[", "]]"),
            "read-only": ("([", "])"),
            "private": ("[/", "/]"),
        }.get(f["type"], ("[", "]"))
        lines.append(
            f"    fn_{mid(f['name'])}{shape_l}{f['name']}{shape_r}:::{f['type'].replace('-', '_')}Style"
        )
    lines.append("  end")

    # Edges
    func_names = {f["name"] for f in p["functions"]}
    map_names = {m["name"] for m in p["maps"]}
    var_names = {v["name"] for v in p["data_vars"]}

    for f in p["functions"]:
        fn = f"fn_{mid(f['name'])}"
        for m in f["map_reads"]:
            if m in map_names:
                lines.append(f"  map_{mid(m)} -. read .-> {fn}")
        for m in f["map_writes"]:
            if m in map_names:
                lines.append(f"  {fn} -- write --> map_{mid(m)}")
        for m in f["map_deletes"]:
            if m in map_names:
                lines.append(f"  {fn} -- delete --> map_{mid(m)}")
        for v in f["var_reads"]:
            if v in var_names:
                lines.append(f"  var_{mid(v)} -. read .-> {fn}")
        for v in f["var_writes"]:
            if v in var_names:
                lines.append(f"  {fn} -- write --> var_{mid(v)}")
        for called in f["calls"]:
            if called in func_names:
                lines.append(f"  {fn} --> fn_{mid(called)}")
        for e in f["errors_used"]:
            if e in p["errors"]:
                lines.append(f"  {fn} -. throws .-> err_{mid(e)}")

    # Estilos
    lines += [
        "  classDef publicStyle fill:#4CAF50,color:#fff,stroke:#388E3C",
        "  classDef read_onlyStyle fill:#2196F3,color:#fff,stroke:#1565C0",
        "  classDef privateStyle fill:#FF9800,color:#fff,stroke:#E65100",
        "  classDef errStyle fill:#F44336,color:#fff,stroke:#B71C1C",
        "  classDef constStyle fill:#607D8B,color:#fff,stroke:#37474F",
        "  classDef varStyle fill:#E91E63,color:#fff,stroke:#880E4F",
        "  classDef tokenStyle fill:#FF5722,color:#fff,stroke:#BF360C",
    ]
    return "\n".join(lines)


def diagram_call_graph(p: dict) -> str:
    func_names = {f["name"] for f in p["functions"]}
    lines = ["graph TD"]
    for f in p["functions"]:
        shape_l, shape_r = {
            "public": ("[[", "]]"),
            "read-only": ("([", "])"),
            "private": ("[/", "/]"),
        }.get(f["type"], ("[", "]"))
        lines.append(
            f"  fn_{mid(f['name'])}{shape_l}{f['name']}{shape_r}:::{f['type'].replace('-', '_')}Style"
        )
    for f in p["functions"]:
        for called in f["calls"]:
            if called in func_names:
                lines.append(f"  fn_{mid(f['name'])} --> fn_{mid(called)}")
    lines += [
        "  classDef publicStyle fill:#4CAF50,color:#fff",
        "  classDef read_onlyStyle fill:#2196F3,color:#fff",
        "  classDef privateStyle fill:#FF9800,color:#fff",
    ]
    return "\n".join(lines)


def diagram_data_flow(p: dict) -> str:
    lines = ["graph LR"]
    map_names = {m["name"] for m in p["maps"]}
    var_names = {v["name"] for v in p["data_vars"]}

    for m in p["maps"]:
        lines.append(f"  map_{mid(m['name'])}[(🗺 {m['name']})]")
    for v in p["data_vars"]:
        lines.append(f"  var_{mid(v['name'])}([📦 {v['name']}])")
    for f in p["functions"]:
        if (
            f["map_reads"]
            or f["map_writes"]
            or f["map_deletes"]
            or f["var_reads"]
            or f["var_writes"]
        ):
            shape_l, shape_r = {
                "public": ("[[", "]]"),
                "read-only": ("([", "])"),
                "private": ("[/", "/]"),
            }.get(f["type"], ("[", "]"))
            lines.append(
                f"  fn_{mid(f['name'])}{shape_l}{f['name']}{shape_r}:::{f['type'].replace('-', '_')}Style"
            )
            for m in f["map_reads"]:
                if m in map_names:
                    lines.append(f"  map_{mid(m)} -. read .-> fn_{mid(f['name'])}")
            for m in f["map_writes"]:
                if m in map_names:
                    lines.append(f"  fn_{mid(f['name'])} -- write --> map_{mid(m)}")
            for m in f["map_deletes"]:
                if m in map_names:
                    lines.append(f"  fn_{mid(f['name'])} -- delete --> map_{mid(m)}")
            for v in f["var_reads"]:
                if v in var_names:
                    lines.append(f"  var_{mid(v)} -. read .-> fn_{mid(f['name'])}")
            for v in f["var_writes"]:
                if v in var_names:
                    lines.append(f"  fn_{mid(f['name'])} -- write --> var_{mid(v)}")
    lines += [
        "  classDef publicStyle fill:#4CAF50,color:#fff",
        "  classDef read_onlyStyle fill:#2196F3,color:#fff",
        "  classDef privateStyle fill:#FF9800,color:#fff",
    ]
    return "\n".join(lines)


def diagram_map_schema(p: dict) -> str:
    """Diagrama de clases Mermaid mostrando la estructura interna de maps."""
    if not p["maps"] and not p["data_vars"]:
        return ""
    lines = ["classDiagram"]
    for m in p["maps"]:
        name = m["name"]
        # Limpiar tipos para mostrar
        key = re.sub(r"\s+", " ", m["key"])[:60]
        val = re.sub(r"\s+", " ", m["val"])[:60]
        safe_name = mid(name)
        lines.append(f"  class {safe_name}MAP {{")
        lines.append("    <<map>>")
        lines.append(f"    KEY: {key}")
        lines.append(f"    VALUE: {val}")
        lines.append("  }")
    for v in p["data_vars"]:
        safe_name = mid(v["name"]) + "VAR"
        lines.append(f"  class {safe_name} {{")
        lines.append("    <<data-var>>")
        lines.append(f"    type: {v['type']}")
        lines.append("  }")
    return "\n".join(lines)


def diagram_error_flow(p: dict) -> str:
    """Qué funciones pueden lanzar qué errores."""
    funcs_with_errors = [f for f in p["functions"] if f["errors_used"]]
    if not funcs_with_errors:
        return ""
    lines = ["graph LR"]
    for e in p["errors"]:
        lines.append(f"  err_{mid(e)}[❌ {e}]:::errStyle")
    for f in funcs_with_errors:
        shape_l, shape_r = {
            "public": ("[[", "]]"),
            "read-only": ("([", "])"),
            "private": ("[/", "/]"),
        }.get(f["type"], ("[", "]"))
        lines.append(
            f"  fn_{mid(f['name'])}{shape_l}{f['name']}{shape_r}:::{f['type'].replace('-', '_')}Style"
        )
        for e in f["errors_used"]:
            lines.append(f"  fn_{mid(f['name'])} -- asserts --> err_{mid(e)}")
    lines += [
        "  classDef publicStyle fill:#4CAF50,color:#fff",
        "  classDef read_onlyStyle fill:#2196F3,color:#fff",
        "  classDef privateStyle fill:#FF9800,color:#fff",
        "  classDef errStyle fill:#F44336,color:#fff",
    ]
    return "\n".join(lines)


# ── Markdown builder ──────────────────────────────────────────────────────────


def wrap_mermaid(diagram: str) -> str:
    return f"```mermaid\n{diagram}\n```"


def build_markdown(p: dict, contract_name: str) -> str:
    sections = [f"# 📊 Clarity Contract Analysis: `{contract_name}`\n"]

    # Resumen
    sections.append("## 📋 Summary\n")
    sections.append("| Component | Count |")
    sections.append("|---|---|")
    sections.append(f"| Traits used | {len(p['traits_used'])} |")
    sections.append(f"| Constants | {len(p['constants'])} |")
    sections.append(f"| Errors | {len(p['errors'])} |")
    sections.append(f"| Maps | {len(p['maps'])} |")
    sections.append(f"| Data Vars | {len(p['data_vars'])} |")
    sections.append(f"| Tokens | {len(p['tokens'])} |")
    pub = sum(1 for f in p["functions"] if f["type"] == "public")
    ro = sum(1 for f in p["functions"] if f["type"] == "read-only")
    priv = sum(1 for f in p["functions"] if f["type"] == "private")
    sections.append(f"| Public functions | {pub} |")
    sections.append(f"| Read-only functions | {ro} |")
    sections.append(f"| Private functions | {priv} |")
    sections.append("")

    # Diagrama: Arquitectura
    sections.append("## 🏗️ Architecture\n")
    sections.append("> Funciones, storage, traits y relaciones entre ellos.\n")
    sections.append(wrap_mermaid(diagram_architecture(p)))
    sections.append("")

    # Diagrama: Call Graph
    if any(f["calls"] for f in p["functions"]):
        sections.append("## 📞 Call Graph\n")
        sections.append(wrap_mermaid(diagram_call_graph(p)))
        sections.append("")

    # Diagrama: Data Flow
    if p["maps"] or p["data_vars"]:
        sections.append("## 🔄 Data Flow\n")
        sections.append("> Accesos de lectura/escritura al storage.\n")
        sections.append(wrap_mermaid(diagram_data_flow(p)))
        sections.append("")

    # Diagrama: Map Schema
    schema = diagram_map_schema(p)
    if schema:
        sections.append("## 🗺️ Storage Schema\n")
        sections.append(wrap_mermaid(schema))
        sections.append("")

    # Diagrama: Error Flow
    err_flow = diagram_error_flow(p)
    if err_flow:
        sections.append("## ❌ Error Paths\n")
        sections.append(wrap_mermaid(err_flow))
        sections.append("")

    # Tabla de funciones
    sections.append("## ⚙️ Function Details\n")
    sections.append(
        "| Function | Type | Params | Map R | Map W | Var R | Var W | Asserts | Calls |"
    )
    sections.append("|---|---|---|---|---|---|---|---|---|")
    for f in p["functions"]:
        params = ", ".join(f["params"]) if f["params"] else "—"
        sections.append(
            f"| `{f['name']}` | {f['type']} | {params} "
            f"| {', '.join(f['map_reads']) or '—'} "
            f"| {', '.join(f['map_writes'] | f['map_deletes']) or '—'} "
            f"| {', '.join(f['var_reads']) or '—'} "
            f"| {', '.join(f['var_writes']) or '—'} "
            f"| {f['asserts']} "
            f"| {', '.join(f['calls']) or '—'} |"
        )
    sections.append("")

    # Traits usados
    if p["traits_used"]:
        sections.append("## 🔗 Traits\n")
        for t in p["traits_used"]:
            sections.append(f"- `{t['alias']}` → `{t['ref']}`")
        sections.append("")

    return "\n".join(sections)


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Clarity → Mermaid Markdown visualizer")
    ap.add_argument("contract", help="Ruta al .clar")
    ap.add_argument("--output", "-o", default=None, help="Archivo .md de salida")
    args = ap.parse_args()

    src = Path(args.contract)
    if not src.exists():
        sys.exit(f"❌  No encontrado: {src}")

    code = src.read_text(encoding="utf-8")
    parsed = parse_contract(code)
    md = build_markdown(parsed, src.stem)

    out = Path(args.output) if args.output else src.with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    print(
        f"✅  {out}  ({len(parsed['functions'])} funciones, {len(parsed['maps'])} maps)"
    )
    print("    Abrí en VSCode con la extensión 'Markdown Preview Mermaid Support'")


main()
