#!/usr/bin/env python3
"""
clarity_viz.py — Visualize Clarity smart contract structure
Usage:
    python clarity_viz.py contract.clar
    python clarity_viz.py contract.clar --output my_contract --format svg
    python clarity_viz.py contract.clar --graph all|arch|calls|data
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from graphviz import Digraph
except ImportError:
    sys.exit(
        "❌  pip install graphviz   (también instalar Graphviz binarios: https://graphviz.org/download/)"
    )

# ── Builtins de Clarity (excluir del call-graph) ─────────────────────────────
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
    "expect!",
    "expect-err!",
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
    "burn-block-height",
    "stx-transfer?",
    "stx-get-balance",
    "hash160",
    "sha256",
    "sha512",
    "keccak256",
    "secp256k1-recover?",
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
    "define-fungible-token",
    "define-non-fungible-token",
    "use-trait",
    "impl-trait",
    "nft-mint?",
    "nft-transfer?",
    "nft-get-owner?",
    "nft-burn?",
    "ft-mint?",
    "ft-transfer?",
    "ft-get-balance?",
    "ft-get-supply?",
    "ft-burn?",
    "as-max-len?",
    "unwrap",
}

# ── Colores por tipo de nodo ──────────────────────────────────────────────────
COLORS = {
    "public": {"fillcolor": "#4CAF50", "fontcolor": "white"},
    "read-only": {"fillcolor": "#2196F3", "fontcolor": "white"},
    "private": {"fillcolor": "#FF9800", "fontcolor": "white"},
    "map": {"fillcolor": "#9C27B0", "fontcolor": "white"},
    "data-var": {"fillcolor": "#E91E63", "fontcolor": "white"},
    "constant": {"fillcolor": "#607D8B", "fontcolor": "white"},
    "error": {"fillcolor": "#F44336", "fontcolor": "white"},
    "trait": {"fillcolor": "#00BCD4", "fontcolor": "white"},
    "token": {"fillcolor": "#FF5722", "fontcolor": "white"},
}

# ── Parser ────────────────────────────────────────────────────────────────────


def strip_comments(code: str) -> str:
    return re.sub(r";;[^\n]*", "", code)


def extract_top_level_sexprs(code: str) -> list[str]:
    """Extrae s-expresiones de nivel top del código Clarity."""
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
        "constants": [],  # (name, value_snippet)
        "errors": [],  # (name)
        "data_vars": [],  # name
        "maps": [],  # name
        "traits_used": [],  # (alias, contract_ref)
        "traits_impl": [],  # contract_ref
        "tokens": [],  # name
        "functions": [],  # list of dicts
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

        # define-constant (separar errores de constantes)
        m = re.match(r"\(define-constant\s+(\S+)\s+(.+)", expr, re.DOTALL)
        if m:
            name, val = m.group(1), m.group(2).strip()
            if name.startswith("ERR_") or "(err " in val:
                result["errors"].append(name)
            else:
                result["constants"].append(name)
            continue

        # define-data-var
        m = re.match(r"\(define-data-var\s+(\S+)", expr)
        if m:
            result["data_vars"].append(m.group(1))
            continue

        # define-map
        m = re.match(r"\(define-map\s+(\S+)", expr)
        if m:
            result["maps"].append(m.group(1))
            continue

        # define-fungible-token / define-non-fungible-token
        m = re.match(r"\(define-(?:fungible|non-fungible)-token\s+(\S+)", expr)
        if m:
            result["tokens"].append(m.group(1))
            continue

        # funciones
        m = re.match(r"\((define-(public|private|read-only))\s+\((\S+)", expr)
        if m:
            func_type = m.group(2)
            func_name = m.group(3)
            body = expr

            map_reads = set(re.findall(r"\(map-get\?\s+(\S+)", body))
            map_writes = set(re.findall(r"\(map-set\s+(\S+)", body))
            map_deletes = set(re.findall(r"\(map-delete\s+(\S+)", body))
            var_reads = set(re.findall(r"\(var-get\s+(\S+)", body))
            var_writes = set(re.findall(r"\(var-set\s+(\S+)", body))
            errors_used = set(re.findall(r"(ERR_[A-Z_0-9]+)", body))
            constants_used = (
                set(re.findall(r"\b([A-Z][A-Z_0-9]+)\b", body)) - errors_used
            )

            # Llamadas a funciones del propio contrato (filtrar builtins)
            raw_calls = set(re.findall(r"\(([a-z][a-z0-9\-!?]+)[\s\)]", body))
            calls = raw_calls - CLARITY_BUILTINS - {func_name}

            result["functions"].append(
                {
                    "name": func_name,
                    "type": func_type,
                    "map_reads": map_reads,
                    "map_writes": map_writes,
                    "map_deletes": map_deletes,
                    "var_reads": var_reads,
                    "var_writes": var_writes,
                    "errors_used": errors_used,
                    "constants_used": constants_used,
                    "calls": calls,
                }
            )

    return result


# ── Grafos ────────────────────────────────────────────────────────────────────


def node_attrs(kind: str, label: str | None = None, shape: str = "box") -> dict:
    attrs = {**COLORS.get(kind, {}), "style": "filled", "shape": shape}
    if label:
        attrs["label"] = label
    return attrs


def build_architecture_graph(p: dict, name: str) -> Digraph:
    """Grafo general: todos los componentes del contrato y sus relaciones."""
    g = Digraph(name=name, comment="Clarity Contract Architecture")
    g.attr(rankdir="LR", fontname="Helvetica", compound="true")

    func_names = {f["name"] for f in p["functions"]}

    # ── Cluster: Traits
    if p["traits_used"] or p["traits_impl"]:
        with g.subgraph(name="cluster_traits") as c:
            c.attr(label="Traits", style="dashed", color="#00BCD4")
            for t in p["traits_used"]:
                c.node(
                    f"trait_{t['alias']}",
                    t["alias"],
                    **node_attrs("trait", shape="ellipse"),
                )

    # ── Cluster: Storage
    with g.subgraph(name="cluster_storage") as c:
        c.attr(label="Storage", style="filled", fillcolor="#F3E5F5", color="#9C27B0")
        for m in p["maps"]:
            c.node(f"map_{m}", f"🗺 {m}", **node_attrs("map"))
        for v in p["data_vars"]:
            c.node(f"var_{v}", f"📦 {v}", **node_attrs("data-var"))
        for tok in p["tokens"]:
            c.node(f"tok_{tok}", f"🪙 {tok}", **node_attrs("token"))

    # ── Cluster: Constants & Errors
    with g.subgraph(name="cluster_constants") as c:
        c.attr(
            label="Constants / Errors",
            style="filled",
            fillcolor="#ECEFF1",
            color="#607D8B",
        )
        for cn in p["constants"]:
            c.node(f"const_{cn}", cn, **node_attrs("constant"))
        for er in p["errors"]:
            c.node(f"err_{er}", er, **node_attrs("error"))

    # ── Cluster: Functions
    with g.subgraph(name="cluster_functions") as c:
        c.attr(label="Functions", style="filled", fillcolor="#E8F5E9", color="#4CAF50")
        for f in p["functions"]:
            label = f["name"]
            c.node(f"fn_{f['name']}", label, **node_attrs(f["type"]))

    # ── Edges: map accesses
    for f in p["functions"]:
        fn_node = f"fn_{f['name']}"
        for m in f["map_reads"]:
            if m in p["maps"]:
                g.edge(
                    fn_node, f"map_{m}", style="dashed", color="#9C27B0", label="read"
                )
        for m in f["map_writes"]:
            if m in p["maps"]:
                g.edge(fn_node, f"map_{m}", color="#9C27B0", label="write")
        for m in f["map_deletes"]:
            if m in p["maps"]:
                g.edge(fn_node, f"map_{m}", color="#F44336", label="delete")
        for v in f["var_reads"]:
            if v in p["data_vars"]:
                g.edge(
                    fn_node, f"var_{v}", style="dashed", color="#E91E63", label="read"
                )
        for v in f["var_writes"]:
            if v in p["data_vars"]:
                g.edge(fn_node, f"var_{v}", color="#E91E63", label="write")

    # ── Edges: function calls
    for f in p["functions"]:
        fn_node = f"fn_{f['name']}"
        for called in f["calls"]:
            if called in func_names:
                g.edge(fn_node, f"fn_{called}", color="#555555", arrowsize="0.7")

    # ── Edges: errores usados
    for f in p["functions"]:
        fn_node = f"fn_{f['name']}"
        for er in f["errors_used"]:
            if er in p["errors"]:
                g.edge(
                    fn_node,
                    f"err_{er}",
                    style="dotted",
                    color="#F44336",
                    arrowsize="0.6",
                )

    return g


def build_call_graph(p: dict, name: str) -> Digraph:
    """Grafo de llamadas entre funciones."""
    g = Digraph(name=name + "_calls", comment="Call Graph")
    g.attr(rankdir="TB", fontname="Helvetica")

    func_names = {f["name"] for f in p["functions"]}

    for f in p["functions"]:
        g.node(f"fn_{f['name']}", f["name"], **node_attrs(f["type"]))

    for f in p["functions"]:
        for called in f["calls"]:
            if called in func_names:
                g.edge(f"fn_{f['name']}", f"fn_{called}")

    return g


def build_data_flow_graph(p: dict, name: str) -> Digraph:
    """Grafo de acceso a datos: funciones ↔ maps/vars."""
    g = Digraph(name=name + "_data", comment="Data Access Graph")
    g.attr(rankdir="LR", fontname="Helvetica")

    storage_ids = set()
    for m in p["maps"]:
        nid = f"map_{m}"
        g.node(nid, f"MAP\n{m}", **node_attrs("map"))
        storage_ids.add(m)
    for v in p["data_vars"]:
        nid = f"var_{v}"
        g.node(nid, f"VAR\n{v}", **node_attrs("data-var"))
        storage_ids.add(v)

    for f in p["functions"]:
        fn_id = f"fn_{f['name']}"
        g.node(fn_id, f["name"], **node_attrs(f["type"]))

        for m in f["map_reads"]:
            if m in p["maps"]:
                g.edge(f"map_{m}", fn_id, style="dashed", color="#9C27B0", label="read")
        for m in f["map_writes"]:
            if m in p["maps"]:
                g.edge(fn_id, f"map_{m}", color="#9C27B0", label="write")
        for m in f["map_deletes"]:
            if m in p["maps"]:
                g.edge(fn_id, f"map_{m}", color="#F44336", label="delete")
        for v in f["var_reads"]:
            if v in p["data_vars"]:
                g.edge(f"var_{v}", fn_id, style="dashed", color="#E91E63", label="read")
        for v in f["var_writes"]:
            if v in p["data_vars"]:
                g.edge(fn_id, f"var_{v}", color="#E91E63", label="write")

    return g


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Clarity contract visualizer")
    ap.add_argument("contract", help="Ruta al archivo .clar")
    ap.add_argument(
        "--output", "-o", default=None, help="Nombre base de salida (sin extensión)"
    )
    ap.add_argument(
        "--format",
        "-f",
        default="svg",
        choices=["svg", "png", "pdf"],
        help="Formato de salida",
    )
    ap.add_argument(
        "--graph",
        "-g",
        default="all",
        choices=["all", "arch", "calls", "data"],
        help="Tipo de grafo: all | arch | calls | data",
    )
    ap.add_argument(
        "--view", "-v", action="store_true", help="Abrir el grafo automáticamente"
    )
    args = ap.parse_args()

    src = Path(args.contract)
    if not src.exists():
        sys.exit(f"❌  Archivo no encontrado: {src}")

    code = src.read_text(encoding="utf-8")
    parsed = parse_contract(code)
    base_name = args.output or src.stem

    # Resumen en consola
    print(f"\n📄  Contrato: {src.name}")
    print(f"   traits usados : {len(parsed['traits_used'])}")
    print(f"   constantes    : {len(parsed['constants'])}")
    print(f"   errores       : {len(parsed['errors'])}")
    print(f"   maps          : {len(parsed['maps'])}")
    print(f"   data-vars     : {len(parsed['data_vars'])}")
    print(f"   tokens        : {len(parsed['tokens'])}")
    print(f"   funciones     : {len(parsed['functions'])}")
    for f in parsed["functions"]:
        tag = {"public": "🟢", "read-only": "🔵", "private": "🟠"}.get(f["type"], "⚪")
        print(
            f"      {tag} {f['name']}  maps_r={len(f['map_reads'])} maps_w={len(f['map_writes'])} calls={len(f['calls'])}"
        )
    print()

    graphs_to_render = {
        "arch": (build_architecture_graph, "Arquitectura"),
        "calls": (build_call_graph, "Call graph"),
        "data": (build_data_flow_graph, "Data flow"),
    }
    selected = list(graphs_to_render.keys()) if args.graph == "all" else [args.graph]

    for key in selected:
        builder, label = graphs_to_render[key]
        g = builder(parsed, base_name)
        out_path = f"{base_name}_{key}"
        g.render(out_path, format=args.format, cleanup=True, view=args.view)
        print(f"✅  {label:15s} → {out_path}.{args.format}")

    print("\nDone.")


main()
