#!/usr/bin/env python3
"""Check bundle consistency and portable references without extra packages."""
from pathlib import Path
import json
import re
import tomllib
from generate_agents import render

ROOT = Path(__file__).resolve().parents[1]
roles = json.loads((ROOT / "agents/roles.json").read_text(encoding="utf-8"))
assert len(roles) == 8
for role, meta in roles.items():
    agent = ROOT / "agents" / (role + ".toml")
    data = tomllib.loads(agent.read_text(encoding="utf-8"))
    assert data["name"] == role
    assert agent.read_text(encoding="utf-8") == render(role), role
    signature = meta["model"] + " / " + meta["model_reasoning_effort"]
    reference = ROOT / "skills/frontend-flow/references" / (meta["references"][-1] + ".md")
    assert reference.read_text(encoding="utf-8").splitlines()[0].endswith(signature), role
    for name in ("README.md", "docs/frontend-flow.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert ("(" + chr(96) + role + chr(96) + ") | " + chr(96) + signature + chr(96)) in text, (role, name)
    skill = (ROOT / "skills/frontend-flow/SKILL.md").read_text(encoding="utf-8")
    line = next(line for line in skill.splitlines() if line.startswith("| ") and role in line)
    assert "| " + meta["model"] + " | " + meta["model_reasoning_effort"] + " |" in line, role
for skill in ("frontend-flow", "code-review"):
    text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    header = text.split("---", 2)[1]
    assert "name: " + skill in header and "description: " in header
    assert "[TODO:" not in text
for folder in ("skills", "agents", "instructions", "docs"):
    for file in (ROOT / folder).rglob("*"):
        if not file.is_file():
            continue
        text = file.read_text(encoding="utf-8")
        assert not re.search(r"[A-Za-z]:[/\\]Users[/\\]|/Users/|/home/[^ /]+/", text), file
        if file.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in link or link.startswith("#"):
                    continue
                assert (file.parent / link).exists(), (file, link)
config = tomllib.loads((ROOT / "config/playwright.toml").read_text(encoding="utf-8"))
assert config["mcp_servers"]["playwright"]["command"] == "npx"
hook = json.loads((ROOT / "hooks/session-start.template.json").read_text(encoding="utf-8"))
assert hook["hooks"][0]["type"] == "command"
print("Bundle valid: 8 agents, 2 skills, model tables, references and portable paths.")
