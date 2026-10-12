---
name: session-handoff
description: "Resume Claude Code after a reset or checkpoint ongoing work in local project context files. Use for session handoffs, prompt-by-prompt change history, decisions, tasks, verification, and recovery after inactivity."
metadata:
  version: "1.1.0"
---

# Session handoff

The user's request for this invocation is:

$ARGUMENTS

Use this workflow in the project where Claude Code was started. The durable context lives in `<project-root>/.claude/session-handoff.local/`. The project root is the Git worktree root if there is one, otherwise the current working directory. The installed helper is `.claude/skills/session-handoff/scripts/handoff.py`. If the helper, local instructions, or hooks have not been installed, explain how to install them from the README; do not claim automatic checkpoints are active.

## On each request or after a reset

1. The `UserPromptSubmit` hook starts a numbered entry before Claude works, without persisting the raw prompt. Run `python3 .claude/skills/session-handoff/scripts/handoff.py status` to see its ID, starting branch/HEAD, and pre-existing dirty paths. If the expected entry is missing, explain that the hook may be disabled or Claude Code may need restarting. Never fabricate a prompt history.
2. Read `INDEX.md`, then the relevant topic files and recent `PROMPT_HISTORY.md` entries. Read archives only if needed. Check `git status --short` in Git projects and inspect the actual files before trusting any saved claim. If the branch changed, treat previous test results and task state as potentially stale. The user's latest instructions take precedence.
3. If `.claude/session-handoff.local.md` exists from the old version, read it, transfer still-relevant facts into the topic files, and mark the migration in `INDEX.md`. Do not delete or silently overwrite the old file. If a previous request remained in progress, reconcile it against the actual workspace; do not assume it finished.
4. Safely summarize the *current* request in its prompt entry promptly, then do the task. If asked only to save a checkpoint, record current verified state and stop. If there is no new task, summarize the saved state and concrete next step without inventing work.

## Save progress

- After each meaningful milestone, update only the relevant files; save again before responding. Do not rely only on the `Stop` hook: it cannot run on a sudden reset or user interrupt. The local `CLAUDE.local.md` keeps this instruction in future sessions; the `Stop` hook requests a missing final checkpoint once and then allows stopping with a warning to avoid a loop.
- Use the helper for every handoff-file write. It locks concurrent writers and replaces files atomically. First get the existing topic file's hash, then supply that hash when writing its complete updated text. If it changed in the meantime, reread and merge; never force-overwrite someone else's work:

  ```sh
  python3 .claude/skills/session-handoff/scripts/handoff.py hash TASKS.md
  python3 .claude/skills/session-handoff/scripts/handoff.py write TASKS.md --expected-hash <hash> <<'TEXT'
  # Tasks

  Updated: YYYY-MM-DD HH:MM with time zone

  ## Active work
  - Actual verified state and next action.
  TEXT
  ```

- Update the current prompt record after each change or check, and finalize it before stopping. Supply concise, safe JSON on stdin (replace `P-0001` with the ID reported by `status`):

  ```sh
  python3 .claude/skills/session-handoff/scripts/handoff.py update P-0001 <<'JSON'
  {"summary":"Add login tests","changes":[{"path":"tests/login.test.ts","description":"Added coverage for invalid tokens"}],"checks":[{"command":"npm test -- login","result":"passed"}],"outcome":"Tests added; no remaining blocker","status":"completed"}
  JSON
  ```

  You may omit fields not yet known and leave status `in progress` during work. Updates append unique changes/checks to the entry. Report "no project files changed" in the outcome if nothing changed. The helper records the current HEAD and worktree fingerprint for checks; `status` lists checks that became stale after subsequent changes. Still verify actual results yourself: a hash cannot prove a command ran.
- Compare each changed path with the prompt's starting Git status and your own edits. A pre-existing dirty file is not automatically your change, and another session may edit it concurrently. Use relative paths and distinguish saved edits from proposals. If a topic file is stale or a write/check fails, tell the user explicitly; never claim a checkpoint was saved when it was not.
- Never copy secrets, tokens, credentials, environment-file contents, private customer data, or large source/output dumps into handoff files or JSON arguments. Use safe summaries, not full prompts. Do not stage, commit, or upload local context without explicit instruction.

## Context files

The helper creates these files under `.claude/session-handoff.local/`. Each topic file has an `Updated: YYYY-MM-DD HH:MM with time zone` line. Keep entries concise and current while preserving the history needed to understand decisions.

| File | Keep up to date with |
| --- | --- |
| `INDEX.md` | Short entrypoint: current focus, branch/HEAD checked on resume, first concrete next action, and relative links to the other topic files. |
| `PROJECT.md` | Stable orientation: project purpose, relevant architecture and paths, build/test commands, and enduring user preferences. |
| `DECISIONS.md` | Dated decisions with rationale. Mark old choices as superseded by newer decisions rather than erasing their history. |
| `TASKS.md` | Active work, acceptance criteria, completed milestones, blockers, and exact next steps. Mark incomplete work explicitly. |
| `VERIFICATION.md` | Commands, dates, observed results, relevant prompt IDs and HEAD, untested changes, and checks made stale by later edits. |
| `PROMPT_HISTORY.md` | Helper-generated recent prompt-to-change entries; do not edit this file manually. Older completed entries move to `archive/YYYY-MM.md` after 50 entries. |

Treat the local files as a lead, never as proof that code or tests are current. On completion, tell the user where the handoff was saved and whether Git excludes it. Optional private backup outside the workspace is recommended if files might be deleted, but never required or automatic.
