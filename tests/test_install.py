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

    def test_overwrite_refreshes_hook_command_with_backup_and_dry_run(self):
        self.install()
        p = self.home / "hooks.json"
        script = self.home / "skills/frontend-flow/scripts/session-start.cjs"
        old_node = self.base / "previous Node" / Path(self.node).name
        other = {"hooks": [{"type": "command", "command": "echo other"}]}
        for command in (installer.shell_command(old_node, script), 'node "' + script.as_posix() + '"'):
            with self.subTest(command=command):
                hooks = json.loads(p.read_text(encoding="utf-8"))
                flow = hooks["hooks"]["SessionStart"][-1]
                expected_command = flow["hooks"][0]["command"]
                flow["hooks"][0]["command"] = command
                hooks["hooks"]["SessionStart"] = [other, flow]
                hooks["description"] = "keep"
                original = json.dumps(hooks).encode("utf-8")
                p.write_bytes(original)
                with self.assertRaisesRegex(ValueError, "different frontend-flow hook"):
                    self.install()
                backups_before = list((self.home / "frontend-flow-backups").glob("*/hooks.json"))
                self.assertEqual(self.install(overwrite=True, dry_run=True), ["hooks.json"])
                self.assertEqual(p.read_bytes(), original)
                self.assertEqual(list((self.home / "frontend-flow-backups").glob("*/hooks.json")), backups_before)
                self.assertEqual(self.install(overwrite=True), ["hooks.json"])
                updated = json.loads(p.read_text(encoding="utf-8"))
                self.assertEqual(updated["hooks"]["SessionStart"][0], other)
                self.assertEqual(updated["description"], "keep")
                self.assertEqual(updated["hooks"]["SessionStart"][1]["hooks"][0]["command"], expected_command)
                backups = list((self.home / "frontend-flow-backups").glob("*/hooks.json"))
                self.assertEqual(len(backups), len(backups_before) + 1)
                self.assertTrue(any(backup.read_bytes() == original for backup in backups))
                self.assertEqual(self.install(overwrite=True), [])

    def test_overwrite_rejects_foreign_or_customized_hooks(self):
        group = json.loads((installer.REPO / "hooks/session-start.template.json").read_text(encoding="utf-8"))
        script = self.home / "skills/frontend-flow/scripts/session-start.cjs"
        old_node = self.base / "previous Node" / Path(self.node).name
        group["hooks"][0]["command"] = installer.shell_command(old_node, script)
        foreign = copy.deepcopy(group)
        foreign["hooks"][0]["command"] = installer.shell_command(old_node, self.base / "other/frontend-flow/scripts/session-start.cjs")
        custom_matcher = copy.deepcopy(group)
        custom_matcher["matcher"] = "startup"
        custom_handler = copy.deepcopy(group)
        custom_handler["hooks"][0]["timeout"] = 30
        mixed = copy.deepcopy(group)
        mixed["hooks"].append({"type": "command", "command": "echo other"})
        wrapper = copy.deepcopy(group)
        wrapper["hooks"][0]["command"] += " && echo custom"
        malformed = copy.deepcopy(group)
        malformed["hooks"][0]["command"] += '"'
        matching = copy.deepcopy(group)
        matching["hooks"][0]["command"] = installer.shell_command(Path(self.node).resolve(), script)
        cases = [[hook] for hook in (foreign, custom_matcher, custom_handler, mixed, wrapper, malformed)]
        cases.extend(([matching, foreign], [matching, group], [group, group], [matching, matching]))
        for groups in cases:
            with self.subTest(hooks=groups):
                original = json.dumps({"hooks": {"SessionStart": groups}})
                p = self.put("hooks.json", original)
                with self.assertRaisesRegex(ValueError, "frontend-flow hook"):
                    self.install(overwrite=True)
                self.assertEqual(p.read_text(encoding="utf-8"), original)
                self.assertFalse((self.home / "agents").exists())

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
