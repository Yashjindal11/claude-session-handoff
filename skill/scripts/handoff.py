#!/usr/bin/env python3
"""Local, dependency-free state management for the session-handoff skill."""

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


DIRECTORY = Path(".claude/session-handoff.local")
SKILL_PATH = Path(".claude/skills/session-handoff/scripts/handoff.py")
VERSION = "1.1.1"
TOPIC_FILES = ("INDEX.md", "PROJECT.md", "DECISIONS.md", "TASKS.md", "VERIFICATION.md")
MAX_CURRENT_ENTRIES = 50
START_MARKER = "<!-- session-handoff:start -->"
END_MARKER = "<!-- session-handoff:end -->"
REMINDER = """<!-- session-handoff:start -->
## Local session handoff
For each new request, the local hook starts a prompt-history entry without saving the raw prompt.
Read `.claude/session-handoff.local/INDEX.md` and check the actual workspace before continuing.
Use the `session-handoff` skill and its helper to update the relevant context files after meaningful milestones.
Before responding, finalize the current prompt entry with a safe summary, actual changes, checks, and outcome.
If the Stop hook asks for a checkpoint, complete it before stopping; never claim an unsaved result.
<!-- session-handoff:end -->
"""


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="minutes")


def git(root, *args, optional=False):
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except FileNotFoundError:
        if optional:
            return None
        raise RuntimeError("Git is required to inspect this Git project")
    if result.returncode == 0:
        return result.stdout.strip()
    error = result.stderr.lower()
    if optional and ("not a git repository" in error or
                     (args == ("rev-parse", "HEAD") and
                      ("unknown revision" in error or "needed a single revision" in error))):
        return None
    raise RuntimeError("git {} failed: {}".format(" ".join(args), result.stderr.strip()))


def is_git_project(root):
    return git(root, "rev-parse", "--is-inside-work-tree", optional=True) == "true"


def project_root(cwd):
    cwd = Path(cwd).expanduser().resolve()
    if not cwd.is_dir():
        raise ValueError("Project directory does not exist: {}".format(cwd))
    found = git(cwd, "rev-parse", "--show-toplevel", optional=True)
    return Path(found).resolve() if found else cwd


def ensure_private(root):
    if not is_git_project(root):
        return
    tracked = subprocess.run(
        ["git", "ls-files", "--", str(DIRECTORY), "CLAUDE.local.md",
         ".claude/settings.local.json", ".claude/session-handoff.local.md"],
        cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        check=True,
    ).stdout.strip()
    if tracked:
        raise RuntimeError("Local handoff paths are tracked by Git; untrack them explicitly first:\n" + tracked)
    exclude_path = git(root, "rev-parse", "--git-path", "info/exclude")
    if exclude_path is None:
        raise RuntimeError("Cannot locate Git's local exclude file")
    exclude = Path(exclude_path)
    if not exclude.is_absolute():
        exclude = root / exclude
    patterns = ["/.claude/session-handoff.local/", "/CLAUDE.local.md",
                "/.claude/settings.local.json"]
    if (root / ".claude/session-handoff.local.md").exists():
        patterns.append("/.claude/session-handoff.local.md")
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    missing = [pattern for pattern in patterns if pattern not in existing.splitlines()]
    if missing:
        with exclude.open("a", encoding="utf-8") as output:
            output.write(("" if not existing or existing.endswith("\n") else "\n") +
                         "\n".join(missing) + "\n")
    for relative in (str(DIRECTORY / "INDEX.md"), "CLAUDE.local.md",
                     ".claude/settings.local.json"):
        if subprocess.run(["git", "check-ignore", "-q", "--", relative],
                          cwd=str(root)).returncode != 0:
            raise RuntimeError("Git did not exclude {}; refusing to save context".format(relative))


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing to replace a symlink: {}".format(path))
    fd, temporary = tempfile.mkstemp(prefix=".handoff-", dir=str(path.parent))
    try:
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@contextlib.contextmanager
def locked(root):
    directory = root / DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield directory
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def default_topic(filename, root):
    timestamp = now()
    if filename == "INDEX.md":
        legacy = root / ".claude/session-handoff.local.md"
        migration = ("\n- Older handoff needs review: `../session-handoff.local.md`.\n"
                     if legacy.exists() else "")
        return (
            "# Session handoff\n\nUpdated: {}\n\n"
            "## Current focus\n- Confirm the current request against the workspace.\n\n"
            "## Next action\n- Read the task and check the working tree.\n\n"
            "## Project identity\n- Branch and HEAD: check on resume; do not assume this snapshot matches another branch.\n"
            "{}\n## Context\n- [Project](PROJECT.md)\n- [Decisions](DECISIONS.md)\n"
            "- [Tasks](TASKS.md)\n- [Verification](VERIFICATION.md)\n"
            "- [Prompt history](PROMPT_HISTORY.md)\n"
        ).format(timestamp, migration)
    titles = {
        "PROJECT.md": "Project orientation",
        "DECISIONS.md": "Decisions",
        "TASKS.md": "Tasks",
        "VERIFICATION.md": "Verification",
    }
    return "# {}\n\nUpdated: {}\n\nNo verified entries yet.\n".format(titles[filename], timestamp)


