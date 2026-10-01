#!/usr/bin/env python3
"""Instala los skills de .claude/skills como Agent Skills de GitHub Copilot.

La fuente de verdad sigue siendo .claude/skills; esto genera una copia
adaptada. Lo único que cambia es la resolución de rutas: los SKILL.md
invocan `python3 scripts/x.py` y citan `references/y.md` relativos a la
carpeta del skill, pero Copilot corre los comandos desde la raíz del
workspace. La copia reescribe esas rutas para que funcionen desde ahí.

Uso:
    python3 tools/install_copilot_skills.py           # -> .github/skills (se commitea)
    python3 tools/install_copilot_skills.py --user    # -> ~/.copilot/skills (solo tu máquina)
    python3 tools/install_copilot_skills.py --check   # exit 1 si .github/skills quedó desactualizado
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / ".claude" / "skills"
PROJECT_TARGET = REPO_ROOT / ".github" / "skills"
USER_TARGET = Path.home() / ".copilot" / "skills"

IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Solo rutas "desnudas": no toca las que ya vienen precedidas por / . o un identificador.
RELATIVE_PATH_RE = re.compile(r"(?<![\w./-])(scripts|references)/")
MARKER = "<!-- generado por tools/install_copilot_skills.py desde .claude/skills/{name}; no editar a mano -->"


def parse_frontmatter(text: str, skill: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"{skill}: SKILL.md sin frontmatter YAML")
    fields = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            fields[key.strip()] = value.strip()
    return fields


def validate(skill_dir: Path, text: str) -> None:
    fm = parse_frontmatter(text, skill_dir.name)
    name, desc = fm.get("name", ""), fm.get("description", "")
    errors = []
    if name != skill_dir.name:
        errors.append(f"name '{name}' no coincide con la carpeta '{skill_dir.name}'")
    if not NAME_RE.match(name) or len(name) > 64:
        errors.append("name debe ser minúsculas/dígitos/guiones, máx. 64")
    if not desc or len(desc) > 1024:
        errors.append(f"description obligatoria y de máx. 1024 caracteres (tiene {len(desc)})")
    if errors:
        raise SystemExit(f"{skill_dir.name}: " + "; ".join(errors))


def rewrite_markdown(text: str, prefix: str, name: str, is_skill_md: bool) -> str:
    text = RELATIVE_PATH_RE.sub(lambda m: f"{prefix}/{name}/{m.group(1)}/", text)
    if is_skill_md:
        end = text.index("\n---\n", 4) + len("\n---\n")
        text = text[:end] + "\n" + MARKER.format(name=name) + "\n" + text[end:]
    return text


def render(skill_dir: Path, prefix: str) -> dict[str, bytes]:
    """Devuelve {ruta relativa: contenido} de la versión Copilot del skill."""
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    validate(skill_dir, skill_md)
    out: dict[str, bytes] = {}
    for path in sorted(skill_dir.rglob("*")):
        rel = path.relative_to(skill_dir)
        if path.is_dir() or IGNORED_DIRS & set(rel.parts) or path.suffix in IGNORED_SUFFIXES:
            continue
        if path.suffix == ".md":
            text = rewrite_markdown(path.read_text(encoding="utf-8"), prefix, skill_dir.name,
                                    is_skill_md=rel.as_posix() == "SKILL.md")
            out[rel.as_posix()] = text.encode("utf-8")
        else:
            out[rel.as_posix()] = path.read_bytes()
    return out


def read_tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and not IGNORED_DIRS & set(p.relative_to(root).parts)}


def is_generated(target_dir: Path) -> bool:
    skill_md = target_dir / "SKILL.md"
    return skill_md.exists() and "generado por tools/install_copilot_skills.py" in skill_md.read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", action="store_true", help="instalar en ~/.copilot/skills en vez del repo")
    ap.add_argument("--check", action="store_true", help="solo verificar que la copia esté al día")
    ap.add_argument("--force", action="store_true", help="pisar skills de destino no generados por este script")
    args = ap.parse_args()

    target = USER_TARGET if args.user else PROJECT_TARGET
    # Comandos del skill se corren desde la raíz del workspace: ruta relativa para el repo, absoluta para ~.
    prefix = target.as_posix() if args.user else target.relative_to(REPO_ROOT).as_posix()

    skills = sorted(d for d in SOURCE.iterdir() if (d / "SKILL.md").is_file())
    if not skills:
        print(f"No hay skills en {SOURCE}", file=sys.stderr)
        return 1

    stale = []
    for skill_dir in skills:
        expected = render(skill_dir, prefix)
        dest = target / skill_dir.name
        if args.check:
            if read_tree(dest) != expected:
                stale.append(skill_dir.name)
            continue

        if dest.exists() and not is_generated(dest) and not args.force:
            print(f"{dest} existe y no lo generó este script; usá --force para pisarlo", file=sys.stderr)
            return 1
        shutil.rmtree(dest, ignore_errors=True)
        for rel, content in expected.items():
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
            shutil.copymode(skill_dir / rel, out)
        print(f"instalado {skill_dir.name} -> {dest}")

    if stale:
        print("desactualizados respecto de .claude/skills: " + ", ".join(stale)
              + "\ncorré: python3 tools/install_copilot_skills.py", file=sys.stderr)
        return 1
    if args.check:
        print("skills de Copilot al día")
    return 0


if __name__ == "__main__":
    sys.exit(main())
