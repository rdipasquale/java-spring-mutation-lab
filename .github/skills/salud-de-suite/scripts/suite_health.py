#!/usr/bin/env python3
"""Mide la salud de una suite de pruebas unitarias antes de confiar en ella.

Corre la suite N veces, compara los resultados test por test y reporta:
  - si pasa en verde
  - qué tests son intermitentes (verde en una corrida, rojo en otra)
  - cuánto tarda (necesario para calcular timeouts de mutación)
  - cuántos tests hay y si alguno quedó ignorado

Salida: JSON a stdout y, si se pasa --out, también a un archivo.

Uso:
    python3 suite_health.py --root . --runs 2
"""
import argparse
import glob
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from detect_stack import detect  # noqa: E402


def _strip_ns(tag):
    return tag.split("}")[-1]


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------

def build_command(stack, results_dir: Path):
    """Comando de test con reporte machine-readable forzado."""
    cmd = list(stack["test_command"])
    if stack["language"] == "python":
        cmd += ["--junit-xml", str(results_dir / "pytest.xml"), "-q"]
    elif stack["language"] == "dotnet":
        cmd += ["--logger", f"trx;LogFileName={results_dir / 'results.trx'}"]
    return cmd


def run_once(stack, run_idx, results_root: Path, timeout: int):
    results_dir = results_root / f"run-{run_idx}"
    results_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_command(stack, results_dir)
    root = stack["project_root"]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, timeout=timeout
        )
        rc, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        rc, out, err, timed_out = -1, (e.stdout or ""), (e.stderr or ""), True
    except FileNotFoundError:
        return {
            "run": run_idx, "error": f"no se encontró el ejecutable: {cmd[0]}",
            "command": cmd, "tests": {}, "duration_s": 0.0, "exit_code": 127,
        }
    duration = time.monotonic() - start

    if isinstance(out, bytes):
        out = out.decode("utf-8", "replace")
    if isinstance(err, bytes):
        err = err.decode("utf-8", "replace")

    tests = collect_results(stack, results_dir)
    return {
        "run": run_idx,
        "command": cmd,
        "exit_code": rc,
        "timed_out": timed_out,
        "duration_s": round(duration, 2),
        "tests": tests,
        "stdout_tail": out[-4000:],
        "stderr_tail": err[-4000:],
    }


# --------------------------------------------------------------------------
# Parseo de resultados
# --------------------------------------------------------------------------

def collect_results(stack, results_dir: Path):
    fmt = stack.get("test_results_format")
    if fmt == "junit-xml":
        files = sorted(glob.glob(str(results_dir / "*.xml")))
        if not files and stack.get("test_results_glob"):
            files = sorted(
                glob.glob(
                    os.path.join(stack["project_root"], stack["test_results_glob"]),
                    recursive=True,
                )
            )
        return parse_junit(files)
    if fmt == "trx":
        files = sorted(glob.glob(str(results_dir / "*.trx")))
        if not files:
            files = sorted(
                glob.glob(
                    os.path.join(stack["project_root"], "**", "TestResults", "*.trx"),
                    recursive=True,
                )
            )
        return parse_trx(files)
    return {}


def parse_junit(files):
    """JUnit XML -> {nombre_test: passed|failed|error|skipped}"""
    tests = {}
    for path in files:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for case in root.iter():
            if _strip_ns(case.tag) != "testcase":
                continue
            cls = case.get("classname") or case.get("class") or ""
            name = case.get("name") or ""
            key = f"{cls}::{name}" if cls else name
            status = "passed"
            for child in case:
                t = _strip_ns(child.tag)
                if t == "failure":
                    status = "failed"
                elif t == "error":
                    status = "error"
                elif t == "skipped":
                    status = "skipped"
            tests[key] = status
    return tests


def parse_trx(files):
    """TRX de dotnet test -> {nombre_test: passed|failed|skipped}"""
    tests = {}
    mapping = {
        "passed": "passed", "failed": "failed", "error": "error",
        "notexecuted": "skipped", "inconclusive": "skipped",
        "timeout": "error", "aborted": "error",
    }
    for path in files:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for r in root.iter():
            if _strip_ns(r.tag) != "UnitTestResult":
                continue
            name = r.get("testName") or ""
            outcome = (r.get("outcome") or "").lower()
            tests[name] = mapping.get(outcome, outcome or "unknown")
    return tests


# --------------------------------------------------------------------------
# Análisis
# --------------------------------------------------------------------------