def initialize(root):
    ensure_private(root)
    with locked(root) as directory:
        for filename in TOPIC_FILES:
            path = directory / filename
            if not path.exists():
                atomic_write(path, default_topic(filename, root))
        state_path = directory / ".state.json"
        if not state_path.exists():
            atomic_write(state_path, json.dumps({"version": 1, "next_id": 1, "entries": []}, indent=2) + "\n")
        history = directory / "PROMPT_HISTORY.md"
        if not history.exists():
            state = load_state(directory)
            atomic_write(history, render_history(state["entries"]))


def load_state(directory):
    state = json.loads((directory / ".state.json").read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or state.get("version") != 1
            or not isinstance(state.get("entries"), list)
            or not isinstance(state.get("next_id"), int)):
        raise ValueError("Unsupported or corrupt handoff state; do not overwrite it")
    return state


def save_state(directory, state):
    atomic_write(directory / ".state.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    atomic_write(directory / "PROMPT_HISTORY.md", render_history(state["entries"]))


def render_entry(entry):
    lines = [
        "## {} - {}".format(entry["id"], entry["started"]),
        "- Prompt: {}".format(entry["summary"]),
        "- Status: {}".format(entry["status"]),
        "- Session prompt ID: `{}`".format(entry.get("prompt_id") or "unavailable"),
        "- Starting code: branch `{}`, HEAD `{}`, pre-existing dirty paths: {}".format(
            entry["baseline"]["branch"] or "unavailable",
            entry["baseline"]["head"] or "unavailable",
            ", ".join("`{}`".format(path) for path in entry["baseline"]["dirty_paths"]) or "none",
        ),
        "- Changes:",
    ]
    lines += ["  - `{}` - {}".format(item["path"], item["description"])
              for item in entry["changes"]] or ["  - No project files changed yet."]
    lines.append("- Checks:")
    lines += ["  - `{}` - {} (HEAD `{}`).".format(item["command"], item["result"],
                                               item["head"] or "unavailable")
              for item in entry["checks"]] or ["  - Not run yet."]
    lines.append("- Outcome / next step: {}".format(entry["outcome"]))
    return "\n".join(lines) + "\n"


def render_history(entries):
    return ("# Prompt history\n\nUpdated: {}\n\n"
            "Completed older entries are in `archive/YYYY-MM.md`. Raw prompts are never stored here.\n\n"
            "{}").format(now(), "\n".join(render_entry(entry) for entry in entries))


def archive_old(directory, state):
    completed = [entry for entry in state["entries"] if entry["status"] != "in progress"]
    if len(completed) <= MAX_CURRENT_ENTRIES:
        return
    oldest = completed[0]
    month = oldest["started"][:7]
    destination = directory / "archive" / (month + ".md")
    existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
    if ("## {} - ".format(oldest["id"])) not in existing:
        if not existing:
            existing = "# Archived prompt history: {}\n\n".format(month)
        atomic_write(destination, existing + render_entry(oldest) + "\n")
    state["entries"].remove(oldest)


def baseline(root):
    if not is_git_project(root):
        return {"branch": None, "head": None, "dirty_paths": []}
    status = git(root, "status", "--porcelain=v1", "--untracked-files=normal")
    paths = [line[3:] for line in status.splitlines()] if status else []
    return {
        "branch": git(root, "branch", "--show-current"),
        "head": git(root, "rev-parse", "HEAD", optional=True),
        "dirty_paths": paths,
    }


def workspace_fingerprint(root):
    if not is_git_project(root):
        return None
    fingerprint = hashlib.sha256()
    head = git(root, "rev-parse", "HEAD", optional=True)
    diff_commands = ([["git", "diff", "--no-ext-diff", "--binary", "HEAD"]] if head
                     else [["git", "diff", "--no-ext-diff", "--binary", "--cached"],
                           ["git", "diff", "--no-ext-diff", "--binary"]])
    for command in diff_commands:
        diff = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        fingerprint.update(diff.stdout)
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    for raw_path in sorted(filter(None, untracked.stdout.split(b"\0"))):
        fingerprint.update(raw_path)
        path = root / os.fsdecode(raw_path)
        if path.is_symlink():
            fingerprint.update(os.fsencode(os.readlink(path)))
        elif path.is_file():
            with path.open("rb") as file:
                for chunk in iter(lambda: file.read(65536), b""):
                    fingerprint.update(chunk)
    fingerprint.update((head or "").encode("ascii"))
    return fingerprint.hexdigest()


def begin(root, event):
    initialize(root)
    with locked(root) as directory:
        state = load_state(directory)
        prompt_id = event.get("prompt_id")
        session_id = event.get("session_id")
        if prompt_id:
            for entry in state["entries"]:
                if entry.get("prompt_id") == prompt_id:
                    return entry["id"]
        for entry in state["entries"]:
            if entry["status"] == "in progress" and entry.get("session_id") == session_id:
                entry["status"] = "interrupted"
                entry["outcome"] = "A later prompt arrived before this request was finalized; reconcile with the workspace."
        identifier = "P-{:04d}".format(state["next_id"])
        state["next_id"] += 1
        state["entries"].append({
            "id": identifier,
            "started": now(),
            "prompt_id": prompt_id,
            "session_id": session_id,
            "summary": "Pending safe summary (raw prompt not stored).",
            "status": "in progress",
            "baseline": baseline(root),
            "changes": [],
            "checks": [],
            "outcome": "Pending; see TASKS.md for the next action.",
        })
        while len([entry for entry in state["entries"] if entry["status"] != "in progress"]) > MAX_CURRENT_ENTRIES:
            archive_old(directory, state)
        save_state(directory, state)
        return identifier


def update(root, identifier, payload):
    initialize(root)
    allowed = {"summary", "changes", "checks", "outcome", "status"}
    if not isinstance(payload, dict) or not payload or set(payload) - allowed:
        raise ValueError("Expected a JSON object with summary, changes, checks, outcome, or status")
    for key in ("summary", "outcome"):
        if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
            raise ValueError("{} must be nonempty text".format(key))
    if "status" in payload and payload["status"] not in (
        "in progress", "completed", "blocked", "interrupted"
    ):
        raise ValueError("Invalid prompt status")
    for key, fields in (("changes", ("path", "description")), ("checks", ("command", "result"))):
        if key in payload:
            if not isinstance(payload[key], list) or any(
                not isinstance(item, dict) or
                any(not isinstance(item.get(field), str) or not item[field].strip() for field in fields)
                for item in payload[key]
            ):
                raise ValueError("{} must be a list of entries with {}".format(key, ", ".join(fields)))
    with locked(root) as directory:
        state = load_state(directory)
        entry = next((item for item in state["entries"] if item["id"] == identifier), None)
        if entry is None:
            raise ValueError("No current entry {}; it may already be archived".format(identifier))
        if entry["status"] != "in progress":
            raise ValueError("{} is already finalized".format(identifier))
        for key in ("summary", "outcome", "status"):
            if key in payload:
                entry[key] = payload[key].strip()
        for change in payload.get("changes", []):
            path = Path(change["path"])
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Change path must be relative to the project")
            if (not (root / path).exists()
                    and (not is_git_project(root) or git(root, "ls-files", "--", str(path)) == "")
                    and str(path) not in entry["baseline"]["dirty_paths"]):
                raise ValueError("Change path is not in the project: {}".format(path))
            if change not in entry["changes"]:
                entry["changes"].append(change)
        for check in payload.get("checks", []):
            result = dict(check)
            result["head"] = baseline(root)["head"]
            result["fingerprint"] = workspace_fingerprint(root)
            if result not in entry["checks"]:
                entry["checks"].append(result)
        if entry["status"] != "in progress" and entry["summary"].startswith("Pending safe summary"):
            raise ValueError("Summarize the request safely before finalizing")
        while len([item for item in state["entries"] if item["status"] != "in progress"]) > MAX_CURRENT_ENTRIES:
            archive_old(directory, state)
        save_state(directory, state)


def hook_event():
    event = json.load(sys.stdin)
    if not isinstance(event, dict) or not isinstance(event.get("cwd"), str):
        raise ValueError("Hook input must contain a working directory")
    return event


def install(root):
    root = project_root(root)
    source_skill = Path(__file__).resolve().parent.parent / "SKILL.md"
    if not source_skill.is_file() or Path(__file__).resolve() != (root / SKILL_PATH).resolve():
        raise RuntimeError("Put SKILL.md and this script in the project's .claude/skills/session-handoff/ directory first")
    if '  version: "{}"'.format(VERSION) not in source_skill.read_text(encoding="utf-8"):
        raise ValueError("Installed SKILL.md does not match helper version {}; download both again".format(VERSION))
    settings_path = root / ".claude/settings.local.json"
    instructions_path = root / "CLAUDE.local.md"
    settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError("Existing settings.local.json must contain a JSON object")
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Existing hooks setting must be a JSON object")
    for name, command in (("UserPromptSubmit", "hook-begin"), ("Stop", "hook-stop")):
        groups = hooks.setdefault(name, [])
        if not isinstance(groups, list):
            raise ValueError("Existing {} hooks must be a list".format(name))
        entry = {"hooks": [{"type": "command", "command": "python3",
                            "args": ["${CLAUDE_PROJECT_DIR}/" + str(SKILL_PATH), command],
                            "timeout": 10}]}
        if not any(isinstance(group, dict) and any(
            isinstance(handler, dict) and str(SKILL_PATH) in " ".join(
                [str(handler.get("command", ""))] +
                [str(arg) for arg in handler.get("args", [])]
            ) and command in " ".join(str(arg) for arg in handler.get("args", []))
            for handler in group.get("hooks", [])
        ) for group in groups):
            groups.append(entry)
    instructions = instructions_path.read_text(encoding="utf-8") if instructions_path.exists() else ""
    if (START_MARKER in instructions) != (END_MARKER in instructions):
        raise ValueError("Existing CLAUDE.local.md has an incomplete handoff block")
    if START_MARKER in instructions:
        start = instructions.index(START_MARKER)
        end = instructions.index(END_MARKER, start) + len(END_MARKER)
        instructions = instructions[:start] + REMINDER.rstrip("\n") + instructions[end:]
    else:
        instructions = instructions.rstrip("\n") + ("\n\n" if instructions else "") + REMINDER
    ensure_private(root)
    atomic_write(instructions_path, instructions.rstrip("\n") + "\n")
    atomic_write(settings_path, json.dumps(settings, indent=2) + "\n")
    initialize(root)
    print("Installed local handoff in {}. Restart Claude Code to load its hooks and instructions.".format(root))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "hook-begin", "hook-stop", "status",
                                            "hash", "update", "write"))
    parser.add_argument("value", nargs="?", help="Prompt ID for update, or topic filename for write")
    parser.add_argument("--project", default=None, help="Project directory (default: current directory)")
    parser.add_argument("--expected-hash", help="SHA-256 from 'hash' before updating a topic file")
    args = parser.parse_args()
    if args.action.startswith("hook-"):
        event = hook_event()
        if event.get("agent_id"):
            return
        if event.get("hook_event_name") != (
            "UserPromptSubmit" if args.action == "hook-begin" else "Stop"
        ):
            raise ValueError("Unexpected hook event")
        root = project_root(event["cwd"])
    else:
        event = {}
        root = project_root(args.project or os.getcwd())
    if args.action == "install":
        install(root)
    elif args.action == "hook-begin":
        identifier = begin(root, event)
        print("Local handoff {} started. Raw prompt was not saved. Read INDEX.md; use the "
              "session-handoff skill to checkpoint actual work and finalize {} before stopping."
              .format(identifier, identifier))
    elif args.action == "hook-stop":
        initialize(root)
        with locked(root) as directory:
            state = load_state(directory)
            prompt_id = event.get("prompt_id")
            candidates = [entry for entry in state["entries"]
                          if entry.get("prompt_id") == prompt_id] if prompt_id else [
                              entry for entry in state["entries"]
                              if entry.get("session_id") == event.get("session_id")]
            current = candidates[-1] if candidates else None
        if current and current["status"] == "in progress":
            message = ("Handoff {} is still in progress. Update relevant context files and "
                       "finalize the prompt entry with the helper before responding."
                       .format(current["id"]))
            if event.get("stop_hook_active"):
                print(json.dumps({"systemMessage": message + " This turn was allowed to stop to avoid a loop."}))
            else:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "Stop", "additionalContext": message}}))
    elif args.action == "status":
        initialize(root)
        with locked(root) as directory:
            state = load_state(directory)
            if not state["entries"]:
                print(json.dumps({"status": "no prompts yet"}))
            else:
                current = dict(state["entries"][-1])
                fingerprint = workspace_fingerprint(root)
                identity = baseline(root)
                current["current_branch"] = identity["branch"]
                current["current_head"] = identity["head"]
                current["branch_changed"] = current["baseline"]["branch"] != current["current_branch"]
                current["stale_checks"] = [
                    "{}: {}".format(entry["id"], check["command"])
                    for entry in state["entries"] for check in entry["checks"]
                    if fingerprint is None or check.get("fingerprint") != fingerprint
                ]
                print(json.dumps(current, indent=2))
    elif args.action == "update":
        if not args.value:
            parser.error("update requires a prompt ID")
        update(root, args.value, json.load(sys.stdin))
        print("Updated {}".format(args.value))
    elif args.action == "hash":
        if args.value not in TOPIC_FILES:
            parser.error("hash requires one of: " + ", ".join(TOPIC_FILES))
        initialize(root)
        with locked(root) as directory:
            print(digest((directory / args.value).read_text(encoding="utf-8")))
    elif args.action == "write":
        if args.value not in TOPIC_FILES:
            parser.error("write requires one of: " + ", ".join(TOPIC_FILES))
        if not args.expected_hash:
            parser.error("write requires --expected-hash from 'hash FILENAME'")
        content = sys.stdin.read()
        if not content.strip() or "Updated:" not in content:
            raise ValueError("Topic text must include an Updated: line")
        initialize(root)
        with locked(root) as directory:
            current = (directory / args.value).read_text(encoding="utf-8")
            if digest(current) != args.expected_hash:
                raise RuntimeError("{} changed since it was read; reread and merge before writing".format(args.value))
            atomic_write(directory / args.value, content)
        print("Saved {}".format(args.value))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print("Handoff error: {}".format(error), file=sys.stderr)
        sys.exit(1)
