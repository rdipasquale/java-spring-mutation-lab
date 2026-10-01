#!/usr/bin/env python3
"""Convierte la salida de PIT / mutmut / Stryker a un esquema único.

El punto no es solo unificar campos: es darle a cada mutante una huella
(`fingerprint`) que sobreviva a los refactors. Si identificás mutantes por
archivo+línea, el primer `black` o el primer método que se mueve 20 líneas
te invalida todo el historial de triage y volvés a reportar como "nuevo"
algo que ya revisaste y descartaste.

La huella se calcula sobre (archivo, símbolo que lo contiene, operador,
ordinal del operador dentro del símbolo). Mover una función de lugar no
la cambia; renombrarla sí, y eso está bien, porque renombrar una función
suele significar que cambió su contrato.

Uso:
    python3 normalize.py --tool pit    --input target/pit-reports
    python3 normalize.py --tool stryker --input StrykerOutput
    python3 normalize.py --tool mutmut  --input .  --source-root src
"""
import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

SCHEMA = "mutants/1"

# Estados canónicos.
KILLED, SURVIVED, TIMEOUT, NO_COVERAGE, ERROR = (
    "killed", "survived", "timeout", "no_coverage", "error"
)


# --------------------------------------------------------------------------
# Resolución del símbolo que contiene una línea
# --------------------------------------------------------------------------

class SymbolIndex:
    """Dice qué función/método contiene una línea dada. Cachea por archivo."""

    def __init__(self, repo_root: Path):
        self.root = Path(repo_root)
        self._cache = {}

    def enclosing(self, relpath: str, line: int) -> str:
        if relpath not in self._cache:
            self._cache[relpath] = self._build(relpath)
        spans = self._cache[relpath]
        best = None
        for start, end, name in spans:
            if start <= line <= end:
                # el span más chico que contiene la línea = el más anidado
                if best is None or (end - start) < (best[1] - best[0]):
                    best = (start, end, name)
        return best[2] if best else "<module>"

    def _build(self, relpath):
        path = self.root / relpath
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        if path.suffix == ".py":
            return self._python_spans(text)
        if path.suffix in (".java", ".cs", ".kt"):
            return self._brace_spans(text)
        return []

    @staticmethod
    def _python_spans(text):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        spans = []

        def visit(node, prefix=""):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f"{prefix}{child.name}"
                    end = getattr(child, "end_lineno", child.lineno)
                    spans.append((child.lineno, end, name))
                    visit(child, prefix=f"{name}.")
                else:
                    visit(child, prefix=prefix)

        visit(tree)
        return spans

    # Para Java/C# no vale la pena meter un parser completo: alcanza con
    # ubicar declaraciones de método y balancear llaves desde ahí.
    DECL = re.compile(
        r"^\s*(?:(?:public|private|protected|internal|static|final|abstract|"
        r"virtual|override|async|sealed|partial|synchronized|native|unsafe)\s+)*"
        r"[\w<>\[\],.?\s]+\s+(\w+)\s*\([^;{]*\)\s*(?:\w[\w\s,.<>]*)?\{",
        re.M,
    )

    @classmethod
    def _brace_spans(cls, text):
        lines = text.splitlines()
        spans = []
        for m in cls.DECL.finditer(text):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch", "using", "lock", "do"):
                continue
            start_line = text[: m.start()].count("\n") + 1
            depth, end_line = 0, start_line
            started = False
            for i in range(start_line - 1, len(lines)):
                depth += lines[i].count("{") - lines[i].count("}")
                if "{" in lines[i]:
                    started = True
                if started and depth <= 0:
                    end_line = i + 1
                    break
            else:
                end_line = len(lines)
            spans.append((start_line, end_line, name))
        return spans


def fingerprint(relpath, symbol, operator, ordinal):
    raw = f"{relpath}|{symbol}|{operator}|{ordinal}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def assign_fingerprints(mutants, index: SymbolIndex):
    """Resuelve símbolo y ordinal, y estampa la huella.

    El ordinal es la posición del mutante entre los de su mismo operador
    dentro del mismo símbolo, ordenados por línea. Así, si la función se
    mueve entera, la huella no cambia.
    """
    for m in mutants:
        if not m.get("symbol"):
            m["symbol"] = index.enclosing(m["file"], m.get("line") or 0)

    buckets = defaultdict(list)
    for m in mutants:
        buckets[(m["file"], m["symbol"], m["operator"])].append(m)

    for (relpath, symbol, operator), group in buckets.items():
        group.sort(key=lambda x: (x.get("line") or 0, x.get("column") or 0))
        for i, m in enumerate(group):
            m["ordinal"] = i
            m["fingerprint"] = fingerprint(relpath, symbol, operator, i)
    return mutants


# --------------------------------------------------------------------------
# PIT (Java)
# --------------------------------------------------------------------------

