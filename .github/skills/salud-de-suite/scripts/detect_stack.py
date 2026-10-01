#!/usr/bin/env python3
"""Detecta lenguaje, build tool y comando de pruebas unitarias de un proyecto.

Salida: JSON por stdout. Es el contrato que consumen tanto suite_health.py
como la skill caza-de-mutantes.

Uso:
    python3 detect_stack.py [--root .] [--module <path>]
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Directorios que nunca son parte del proyecto del usuario.
IGNORE = {
    ".git", "node_modules", "venv", ".venv", "env", "target", "build", "bin",
    "obj", "dist", ".tox", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".idea", ".vs", ".gradle", "site-packages",
}


def walk(root: Path, max_depth: int = 4):
    """Recorre el árbol salteando ruido, con tope de profundidad."""
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in IGNORE and not d.startswith(".")]
        yield Path(dirpath), filenames


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


# --------------------------------------------------------------------------
# Java
# --------------------------------------------------------------------------

def detect_java(root: Path):
    poms, gradles = [], []
    for dirpath, filenames in walk(root):
        for f in filenames:
            if f == "pom.xml":
                poms.append(dirpath / f)
            elif f in ("build.gradle", "build.gradle.kts"):
                gradles.append(dirpath / f)
    if not poms and not gradles:
        return None

    if poms:
        root_pom = min(poms, key=lambda p: len(p.parts))
        modules = _maven_modules(root_pom)
        junit5 = _maven_uses_junit5(poms)
        return {
            "language": "java",
            "build_tool": "maven",
            "project_root": str(root_pom.parent),
            "manifest": str(root_pom),
            "modules": modules,
            "multi_module": bool(modules),
            "junit_version": 5 if junit5 else 4,
            "test_command": ["mvn", "-B", "test"],
            "test_results_glob": "**/target/surefire-reports/TEST-*.xml",
            "test_results_format": "junit-xml",
            "source_dirs": ["src/main/java"],
            "test_dirs": ["src/test/java"],
        }

    root_gradle = min(gradles, key=lambda p: len(p.parts))
    wrapper = (root_gradle.parent / "gradlew").exists()
    return {
        "language": "java",
        "build_tool": "gradle",
        "project_root": str(root_gradle.parent),
        "manifest": str(root_gradle),
        "modules": _gradle_modules(root_gradle.parent),
        "multi_module": len(gradles) > 1,
        "junit_version": 5 if _gradle_uses_junit5(gradles) else 4,
        "test_command": (["./gradlew"] if wrapper else ["gradle"]) + ["test"],
        "test_results_glob": "**/build/test-results/test/TEST-*.xml",
        "test_results_format": "junit-xml",
        "source_dirs": ["src/main/java"],
        "test_dirs": ["src/test/java"],
    }


def _maven_modules(pom: Path):
    try:
        tree = ET.parse(pom)
    except ET.ParseError:
        return []
    return [
        (m.text or "").strip()
        for m in tree.getroot().iter()
        if _strip_ns(m.tag) == "module" and m.text
    ]


def _maven_uses_junit5(poms):
    for pom in poms:
        try:
            text = pom.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "junit-jupiter" in text or "junit5" in text:
            return True
    return False


def _gradle_modules(root: Path):
    for name in ("settings.gradle", "settings.gradle.kts"):
        f = root / name
        if f.exists():
            text = f.read_text(encoding="utf-8", errors="ignore")
            return re.findall(r"include\s*\(?\s*['\"]:?([^'\"]+)['\"]", text)
    return []


def _gradle_uses_junit5(gradles):
    for g in gradles:
        text = g.read_text(encoding="utf-8", errors="ignore")
        if "junit-jupiter" in text or "useJUnitPlatform" in text:
            return True
    return False


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------

PY_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "pytest.ini")


def detect_python(root: Path):
    marker = None
    for dirpath, filenames in walk(root):
        for m in PY_MARKERS:
            if m in filenames:
                cand = dirpath / m
                if marker is None or len(cand.parts) < len(marker.parts):
                    marker = cand
    if marker is None:
        py_files = [
            dirpath / f
            for dirpath, filenames in walk(root)
            for f in filenames
            if f.endswith(".py")
        ]
        if not py_files:
            return None
        marker = root / "pyproject.toml"  # inexistente, pero fija la raíz

    proj = marker.parent
    runner = _python_runner(proj)
    return {
        "language": "python",
        "build_tool": runner["build_tool"],
        "project_root": str(proj),
        "manifest": str(marker) if marker.exists() else None,
        "modules": [],
        "multi_module": False,
        "test_runner": runner["runner"],
        "test_command": runner["command"],
        "test_results_glob": None,  # se genera on demand con --junit-xml
        "test_results_format": "junit-xml",
        "source_dirs": _python_source_dirs(proj),
        "test_dirs": _python_test_dirs(proj),
        "venv": _python_venv(proj),
    }


def _python_runner(proj: Path):
    pyproject = proj / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8", errors="ignore") if pyproject.exists() else ""
    if "[tool.poetry]" in text:
        return {"build_tool": "poetry", "runner": "pytest",
                "command": ["poetry", "run", "pytest"]}
    if (proj / "uv.lock").exists() or "[tool.uv]" in text:
        return {"build_tool": "uv", "runner": "pytest",
                "command": ["uv", "run", "pytest"]}
    if (proj / "Pipfile").exists():
        return {"build_tool": "pipenv", "runner": "pytest",
                "command": ["pipenv", "run", "pytest"]}
    runner = "pytest"
    if not text and (proj / "pytest.ini").exists() is False:
        # Sin señales de pytest, unittest sigue siendo un default razonable,
        # pero pytest corre tests de unittest igual, así que lo preferimos.
        runner = "pytest"
    return {"build_tool": "pip", "runner": runner,
            "command": [sys.executable or "python3", "-m", "pytest"]}


def _python_source_dirs(proj: Path):
    dirs = []
    if (proj / "src").is_dir():
        dirs.append("src")
    for child in sorted(proj.iterdir()):
        if (child.is_dir() and child.name not in IGNORE
                and child.name not in dirs
                and not child.name.startswith(".")
                and (child / "__init__.py").exists()):
            dirs.append(child.name)
    return dirs or ["."]


def _python_test_dirs(proj: Path):
    return [d for d in ("tests", "test") if (proj / d).is_dir()] or ["tests"]


def _python_venv(proj: Path):
    if os.environ.get("VIRTUAL_ENV"):
        return os.environ["VIRTUAL_ENV"]
    for name in (".venv", "venv"):
        if (proj / name / "bin" / "python").exists() or (proj / name / "Scripts" / "python.exe").exists():
            return str(proj / name)
    return None


# --------------------------------------------------------------------------
# .NET
# --------------------------------------------------------------------------

def detect_dotnet(root: Path):
    slns, csprojs = [], []
    for dirpath, filenames in walk(root):
        for f in filenames:
            if f.endswith((".sln", ".slnx")):
                slns.append(dirpath / f)
            elif f.endswith((".csproj", ".fsproj", ".vbproj")):
                csprojs.append(dirpath / f)
    if not slns and not csprojs:
        return None

    test_projects, src_projects = [], []
    for p in csprojs:
        (test_projects if _is_test_project(p) else src_projects).append(str(p))

    if slns:
        entry = min(slns, key=lambda p: len(p.parts))
    else:
        entry = min(csprojs, key=lambda p: len(p.parts))

    return {
        "language": "dotnet",
        "build_tool": "dotnet",
        "project_root": str(entry.parent),
        "manifest": str(entry),
        "modules": [os.path.basename(p) for p in src_projects],
        "multi_module": len(src_projects) > 1,
        "test_projects": test_projects,
        "source_projects": src_projects,
        "test_command": ["dotnet", "test", str(entry)],
        "test_results_glob": "**/TestResults/*.trx",
        "test_results_format": "trx",
        "source_dirs": [],
        "test_dirs": [],
    }


TEST_PKG = re.compile(
    r"(Microsoft\.NET\.Test\.Sdk|xunit|NUnit|MSTest\.TestFramework)", re.I
)


def _is_test_project(csproj: Path) -> bool:
    try:
        text = csproj.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if TEST_PKG.search(text):
        return True
    return bool(re.search(r"(test|spec)s?\.(cs|fs|vb)proj$", csproj.name, re.I))


# --------------------------------------------------------------------------

DETECTORS = (detect_java, detect_python, detect_dotnet)


def detect(root: Path):
    found = [d(root) for d in DETECTORS]
    found = [f for f in found if f]
    if not found:
        return {"detected": False, "reason": "no se reconoció java, python ni .net",
                "candidates": []}
    primary = found[0]
    primary["detected"] = True
    primary["other_stacks"] = [f["language"] for f in found[1:]]
    return primary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    result = detect(Path(args.root))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("detected") else 1


if __name__ == "__main__":
    sys.exit(main())
