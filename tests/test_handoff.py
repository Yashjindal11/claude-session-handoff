import concurrent.futures
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / "skill/scripts/handoff.py"
SKILL = SOURCE / "skill/SKILL.md"

spec = importlib.util.spec_from_file_location("handoff", SCRIPT)
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name) / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "config", "user.name", "Demo User"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=self.root, check=True)
        (self.root / "README.md").write_text("Initial project\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "Initial project"], cwd=self.root, check=True)
        destination = self.root / ".claude/skills/session-handoff"
        (destination / "scripts").mkdir(parents=True)
        shutil.copy2(SKILL, destination / "SKILL.md")
        shutil.copy2(SCRIPT, destination / "scripts/handoff.py")
        self.script = destination / "scripts/handoff.py"

    def command(self, action, value=None, input_text=None, check=True, extra=()):
        args = [sys.executable, str(self.script), action]
        if value:
            args.append(value)
        args.extend(extra)
        result = subprocess.run(args, cwd=self.root, input=input_text, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            self.fail("Command failed: {}: {}".format(args, result.stderr))
        return result

    def event(self, name, prompt_id, session="session-1", **extra):
        return json.dumps(dict({"hook_event_name": name, "cwd": str(self.root),
                                "session_id": session, "prompt_id": prompt_id}, **extra))

    def state(self):
        return json.loads((self.root / handoff.DIRECTORY / ".state.json").read_text(encoding="utf-8"))

    def test_install_preserves_existing_files_and_is_idempotent(self):
        (self.root / "CLAUDE.local.md").write_text("# My existing instructions\n", encoding="utf-8")
        settings = self.root / ".claude/settings.local.json"
        settings.write_text(json.dumps({"permissions": {"allow": ["Read"]},
                                        "hooks": {"Stop": [{"hooks": [{"type": "command",
                                                                         "command": "echo original"}]}]}}),
                            encoding="utf-8")
        self.command("install")
        self.command("install")
        instructions = (self.root / "CLAUDE.local.md").read_text(encoding="utf-8")
        self.assertIn("My existing instructions", instructions)
        self.assertEqual(instructions.count(handoff.START_MARKER), 1)
        configured = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(configured["permissions"]["allow"], ["Read"])
        self.assertEqual(len(configured["hooks"]["Stop"]), 2)
        self.assertEqual(len(configured["hooks"]["UserPromptSubmit"]), 1)
        self.assertIn("${CLAUDE_PROJECT_DIR}", json.dumps(configured))
        for name in ("CLAUDE.local.md", ".claude/settings.local.json",
                     ".claude/session-handoff.local/INDEX.md"):
            result = subprocess.run(["git", "check-ignore", "-q", name], cwd=self.root)
            self.assertEqual(result.returncode, 0, name)
        self.assertTrue(all((self.root / handoff.DIRECTORY / name).is_file()
                            for name in (*handoff.TOPIC_FILES, "PROMPT_HISTORY.md")))

    def test_prompt_lifecycle_and_privacy(self):
        self.command("install")
        (self.root / "notes.txt").write_text("Pre-existing work\n", encoding="utf-8")
        start = self.command("hook-begin", input_text=self.event(
            "UserPromptSubmit", "request-1", prompt="Do not log MY_PRIVATE_TOKEN")).stdout
        self.assertIn("P-0001", start)
        self.assertIn("notes.txt", self.state()["entries"][0]["baseline"]["dirty_paths"])
        self.assertIn(".claude/", self.state()["entries"][0]["baseline"]["dirty_paths"])
        self.assertNotIn("MY_PRIVATE_TOKEN", (self.root / handoff.DIRECTORY /
                                               "PROMPT_HISTORY.md").read_text(encoding="utf-8"))
        self.assertEqual(self.state()["next_id"], 2)
        self.command("hook-begin", input_text=self.event("UserPromptSubmit", "request-1"))
        self.assertEqual(len(self.state()["entries"]), 1)
        feedback = self.command("hook-stop", input_text=self.event("Stop", "request-1")).stdout
        self.assertIn("additionalContext", json.loads(feedback)["hookSpecificOutput"])
        task_hash = self.command("hash", "TASKS.md").stdout.strip()
        self.command("write", "TASKS.md", "# Tasks\n\nUpdated: 2026-10-12 21:00 +05:30\n\nDo the work.\n",
                     extra=("--expected-hash", task_hash))
        (self.root / "tests").mkdir()
        (self.root / "tests/test_feature.py").write_text("def test_feature(): pass\n", encoding="utf-8")
        self.command("update", "P-0001", json.dumps({
            "summary": "Add a test",
            "changes": [{"path": "tests/test_feature.py", "description": "Added regression coverage"}],
            "checks": [{"command": "python3 -m unittest", "result": "passed"}],
            "outcome": "Implemented and verified",
            "status": "completed",
        }))
        self.assertEqual(json.loads(self.command("status").stdout)["stale_checks"], [])
        (self.root / "tests/test_feature.py").write_text("def test_feature(): assert True\n",
                                                          encoding="utf-8")
        self.assertEqual(json.loads(self.command("status").stdout)["stale_checks"],
                         ["python3 -m unittest"])
        self.assertEqual(self.command("hook-stop", input_text=self.event("Stop", "request-1")).stdout, "")
        history = (self.root / handoff.DIRECTORY / "PROMPT_HISTORY.md").read_text(encoding="utf-8")
        self.assertIn("tests/test_feature.py", history)
        self.assertIn("passed (HEAD", history)
        self.assertIn("- Status: completed", history)
        self.command("hook-begin", input_text=self.event("UserPromptSubmit", "request-2"))
        self.assertEqual(len(self.state()["entries"]), 2)

    def test_stop_only_requests_one_continuation(self):
        self.command("install")
        self.command("hook-begin", input_text=self.event("UserPromptSubmit", "request-1"))
        feedback = self.command("hook-stop", input_text=self.event(
            "Stop", "request-1", stop_hook_active=True)).stdout
        self.assertIn("systemMessage", json.loads(feedback))
        self.assertEqual(self.state()["entries"][0]["status"], "in progress")

    def test_unfinished_prompt_and_branch_switch_are_visible(self):
        self.command("install")
        self.command("hook-begin", input_text=self.event("UserPromptSubmit", "request-1"))
        subprocess.run(["git", "checkout", "-qb", "feature"], cwd=self.root, check=True)
        self.assertTrue(json.loads(self.command("status").stdout)["branch_changed"])
        self.command("hook-begin", input_text=self.event("UserPromptSubmit", "request-2"))
        first, second = self.state()["entries"]
        self.assertEqual(first["status"], "interrupted")
        self.assertEqual(second["baseline"]["branch"], "feature")
        self.assertEqual(second["status"], "in progress")

    def test_migration_keeps_previous_handoff(self):
        old = self.root / ".claude/session-handoff.local.md"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text("Important old decision: keep feature X.\n", encoding="utf-8")
        self.command("install")
        self.assertIn("keep feature X", old.read_text(encoding="utf-8"))
        self.assertIn("Older handoff needs review", (self.root / handoff.DIRECTORY /
                                                      "INDEX.md").read_text(encoding="utf-8"))
        self.assertEqual(subprocess.run(["git", "check-ignore", "-q", str(old.relative_to(self.root))],
                                        cwd=self.root).returncode, 0)

    def test_concurrent_prompts_are_not_lost(self):
        self.command("install")
        def start(number):
            return self.command("hook-begin", input_text=self.event(
                "UserPromptSubmit", "request-{}".format(number),
                session="session-{}".format(number))).stdout
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(start, range(12)))
        self.assertEqual(len(set(results)), 12)
        self.assertEqual(len(self.state()["entries"]), 12)
        self.assertEqual(self.state()["next_id"], 13)

    def test_stale_topic_write_is_rejected(self):
        self.command("install")
        previous = self.command("hash", "DECISIONS.md").stdout.strip()
        first = "# Decisions\n\nUpdated: today\n\n- Use approach A.\n"
        self.command("write", "DECISIONS.md", first, extra=("--expected-hash", previous))
        stale = self.command("write", "DECISIONS.md",
                             "# Decisions\n\nUpdated: today\n\n- Use approach B.\n",
                             check=False, extra=("--expected-hash", previous))
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("changed since it was read", stale.stderr)
        self.assertEqual((self.root / handoff.DIRECTORY / "DECISIONS.md").read_text(encoding="utf-8"),
                         first)

    def test_archive_preserves_completed_entries(self):
        self.command("install")
        original = handoff.MAX_CURRENT_ENTRIES
        handoff.MAX_CURRENT_ENTRIES = 2
        try:
            for number in range(4):
                event = {"session_id": "session", "prompt_id": "request-{}".format(number)}
                identifier = handoff.begin(self.root, event)
                handoff.update(self.root, identifier, {
                    "summary": "Request {}".format(number), "status": "completed",
                    "outcome": "Done",
                })
        finally:
            handoff.MAX_CURRENT_ENTRIES = original
        self.assertEqual(len(self.state()["entries"]), 2)
        archives = list((self.root / handoff.DIRECTORY / "archive").glob("*.md"))
        self.assertEqual(len(archives), 1)
        contents = archives[0].read_text(encoding="utf-8")
        self.assertIn("## P-0001", contents)
        self.assertIn("## P-0002", contents)
        self.assertIn("## P-0004", (self.root / handoff.DIRECTORY /
                                  "PROMPT_HISTORY.md").read_text(encoding="utf-8"))

    def test_invalid_input_does_not_erase_existing_state(self):
        settings = self.root / ".claude/settings.local.json"
        settings.write_text("{broken json", encoding="utf-8")
        self.assertNotEqual(self.command("install", check=False).returncode, 0)
        self.assertEqual(settings.read_text(encoding="utf-8"), "{broken json")
        settings.unlink()
        self.command("install")
        self.command("hook-begin", input_text=self.event("UserPromptSubmit", "request-1"))
        invalid = self.command("update", "P-0001", json.dumps({
            "summary": "Bad path", "changes": [{"path": "../other", "description": "No"}]
        }), check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(self.state()["entries"][0]["summary"], "Pending safe summary (raw prompt not stored).")

    def test_install_rejects_mismatched_skill(self):
        skill = self.root / ".claude/skills/session-handoff/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace('"1.1.0"', '"1.0.0"'),
                         encoding="utf-8")
        result = self.command("install", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match helper version", result.stderr)
        self.assertFalse((self.root / "CLAUDE.local.md").exists())

    def test_new_git_project_without_commits(self):
        root = Path(self.workspace.name) / "new-project"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        destination = root / ".claude/skills/session-handoff"
        (destination / "scripts").mkdir(parents=True)
        shutil.copy2(SKILL, destination / "SKILL.md")
        shutil.copy2(SCRIPT, destination / "scripts/handoff.py")
        subprocess.run([sys.executable, str(destination / "scripts/handoff.py"), "install"],
                       cwd=root, check=True, stdout=subprocess.PIPE, text=True)
        self.assertIsInstance(handoff.workspace_fingerprint(root), str)

    def test_project_without_git(self):
        root = Path(self.workspace.name) / "plain-project"
        root.mkdir()
        destination = root / ".claude/skills/session-handoff"
        (destination / "scripts").mkdir(parents=True)
        shutil.copy2(SKILL, destination / "SKILL.md")
        shutil.copy2(SCRIPT, destination / "scripts/handoff.py")
        subprocess.run([sys.executable, str(destination / "scripts/handoff.py"), "install"],
                       cwd=root, check=True, stdout=subprocess.PIPE, text=True)
        self.assertTrue((root / handoff.DIRECTORY / "INDEX.md").is_file())
        self.assertIsNone(handoff.workspace_fingerprint(root))


if __name__ == "__main__":
    unittest.main()