PIT_STATUS = {
    "KILLED": KILLED, "SURVIVED": SURVIVED, "TIMED_OUT": TIMEOUT,
    "NO_COVERAGE": NO_COVERAGE, "NON_VIABLE": ERROR, "MEMORY_ERROR": ERROR,
    "RUN_ERROR": ERROR,
}


def parse_pit(input_path: Path, repo_root: Path):
    xmls = list(input_path.rglob("mutations.xml")) if input_path.is_dir() else [input_path]
    if not xmls:
        raise SystemExit(f"no se encontró mutations.xml bajo {input_path}")
    mutants = []
    for xml in xmls:
        root = ET.parse(xml).getroot()
        for node in root.iter("mutation"):
            def txt(tag):
                el = node.find(tag)
                return (el.text or "").strip() if el is not None and el.text else ""

            mutated_class = txt("mutatedClass")
            source_file = txt("sourceFile")
            relpath = _pit_relpath(repo_root, mutated_class, source_file)
            operator = txt("mutator").split(".")[-1]
            killing = txt("killingTest")
            mutants.append({
                "file": relpath,
                "line": int(txt("lineNumber") or 0),
                "column": None,
                "symbol": txt("mutatedMethod") or None,
                "operator": operator,
                "description": txt("description"),
                "original": None,
                "mutated": None,
                "status": PIT_STATUS.get((node.get("status") or "").upper(), ERROR),
                "killing_tests": [killing] if killing else [],
                "tool": "pit",
            })
    return mutants


def _pit_relpath(repo_root: Path, mutated_class: str, source_file: str):
    """PIT da la clase y el nombre del archivo; reconstruimos la ruta real."""
    if not source_file:
        return mutated_class.replace(".", "/") + ".java"
    pkg = mutated_class.rsplit(".", 1)[0].replace(".", "/") if "." in mutated_class else ""
    guess = f"{pkg}/{source_file}" if pkg else source_file
    for base in ("src/main/java", "src/main/kotlin", "src/main/scala", ""):
        cand = repo_root / base / guess if base else repo_root / guess
        if cand.exists():
            return str(cand.relative_to(repo_root))
    matches = list(repo_root.rglob(source_file))
    if matches:
        return str(matches[0].relative_to(repo_root))
    return guess


# --------------------------------------------------------------------------
# Stryker (.NET)
# --------------------------------------------------------------------------

STRYKER_STATUS = {
    "killed": KILLED, "survived": SURVIVED, "timeout": TIMEOUT,
    "nocoverage": NO_COVERAGE, "compileerror": ERROR, "runtimeerror": ERROR,
    "ignored": ERROR, "pending": ERROR,
}


