import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="frontend-flow-install-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "custom codex home"
        self.node = shutil.which("node")
        self.assertIsNotNone(self.node)

    def install(self, **kwargs):
        return installer.install(self.home, node=self.node, **kwargs)

    def put(self, name, text):
        p = self.home / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_dry_run_does_not_create_destination(self):
        result = self.install(dry_run=True, configure_playwright=True, install_style=True)
        self.assertTrue(result)
        self.assertFalse(self.home.exists())

    def test_fresh_install_and_second_run_are_idempotent(self):
        self.install(configure_playwright=True, install_style=True)
        self.assertTrue((self.home / "agents/junior_dev.toml").exists())
        self.assertTrue((self.home / "skills/code-review/SKILL.md").exists())
        self.assertEqual(self.install(configure_playwright=True, install_style=True), [])
        data = json.loads((self.home / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["SessionStart"]), 1)

    def test_conflict_aborts_before_any_write(self):
        p = self.put("agents/frontend_writer.toml", "custom config")
        with self.assertRaisesRegex(ValueError, "Existing file differs"):
            self.install()
        self.assertEqual(p.read_text(encoding="utf-8"), "custom config")
        self.assertFalse((self.home / "hooks.json").exists())
        self.assertFalse((self.home / "skills").exists())

    def test_overwrite_preserves_backup(self):
        p = self.put("agents/frontend_writer.toml", "old personal role")
        self.install(overwrite=True)
        self.assertIn("gpt-6-luna", p.read_text(encoding="utf-8"))
        backups = list((self.home / "frontend-flow-backups").glob("*/agents/frontend_writer.toml"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "old personal role")

    def test_existing_mcp_and_unrelated_config_are_preserved(self):
        original = '# keep comments\nmodel = "example"\n[mcp_servers.playwright]\ncommand = "custom"\n'
        p = self.put("config.toml", original)
        self.install(configure_playwright=True)
        self.assertEqual(p.read_text(encoding="utf-8"), original)

    def test_new_mcp_keeps_other_settings(self):
        self.put("config.toml", '# custom comment\nmodel = "example"\n')
        self.install(configure_playwright=True)
        text = (self.home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("# custom comment", text)
        self.assertEqual(tomllib.loads(text)["model"], "example")
        self.assertIn("playwright", tomllib.loads(text)["mcp_servers"])

    def test_custom_hooks_and_style_survive(self):
        other = {"matcher": "startup", "hooks": [{"type": "command", "command": "echo other"}]}
        self.put("hooks.json", json.dumps({"description": "custom", "hooks": {"SessionStart": [other]}}))
        self.put("AGENTS.md", "Personal instructions\n")
        self.install(install_style=True)
        hook = json.loads((self.home / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(hook["hooks"]["SessionStart"][0], other)
        self.assertEqual(hook["description"], "custom")
        self.assertTrue((self.home / "AGENTS.md").read_text(encoding="utf-8").startswith("Personal instructions"))
        self.assertEqual(self.install(install_style=True), [])

    def test_invalid_config_does_not_install_partially(self):
        self.put("config.toml", "[not-valid")
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse((self.home / "agents").exists())

    def test_conflicting_hook_does_not_install_partially(self):
        self.put("hooks.json", json.dumps({"hooks": {"SessionStart": [{"hooks": [{"command": "node other/frontend-flow/scripts/session-start.cjs"}]}]}}))
        with self.assertRaisesRegex(ValueError, "different frontend-flow hook"):
            self.install()
        self.assertFalse((self.home / "agents").exists())

    def test_inline_hook_conflict(self):
        self.put("config.toml", '[[hooks.SessionStart]]\n[[hooks.SessionStart.hooks]]\ncommand = "node other/frontend-flow/scripts/session-start.cjs"\n')
        with self.assertRaisesRegex(ValueError, "registered inline"):
            self.install()
        self.assertFalse((self.home / "agents").exists())

    def test_generated_hook_runs_from_path_with_spaces(self):
        self.install()
        hooks = json.loads((self.home / "hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        project = self.base / "sample project"
        (project / ".frontend-flow/example").mkdir(parents=True)
        run = subprocess.run(command, shell=True, input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(project)}),
                             text=True, capture_output=True, check=True)
        result = json.loads(run.stdout)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_link_cannot_redirect_install(self):
        self.home.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        try:
            (self.home / "agents").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks unavailable on this account")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
