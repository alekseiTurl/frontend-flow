#!/usr/bin/env python3
"""Install frontend-flow. Python 3.11+, no third-party dependencies."""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tomllib

REPO = Path(__file__).resolve().parents[1]


def safe_target(home, relative):
    candidate = home / relative
    if not candidate.resolve().is_relative_to(home):
        raise ValueError("Destination escapes installation directory: " + str(relative))
    for part in [candidate, *candidate.parents]:
        if part == home:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Refusing to write through a link: " + str(part))
    return candidate


def shell_command(node, script):
    args = [str(node), str(script)]
    if os.name == "nt":
        if any(any(c in a for c in '%!&|<>^"\r\n') for a in args):
            raise ValueError("Unsupported shell character in Node/installation path")
        return " ".join('"' + a + '"' for a in args)
    return shlex.join(args)


def merge_hooks(existing, group):
    data = copy.deepcopy(existing)
    if not isinstance(data, dict) or not isinstance(data.setdefault("hooks", {}), dict):
        raise ValueError("hooks.json must contain a hooks object")
    groups = data["hooks"].setdefault("SessionStart", [])
    if not isinstance(groups, list):
        raise ValueError("SessionStart must be an array")
    for current in groups:
        if current == group:
            return data
        for handler in current.get("hooks", []):
            value = handler.get("command", "").replace("\\", "/")
            if "frontend-flow/scripts/session-start.cjs" in value:
                raise ValueError("A different frontend-flow hook exists; review it manually")
    groups.append(group)
    return data


def build_plan(home, overwrite=False, configure_playwright=False, install_style=False, node=None):
    home = Path(home).expanduser().resolve()
    writes = {}
    sources = []
    for folder in ("agents", "skills/frontend-flow", "skills/code-review"):
        sources.extend(p for p in (REPO / folder).rglob("*") if p.is_file() and p.suffix != ".pyc")
    for source in sources:
        rel = source.relative_to(REPO)
        if rel == Path("agents/roles.json"):
            continue
        data = source.read_bytes()
        dest = safe_target(home, rel)
        if dest.exists() and dest.read_bytes() != data and not overwrite:
            raise ValueError("Existing file differs; review then use --overwrite: " + str(rel))
        if not dest.exists() or dest.read_bytes() != data:
            writes[rel] = data

    config_path = safe_target(home, Path("config.toml"))
    config_text = config_path.read_text(encoding="utf-8-sig") if config_path.exists() else ""
    config = tomllib.loads(config_text)
    if configure_playwright and "playwright" not in config.get("mcp_servers", {}):
        snippet = (REPO / "config/playwright.toml").read_text(encoding="utf-8")
        config_text = config_text.rstrip() + "\n\n" + snippet
        tomllib.loads(config_text)
        writes[Path("config.toml")] = config_text.encode("utf-8")

    node = node or shutil.which("node")
    if not node or not Path(node).is_file():
        raise ValueError("Node.js executable is required for the SessionStart hook")
    group = json.loads((REPO / "hooks/session-start.template.json").read_text(encoding="utf-8"))
    group["hooks"][0]["command"] = shell_command(Path(node).resolve(), home / "skills/frontend-flow/scripts/session-start.cjs")
    for item in config.get("hooks", {}).get("SessionStart", []):
        for handler in item.get("hooks", []):
            if "frontend-flow/scripts/session-start.cjs" in handler.get("command", "").replace("\\", "/"):
                raise ValueError("frontend-flow is registered inline in config.toml; review hooks manually")
    hook_path = safe_target(home, Path("hooks.json"))
    existing = json.loads(hook_path.read_text(encoding="utf-8-sig")) if hook_path.exists() else {}
    merged = merge_hooks(existing, group)
    if merged != existing:
        writes[Path("hooks.json")] = (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    if install_style:
        dest = safe_target(home, Path("AGENTS.md"))
        old = dest.read_text(encoding="utf-8-sig") if dest.exists() else ""
        begin, end = "<!-- frontend-flow-style:start -->", "<!-- frontend-flow-style:end -->"
        if (begin in old) != (end in old) or old.count(begin) > 1 or old.count(end) > 1:
            raise ValueError("Invalid frontend-flow style markers")
        style = (REPO / "instructions/AGENTS.md").read_text(encoding="utf-8").strip()
        block = begin + "\n" + style + "\n" + end
        if begin in old:
            start, stop = old.index(begin), old.index(end) + len(end)
            if stop <= start:
                raise ValueError("Reversed style markers")
            updated = old[:start] + block + old[stop:]
        else:
            updated = old.rstrip() + ("\n\n" if old.strip() else "") + block + "\n"
        if updated != old:
            writes[Path("AGENTS.md")] = updated.encode("utf-8")
    return home, writes


def install(home, *, dry_run=False, overwrite=False, configure_playwright=False, install_style=False, node=None):
    home, writes = build_plan(home, overwrite, configure_playwright, install_style, node)
    originals = {}
    for rel in writes:
        dest = safe_target(home, rel)
        originals[rel] = dest.read_bytes() if dest.exists() else None
    if dry_run:
        return sorted(str(p) for p in writes)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for rel, old in originals.items():
        dest = safe_target(home, rel)
        if (dest.read_bytes() if dest.exists() else None) != old:
            raise ValueError("File changed during installation: " + str(rel))
    for rel, old in originals.items():
        if old is not None:
            save = safe_target(home, Path("frontend-flow-backups") / stamp / rel)
            save.parent.mkdir(parents=True, exist_ok=True)
            save.write_bytes(old)
    for rel, data in writes.items():
        dest = safe_target(home, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return sorted(str(p) for p in writes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--configure-playwright", action="store_true")
    parser.add_argument("--install-style", action="store_true")
    args = parser.parse_args()
    try:
        changed = install(args.codex_home, dry_run=args.dry_run, overwrite=args.overwrite,
                          configure_playwright=args.configure_playwright, install_style=args.install_style)
    except (ValueError, OSError) as exc:
        parser.exit(1, "Installation stopped: " + str(exc) + "\n")
    print(("Would update " if args.dry_run else "Updated ") + str(len(changed)) + " files.")
    for name in changed:
        print(name)
    if not args.dry_run:
        print("Review SessionStart in Codex /hooks, then start a new chat.")
        print("Replaced files are backed up under frontend-flow-backups.")


if __name__ == "__main__":
    main()