def parse_stryker(input_path: Path, repo_root: Path):
    if input_path.is_dir():
        reports = sorted(input_path.rglob("mutation-report.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            reports = sorted(input_path.rglob("*.json"),
                             key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            raise SystemExit(f"no se encontró mutation-report.json bajo {input_path}")
        report_path = reports[0]
    else:
        report_path = input_path

    data = json.loads(report_path.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    test_index = _stryker_tests(data)

    mutants = []
    for relpath, info in files.items():
        norm = _relativize(relpath, repo_root)
        for mut in info.get("mutants", []):
            loc = (mut.get("location") or {}).get("start") or {}
            killers = [test_index.get(t, t) for t in (mut.get("killedBy") or [])]
            mutants.append({
                "file": norm,
                "line": loc.get("line") or 0,
                "column": loc.get("column"),
                "symbol": None,
                "operator": mut.get("mutatorName") or "unknown",
                "description": mut.get("description") or "",
                "original": None,
                "mutated": mut.get("replacement"),
                "status": STRYKER_STATUS.get((mut.get("status") or "").lower().replace(" ", ""), ERROR),
                "killing_tests": killers,
                "tool": "stryker",
            })
    return mutants


def _stryker_tests(data):
    index = {}
    for tfile in (data.get("testFiles") or {}).values():
        for t in tfile.get("tests", []):
            if t.get("id") is not None:
                index[str(t["id"])] = t.get("name") or str(t["id"])
    return index


# --------------------------------------------------------------------------
# mutmut (Python)
# --------------------------------------------------------------------------

def parse_mutmut(input_path: Path, repo_root: Path, cwd=None):
    """mutmut no tiene salida machine-readable estable entre 2.x y 3.x.

    Estrategia: pedirle `mutmut results` y parsear ambos formatos conocidos.
    Es el eslabón más frágil de los tres; si el parseo falla, conviene
    cambiar a cosmic-ray, que persiste todo en SQLite.
    """
    cwd = cwd or str(repo_root)
    try:
        proc = subprocess.run(["mutmut", "results"], cwd=cwd,
                              capture_output=True, text=True, timeout=300)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise SystemExit(f"no se pudo ejecutar `mutmut results`: {e}")
    text = proc.stdout or ""
    mutants = _parse_mutmut_v3(text, repo_root) or _parse_mutmut_v2(text, repo_root)
    if not mutants and text.strip():
        raise SystemExit(
            "no se pudo interpretar la salida de `mutmut results`.\n"
            "Salida cruda:\n" + text[:2000]
        )
    return mutants


V3_STATUS = {
    "killed": KILLED, "survived": SURVIVED, "timeout": TIMEOUT,
    "suspicious": SURVIVED, "no tests": NO_COVERAGE, "not checked": ERROR,
    "skipped": ERROR, "check was interrupted by user": ERROR,
}

# mutmut 3.x: "src.calc.x_descuento__mutmut_3: survived"
V3_LINE = re.compile(r"^([\w.]+?)__mutmut_(\d+)\s*:\s*(.+)$")


def _parse_mutmut_v3(text, repo_root: Path):
    mutants = []
    for line in text.splitlines():
        m = V3_LINE.match(line.strip())
        if not m:
            continue
        dotted, idx, status = m.group(1), int(m.group(2)), m.group(3).strip().lower()
        relpath, symbol = _mutmut_split(dotted, repo_root)
        mutants.append({
            "file": relpath, "line": 0, "column": None, "symbol": symbol,
            "operator": "mutmut", "description": f"{dotted}__mutmut_{idx}",
            "original": None, "mutated": None,
            "status": V3_STATUS.get(status, ERROR),
            "killing_tests": [], "tool": "mutmut", "mutmut_id": f"{dotted}__mutmut_{idx}",
            "ordinal_hint": idx,
        })
    return mutants


# mutmut 2.x: bloques "Survived 🙁 (2)" y luego "---- src/calc.py (2) ----" + "1-2"
V2_HEADER = re.compile(r"^(\w[\w ]*?)\s*[^\w\s]*\s*\((\d+)\)\s*$")
V2_FILE = re.compile(r"^-+\s*(.+?)\s*\(\d+\)\s*-+$")


def _parse_mutmut_v2(text, repo_root: Path):
    mutants, status, relpath = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        fm = V2_FILE.match(line)
        if fm:
            relpath = fm.group(1)
            continue
        hm = V2_HEADER.match(line)
        if hm and hm.group(1).strip().lower() in V3_STATUS:
            status = V3_STATUS[hm.group(1).strip().lower()]
            relpath = None
            continue
        if relpath and status and re.fullmatch(r"[\d,\s-]+", line):
            for token in line.replace(" ", "").split(","):
                if not token:
                    continue
                if "-" in token:
                    a, b = token.split("-", 1)
                    ids = range(int(a), int(b) + 1)
                else:
                    ids = [int(token)]
                for i in ids:
                    mutants.append({
                        "file": relpath, "line": 0, "column": None, "symbol": None,
                        "operator": "mutmut", "description": f"{relpath}#{i}",
                        "original": None, "mutated": None, "status": status,
                        "killing_tests": [], "tool": "mutmut", "mutmut_id": str(i),
                        "ordinal_hint": i,
                    })
    return mutants


def _mutmut_split(dotted, repo_root: Path):
    """'src.calc.x_descuento' -> ('src/calc.py', 'descuento')"""
    parts = dotted.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        cand = Path(*parts[:cut]).with_suffix(".py")
        if (repo_root / cand).exists():
            symbol = ".".join(parts[cut:])
            return str(cand), re.sub(r"^x_", "", symbol) or "<module>"
    return str(Path(*parts[:-1]).with_suffix(".py")), re.sub(r"^x_", "", parts[-1])


# --------------------------------------------------------------------------

def _relativize(path, repo_root: Path):
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(repo_root))
        except ValueError:
            return str(p)
    return str(p)


def summarize(mutants):
    counts = defaultdict(int)
    for m in mutants:
        counts[m["status"]] += 1
    considered = counts[KILLED] + counts[SURVIVED] + counts[TIMEOUT]
    detected = counts[KILLED] + counts[TIMEOUT]
    total_covered = considered + counts[NO_COVERAGE]
    return {
        "total": len(mutants),
        "by_status": dict(counts),
        # Score clásico: sobre mutantes cubiertos. Infla el número.
        "mutation_score": round(100 * detected / considered, 2) if considered else None,
        # Score real: castiga el código sin cobertura. Es el que hay que mirar.
        "mutation_score_covered": round(100 * detected / total_covered, 2) if total_covered else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True, choices=["pit", "mutmut", "stryker"])
    ap.add_argument("--input", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    input_path = Path(args.input)

    if args.tool == "pit":
        mutants = parse_pit(input_path, repo_root)
    elif args.tool == "stryker":
        mutants = parse_stryker(input_path, repo_root)
    else:
        mutants = parse_mutmut(input_path, repo_root)

    assign_fingerprints(mutants, SymbolIndex(repo_root))
    report = {
        "schema": SCHEMA,
        "tool": args.tool,
        "repo_root": str(repo_root),
        "summary": summarize(mutants),
        "mutants": mutants,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(json.dumps({"written": args.out, "summary": report["summary"]},
                         indent=2, ensure_ascii=False))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
