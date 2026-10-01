#!/usr/bin/env python3
"""Memoria persistente del triage de mutantes.

Sin esto, cada corrida te vuelve a mostrar los mismos 40 sobrevivientes que
ya miraste y descartaste, y la skill se vuelve insoportable a la segunda
semana. El ledger recuerda qué decidiste sobre cada mutante (por huella) y
divide la corrida nueva en: nuevos / ya triados / resueltos / regresiones.

Vive en `.mutation-ledger.json` en la raíz del repo y conviene commitearlo:
el triage es conocimiento del equipo, no estado local.

Uso:
    python3 ledger.py diff   --report mutants.json [--ledger .mutation-ledger.json]
    python3 ledger.py record --report mutants.json --triage triage.json
    python3 ledger.py show   --status equivalent
"""
import argparse
import json
import sys
import time
from pathlib import Path

LEDGER_SCHEMA = "mutation-ledger/1"

# Categorías de triage. Cada una implica una acción distinta; ver
# references/triage.md para cómo distinguirlas.
CATEGORIES = {
    "equivalente",        # no cambia comportamiento observable -> suprimir
    "codigo-muerto",      # la rama no debería existir -> borrar código
    "sin-asercion",       # se ejecuta y nadie chequea -> fortalecer test existente
    "hueco-real",         # falta un caso de comportamiento -> test nuevo
    "fuera-de-alcance",   # no vale la pena (logging, glue) -> suprimir con nota
    "pendiente",          # todavía no lo miré
}

SUPPRESSED = {"equivalente", "fuera-de-alcance"}


def load(path: Path):
    if not path.exists():
        return {"schema": LEDGER_SCHEMA, "entries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("entries", {})
    return data


def save(path: Path, data):
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _alive(m):
    return m["status"] in ("survived", "no_coverage")


def diff(report, ledger):
    """Separa la corrida actual contra lo que ya sabíamos."""
    entries = ledger["entries"]
    current = {m["fingerprint"]: m for m in report["mutants"]}

    nuevos, ya_triados, suprimidos, regresiones = [], [], [], []
    for fp, m in current.items():
        prev = entries.get(fp)
        if not _alive(m):
            # Estaba vivo y ahora muere: alguien escribió el test. Buena noticia.
            if prev and prev.get("last_status") in ("survived", "no_coverage"):
                regresiones.append({"fingerprint": fp, "mutant": m,
                                    "direction": "resuelto",
                                    "was": prev["last_status"], "now": m["status"]})
            continue
        if prev is None or prev.get("category", "pendiente") == "pendiente":
            nuevos.append(m)
        elif prev["category"] in SUPPRESSED:
            suprimidos.append({"mutant": m, "category": prev["category"],
                               "note": prev.get("note", "")})
        else:
            # Lo triamos como algo a arreglar y sigue vivo: deuda declarada.
            ya_triados.append({"mutant": m, "category": prev["category"],
                               "note": prev.get("note", ""),
                               "first_seen": prev.get("first_seen")})

    # Mutantes que el ledger conocía vivos y que ya no aparecen: el código
    # cambió. No es un logro, es que desapareció el terreno.
    desaparecidos = [
        {"fingerprint": fp, "entry": e}
        for fp, e in entries.items()
        if fp not in current and e.get("last_status") in ("survived", "no_coverage")
    ]

    return {
        "nuevos": nuevos,
        "ya_triados": ya_triados,
        "suprimidos": suprimidos,
        "resueltos": regresiones,
        "desaparecidos": desaparecidos,
        "counts": {
            "nuevos": len(nuevos), "ya_triados": len(ya_triados),
            "suprimidos": len(suprimidos), "resueltos": len(regresiones),
            "desaparecidos": len(desaparecidos),
        },
    }


def record(report, ledger, triage):
    """Graba decisiones de triage. `triage` es {fingerprint: {category, note}}."""
    entries = ledger["entries"]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    current = {m["fingerprint"]: m for m in report["mutants"]}
    applied, rejected = 0, []

    for fp, decision in triage.items():
        cat = decision.get("category", "pendiente")
        if cat not in CATEGORIES:
            rejected.append({"fingerprint": fp, "reason": f"categoría inválida: {cat}"})
            continue
        if fp not in current:
            rejected.append({"fingerprint": fp, "reason": "no está en el reporte actual"})
            continue
        m = current[fp]
        prev = entries.get(fp, {})
        entries[fp] = {
            "file": m["file"], "symbol": m["symbol"], "operator": m["operator"],
            "ordinal": m["ordinal"],
            "category": cat,
            "note": decision.get("note", ""),
            "proposed_test": decision.get("proposed_test"),
            "last_status": m["status"],
            "first_seen": prev.get("first_seen", now),
            "last_seen": now,
        }
        applied += 1

    # Refrescamos el estado de todo lo que ya estaba, aunque no se trie ahora.
    for fp, m in current.items():
        if fp in entries and fp not in triage:
            entries[fp]["last_status"] = m["status"]
            entries[fp]["last_seen"] = now

    return {"applied": applied, "rejected": rejected, "total_entries": len(entries)}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("diff")
    d.add_argument("--report", required=True)
    d.add_argument("--ledger", default=".mutation-ledger.json")

    r = sub.add_parser("record")
    r.add_argument("--report", required=True)
    r.add_argument("--triage", required=True)
    r.add_argument("--ledger", default=".mutation-ledger.json")

    s = sub.add_parser("show")
    s.add_argument("--ledger", default=".mutation-ledger.json")
    s.add_argument("--category", default=None)

    args = ap.parse_args()
    ledger_path = Path(args.ledger)
    ledger = load(ledger_path)

    if args.cmd == "show":
        entries = ledger["entries"]
        if args.category:
            entries = {k: v for k, v in entries.items() if v.get("category") == args.category}
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return 0

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))

    if args.cmd == "diff":
        print(json.dumps(diff(report, ledger), indent=2, ensure_ascii=False))
        return 0

    triage = json.loads(Path(args.triage).read_text(encoding="utf-8"))
    if isinstance(triage, dict) and "decisions" in triage:
        triage = triage["decisions"]
    result = record(report, ledger, triage)
    save(ledger_path, ledger)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["rejected"] else 1


if __name__ == "__main__":
    sys.exit(main())
