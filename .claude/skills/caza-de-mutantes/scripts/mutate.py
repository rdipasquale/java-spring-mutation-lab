#!/usr/bin/env python3
"""Prepara el worktree, verifica dependencias y corre la caza de mutantes.

Subcomandos:
    check   - ¿están las dependencias? No corre nada, solo diagnostica.
    scope   - ¿qué archivos hay que mutar? (por diff contra una base)
    run     - worktree + ejecución + limpieza garantizada

El worktree existe para que la basura que generan estas herramientas
(mutants/, StrykerOutput/, target/pit-reports/) no te toque el árbol de
trabajo, y para que una corrida de 40 minutos no te bloquee el repo.
Ojo: el worktree NO lleva archivos untracked. Si tu proyecto necesita un
.env o un venv, pasalos con --carry.

Uso:
    python3 mutate.py check --health health.json
    python3 mutate.py scope --health health.json --base origin/main
    python3 mutate.py run   --health health.json --base origin/main --timeout 45
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS = {"java": "pit", "python": "mutmut", "dotnet": "stryker"}


def sh(cmd, cwd=None, timeout=None, check=False):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise SystemExit(f"falló {' '.join(cmd)}:\n{proc.stderr[-2000:]}")
    return proc


def load_health(path):
    health = json.loads(Path(path).read_text(encoding="utf-8"))
    if health.get("analysis", {}).get("verdict") != "apta":
        raise SystemExit(
            "la suite no pasó el chequeo de salud; mutar ahora da resultados sin valor.\n"
            "Bloqueos: " + json.dumps(health.get("analysis", {}).get("blockers", []),
                                      ensure_ascii=False)
        )
    return health


# --------------------------------------------------------------------------
# check: dependencias
# --------------------------------------------------------------------------

def check_deps(stack):
    lang = stack["language"]
    if lang == "java":
        return _check_java(stack)
    if lang == "python":
        return _check_python(stack)
    return _check_dotnet(stack)


def _check_java(stack):
    root = Path(stack["project_root"])
    missing, hints = [], []
    if stack["build_tool"] == "maven":
        poms = list(root.rglob("pom.xml"))
        text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in poms)
        has_pit = "pitest-maven" in text
        has_j5 = "pitest-junit5-plugin" in text
        if not has_pit:
            hints.append(
                "PIT no está declarado. Podés correrlo sin declararlo con\n"
                "  mvn org.pitest:pitest-maven:mutationCoverage\n"
                "pero conviene fijarlo en el pom para que la versión sea reproducible."
            )
        if stack.get("junit_version") == 5 and not has_j5:
            missing.append("pitest-junit5-plugin")
            hints.append(
                "El proyecto usa JUnit 5 y falta pitest-junit5-plugin: sin él PIT\n"
                "no detecta ningún test y todos los mutantes salen SURVIVED.\n"
                "Agregá en el <plugin> de pitest-maven:\n"
                "  <dependencies><dependency>\n"
                "    <groupId>org.pitest</groupId>\n"
                "    <artifactId>pitest-junit5-plugin</artifactId>\n"
                "    <version>1.2.1</version>\n"
                "  </dependency></dependencies>"
            )
        return {"tool": "pit", "ready": not missing, "missing": missing, "hints": hints,
                "declared": has_pit}

    gradles = list(root.rglob("build.gradle*"))
    text = "\n".join(g.read_text(encoding="utf-8", errors="ignore") for g in gradles)
    has_pit = "info.solidsoft.pitest" in text or "pitest" in text
    if not has_pit:
        missing.append("plugin gradle de pitest")
        hints.append("Agregá: plugins { id 'info.solidsoft.pitest' version '1.15.0' }")
    if stack.get("junit_version") == 5 and "pitest-junit5-plugin" not in text:
        missing.append("pitest-junit5-plugin")
        hints.append("pitest { junit5PluginVersion = '1.2.1' } — sin esto no detecta tests.")
    return {"tool": "pit", "ready": not missing, "missing": missing, "hints": hints,
            "declared": has_pit}


def _check_python(stack):
    exe = shutil.which("mutmut")
    version, major = None, None
    if exe:
        p = sh(["mutmut", "version"])
        raw = (p.stdout or p.stderr or "").strip()
        if not raw or p.returncode != 0:
            p = sh(["mutmut", "--version"])
            raw = (p.stdout or p.stderr or "").strip()
        version = raw
        m = re.search(r"(\d+)\.(\d+)", raw or "")
        major = int(m.group(1)) if m else None

    missing, hints = [], []
    if not exe:
        missing.append("mutmut")
        hints.append("pip install mutmut  (o: pip install cosmic-ray, ver nota abajo)")
    if major == 2:
        hints.append("mutmut 2.x: el parseo de resultados es distinto al de 3.x. "
                     "Está contemplado, pero si falla, cosmic-ray es más predecible.")
    pyproject = Path(stack["project_root"]) / "pyproject.toml"
    configured = pyproject.exists() and "[tool.mutmut]" in pyproject.read_text(
        encoding="utf-8", errors="ignore")
    if not configured:
        hints.append(
            "Sin [tool.mutmut] en pyproject.toml, mutmut adivina qué mutar y "
            "suele incluir tests y scripts. Declaralo:\n"
            f"  [tool.mutmut]\n  paths_to_mutate = {stack.get('source_dirs', ['src'])}\n"
            f"  tests_dir = \"{(stack.get('test_dirs') or ['tests'])[0]}\""
        )
    return {"tool": "mutmut", "ready": not missing, "missing": missing, "hints": hints,
            "version": version, "major": major, "configured": configured}


def _check_dotnet(stack):
    missing, hints = [], []
    if not shutil.which("dotnet"):
        return {"tool": "stryker", "ready": False, "missing": ["dotnet"],
                "hints": ["falta el SDK de .NET"]}
    local = sh(["dotnet", "tool", "list"], cwd=stack["project_root"])
    glob = sh(["dotnet", "tool", "list", "--global"])
    listing = (local.stdout or "") + (glob.stdout or "")
    installed = "dotnet-stryker" in listing
    if not installed:
        missing.append("dotnet-stryker")
        hints.append(
            "dotnet tool install -g dotnet-stryker\n"
            "(o, mejor para reproducibilidad: dotnet new tool-manifest && "
            "dotnet tool install dotnet-stryker)"
        )
    if not stack.get("test_projects"):
        missing.append("proyecto de test")
        hints.append("No se detectó ningún .csproj de test; Stryker necesita al menos uno.")
    return {"tool": "stryker", "ready": not missing, "missing": missing,
            "hints": hints, "installed": installed}


# --------------------------------------------------------------------------
# scope: qué mutar
# --------------------------------------------------------------------------

SOURCE_EXT = {"java": (".java",), "python": (".py",), "dotnet": (".cs", ".fs", ".vb")}


def compute_scope(stack, base, repo_root):
    """Archivos fuente tocados contra la base. Es el default por costo."""
    if not base:
        return {"mode": "full", "files": [], "note": "alcance completo (caro)"}

    merge_base = sh(["git", "merge-base", base, "HEAD"], cwd=repo_root)
    ref = merge_base.stdout.strip() or base
    p = sh(["git", "diff", "--name-only", "--diff-filter=ACMR", ref, "HEAD"], cwd=repo_root)
    if p.returncode != 0:
        return {"mode": "full", "files": [],
                "note": f"no se pudo diffear contra {base}: {p.stderr.strip()[:300]}"}

    changed = [f for f in p.stdout.splitlines() if f.strip()]
    exts = SOURCE_EXT[stack["language"]]
    test_markers = ("test", "spec")
    files = [
        f for f in changed
        if f.endswith(exts)
        and not any(mk in Path(f).name.lower() for mk in test_markers)
        and not any(mk in Path(f).parts[0].lower() for mk in test_markers if Path(f).parts)
    ]
    return {"mode": "diff", "base": base, "merge_base": ref,
            "files": files, "changed_total": len(changed),
            "note": "sin archivos fuente cambiados" if not files else ""}


# --------------------------------------------------------------------------
# run: worktree + ejecución
# --------------------------------------------------------------------------

def make_worktree(repo_root, ref="HEAD", carry=()):
    path = Path(tempfile.mkdtemp(prefix="caza-mutantes-"))
    wt = path / "wt"
    p = sh(["git", "worktree", "add", "--detach", str(wt), ref], cwd=repo_root)
    if p.returncode != 0:
        shutil.rmtree(path, ignore_errors=True)
        raise SystemExit(f"no se pudo crear el worktree:\n{p.stderr[-1500:]}")
    for item in carry:
        src = Path(repo_root) / item
        if not src.exists():
            continue
        dst = wt / item
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            shutil.copy2(src, dst)
    return wt


def remove_worktree(repo_root, wt: Path):
    sh(["git", "worktree", "remove", "--force", str(wt)], cwd=repo_root)
    shutil.rmtree(wt.parent, ignore_errors=True)
    sh(["git", "worktree", "prune"], cwd=repo_root)


def build_mutation_command(stack, scope, timeout_s, wt: Path):
    lang = stack["language"]
    if lang == "java":
        return _cmd_pit(stack, scope, timeout_s)
    if lang == "python":
        return _cmd_mutmut(stack, scope, timeout_s)
    return _cmd_stryker(stack, scope, timeout_s, wt)


def _cmd_pit(stack, scope, timeout_s):
    targets = "*"
    if scope["mode"] == "diff" and scope["files"]:
        classes = sorted({
            re.sub(r"\.java$", "", f.split("src/main/java/")[-1]).replace("/", ".")
            for f in scope["files"]
        })
        targets = ",".join(classes)
    common = [
        f"-DtargetClasses={targets}",
        f"-DtimeoutConst={int(timeout_s * 1000)}",
        "-DoutputFormats=XML,HTML",
        "-DtimestampedReports=false",
    ]
    if stack["build_tool"] == "maven":
        return ["mvn", "-B", "org.pitest:pitest-maven:mutationCoverage"] + common, \
               "target/pit-reports"
    gw = "./gradlew" if (Path(stack["project_root"]) / "gradlew").exists() else "gradle"
    return [gw, "pitest"] + [c.replace("-D", "-P") for c in common], \
           "build/reports/pitest"


def _cmd_mutmut(stack, scope, timeout_s):
    cmd = ["mutmut", "run"]
    if scope["mode"] == "diff" and scope["files"]:
        cmd += ["--paths-to-mutate", ",".join(scope["files"])]
    return cmd, "."


def _cmd_stryker(stack, scope, timeout_s, wt: Path):
    cmd = ["dotnet", "stryker", "--reporter", "json", "--reporter", "progress",
           "--output", str(wt / "StrykerOutput")]
    if scope["mode"] == "diff":
        cmd += ["--since", scope.get("base", "main")]
    return cmd, "StrykerOutput"


def run(args):
    health = load_health(args.health)
    stack = health["stack"]
    repo_root = Path(stack["project_root"]).resolve()

    deps = check_deps(stack)
    if not deps["ready"] and not args.force:
        return _emit({"stage": "check", "ok": False, "deps": deps}, args.out), 2

    scope = compute_scope(stack, args.base, repo_root)
    if scope["mode"] == "diff" and not scope["files"]:
        return _emit({"stage": "scope", "ok": True, "scope": scope,
                      "note": "no hay fuentes cambiadas; nada que mutar"}, args.out), 0

    timeout_s = args.timeout or health["analysis"].get("suggested_mutation_timeout_s", 30)
    wt = make_worktree(repo_root, args.ref, carry=args.carry or [])
    started = time.monotonic()
    try:
        cmd, report_subdir = build_mutation_command(stack, scope, timeout_s, wt)
        proc = subprocess.run(cmd, cwd=wt, capture_output=True, text=True,
                              timeout=args.wall_timeout)
        elapsed = time.monotonic() - started
        report_dir = wt / report_subdir

        # El reporte vive en el worktree, que borramos enseguida: lo sacamos afuera.
        keep = Path(args.artifacts or (repo_root / ".caza-mutantes"))
        keep.mkdir(parents=True, exist_ok=True)
        saved = None
        if report_dir.exists():
            saved = keep / "raw"
            shutil.rmtree(saved, ignore_errors=True)
            shutil.copytree(report_dir, saved, dirs_exist_ok=True)

        result = {
            "stage": "run", "ok": proc.returncode == 0,
            "tool": TOOLS[stack["language"]],
            "command": cmd, "exit_code": proc.returncode,
            "elapsed_s": round(elapsed, 1),
            "mutant_timeout_s": timeout_s,
            "scope": scope,
            "worktree": str(wt),
            "raw_report_dir": str(saved) if saved else None,
            "repo_root": str(repo_root),
            "stdout_tail": (proc.stdout or "")[-6000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "next": (
                f"python3 normalize.py --tool {TOOLS[stack['language']]} "
                f"--input {saved} --repo-root {repo_root} --out {keep / 'mutants.json'}"
                if saved else "la herramienta no dejó reporte; mirá stderr_tail"
            ),
        }
        return _emit(result, args.out), (0 if saved else 1)
    except subprocess.TimeoutExpired:
        return _emit({"stage": "run", "ok": False,
                      "error": f"la corrida superó el límite de {args.wall_timeout}s",
                      "hint": "acotá el alcance con --base, o subí --wall-timeout"},
                     args.out), 1
    except FileNotFoundError as e:
        return _emit({"stage": "run", "ok": False,
                      "error": f"no se encontró el ejecutable: {e.filename}",
                      "hint": "corré `mutate.py check` sin --force y seguí las "
                              "instrucciones de instalación que devuelve"},
                     args.out), 2
    finally:
        if not args.keep_worktree:
            remove_worktree(repo_root, wt)


def _emit(obj, out):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    print(text)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    return obj


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("check", "scope", "run"):
        s = sub.add_parser(name)
        s.add_argument("--health", required=True, help="reporte de salud-de-suite")
        s.add_argument("--out", default=None)
        if name in ("scope", "run"):
            s.add_argument("--base", default=None,
                           help="rama base para acotar por diff (ej: origin/main)")
        if name == "run":
            s.add_argument("--ref", default="HEAD")
            s.add_argument("--timeout", type=float, default=None,
                           help="timeout por mutante; default viene del reporte de salud")
            s.add_argument("--wall-timeout", type=int, default=7200)
            s.add_argument("--carry", action="append", default=[],
                           help="archivo/dir untracked a copiar al worktree (repetible)")
            s.add_argument("--artifacts", default=None)
            s.add_argument("--keep-worktree", action="store_true")
            s.add_argument("--force", action="store_true")

    args = ap.parse_args()

    if args.cmd == "check":
        health = json.loads(Path(args.health).read_text(encoding="utf-8"))
        deps = check_deps(health["stack"])
        _emit({"stage": "check", "ok": deps["ready"], "deps": deps}, args.out)
        return 0 if deps["ready"] else 2

    if args.cmd == "scope":
        health = json.loads(Path(args.health).read_text(encoding="utf-8"))
        stack = health["stack"]
        scope = compute_scope(stack, args.base, Path(stack["project_root"]).resolve())
        _emit({"stage": "scope", "ok": True, "scope": scope}, args.out)
        return 0

    _, code = run(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