def analyze(runs):
    """Compara corridas y arma el veredicto."""
    valid = [r for r in runs if not r.get("error")]
    all_names = set()
    for r in valid:
        all_names.update(r["tests"])

    flaky, missing = [], []
    for name in sorted(all_names):
        outcomes = [r["tests"].get(name, "__ausente__") for r in valid]
        distinct = set(outcomes)
        if "__ausente__" in distinct and len(valid) > 1:
            missing.append({"test": name, "outcomes": outcomes})
            distinct.discard("__ausente__")
        if len(distinct) > 1:
            flaky.append({"test": name, "outcomes": outcomes})

    last = valid[-1]["tests"] if valid else {}
    failing = sorted(k for k, v in last.items() if v in ("failed", "error"))
    skipped = sorted(k for k, v in last.items() if v == "skipped")

    durations = [r["duration_s"] for r in valid]
    exit_codes = [r["exit_code"] for r in valid]

    blockers = []
    if not valid:
        blockers.append("ninguna corrida se pudo ejecutar")
    if any(c != 0 for c in exit_codes):
        blockers.append(f"la suite no pasa en verde (exit codes: {exit_codes})")
    if flaky:
        blockers.append(
            f"{len(flaky)} test(s) intermitentes: los resultados de mutación serían ruido"
        )
    if missing:
        blockers.append(f"{len(missing)} test(s) aparecen en unas corridas y en otras no")
    if valid and not all_names:
        blockers.append("no se encontró ningún resultado de test — ¿la suite está vacía o el reporte no se generó?")

    warnings = []
    if len(all_names) and len(skipped) / len(all_names) > 0.1:
        warnings.append(f"{len(skipped)}/{len(all_names)} tests ignorados (skipped)")
    if durations and max(durations) > 300:
        warnings.append(
            f"la suite tarda {max(durations):.0f}s — mutación full va a ser muy cara, usá alcance por diff"
        )

    mean = statistics.mean(durations) if durations else 0.0
    return {
        "verdict": "apta" if not blockers else "no-apta",
        "blockers": blockers,
        "warnings": warnings,
        "total_tests": len(all_names),
        "failing_tests": failing[:50],
        "failing_count": len(failing),
        "skipped_count": len(skipped),
        "flaky_tests": flaky[:50],
        "flaky_count": len(flaky),
        "inconsistent_presence": missing[:20],
        "baseline_duration_s": round(mean, 2),
        "duration_spread_s": round(max(durations) - min(durations), 2) if len(durations) > 1 else 0.0,
        # Regla usual: timeout = base * factor + colchón. Es lo que evita
        # que mutantes vivos se reporten como "timeout" por ruido de máquina.
        "suggested_mutation_timeout_s": round(mean * 1.5 + 10, 1) if mean else 30.0,
    }


# --------------------------------------------------------------------------

def check_tooling(stack):
    """Avisa temprano si falta el ejecutable, antes de correr nada."""
    exe = stack["test_command"][0]
    if exe.startswith("./"):
        ok = os.access(os.path.join(stack["project_root"], exe[2:]), os.X_OK)
    else:
        ok = shutil.which(exe) is not None
    return {"executable": exe, "available": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--runs", type=int, default=2,
                    help="corridas para detectar intermitencia (2 es el mínimo útil)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out", default=None)
    ap.add_argument("--results-dir", default=None)
    args = ap.parse_args()

    stack = detect(Path(args.root))
    if not stack.get("detected"):
        report = {"schema": "suite-health/1", "stack": stack,
                  "analysis": {"verdict": "no-apta",
                               "blockers": ["no se pudo detectar el stack del proyecto"]}}
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2

    tooling = check_tooling(stack)
    if not tooling["available"]:
        report = {
            "schema": "suite-health/1", "stack": stack, "tooling": tooling,
            "analysis": {"verdict": "no-apta",
                         "blockers": [f"falta el ejecutable '{tooling['executable']}' en el PATH"]},
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2

    results_root = Path(args.results_dir or (Path(args.root) / ".suite-health"))
    results_root.mkdir(parents=True, exist_ok=True)

    runs = [run_once(stack, i, results_root, args.timeout) for i in range(1, args.runs + 1)]
    analysis = analyze(runs)

    report = {
        "schema": "suite-health/1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stack": stack,
        "tooling": tooling,
        "runs": runs,
        "analysis": analysis,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0 if analysis["verdict"] == "apta" else 1


if __name__ == "__main__":
    sys.exit(main())
