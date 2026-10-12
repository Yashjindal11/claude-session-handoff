---
name: session-handoff
description: "Resume Claude Code after a reset using local project context files, or save a checkpoint before stopping. Use when continuing work across sessions, preserving decisions, tracking tasks and verification, or recovering context after inactivity."
---

# Session handoff

The user's request for this invocation is:

$ARGUMENTS

Use this workflow in the project where Claude Code was started. The durable context lives in `<project-root>/.claude/session-handoff.local/`. The project root is the Git worktree root if there is one, otherwise the current working directory. Do not store project context in this skill's repository unless that repository is the project being worked on.

## At the start of an invocation

1. Locate the project root. Read `INDEX.md` in the context directory first, then its linked topic files. If any files are missing, plan to create them using the layout below, recording only facts you can verify from the user's instructions and the project. Never invent prior conversation or claim that unsaved context was recovered. If an older `.claude/session-handoff.local.md` exists, read it for still-relevant facts.
2. Check the current working tree (`git status --short` if this is a Git project) and the files relevant to the pending task. Treat saved context as a lead, not as proof that a change exists or a test passed. Resolve discrepancies against the actual workspace; ask the user if the intended direction is still unclear. The user's latest instructions take precedence.
3. Keep all context files local by default. In a Git project, if not already ignored, add the exact root-anchored directory `/.claude/session-handoff.local/` to the repository's local exclude file (`git rev-parse --git-path info/exclude`), not to a tracked `.gitignore`. Also retain or add an exclusion for the older single file if it exists. Do not duplicate existing rules. If any context files are already tracked, tell the user; an exclude rule cannot make tracked files private. Do not untrack, stage, commit, or push them without explicit instructions. If local exclusion fails, report that failure before writing potentially sensitive context.
4. Create missing files, and transfer any still-relevant facts from the older single-file handoff; keep the original intact and note the migration in `INDEX.md`. If the request is to save a checkpoint, update the relevant files and stop. If there is a task, briefly orient yourself from the context files and workspace, then do the task. If there is no specific task, summarize the current state and next action rather than guessing what to implement.

## While working

- Update the relevant topic files after each meaningful milestone: a new user requirement or decision, a completed edit, a test result, a blocker, or a change in next steps. Refresh `INDEX.md` whenever the focus or next action changes. Save any pending changes before your final response. Do not rely on an inactivity timer or an end-of-session hook: the session may reset without warning.
- Keep a useful snapshot, not a full chat transcript. Record what a new agent needs to continue: exact relative file paths, why decisions were made, commands and their observed results, unresolved questions, and a concrete next step. Distinguish verified results from plans and from untested work. Preserve still-relevant information when updating a file; do not rewrite every file if only one topic changed.
- Never copy secrets, tokens, credentials, environment-file contents, private customer data, or large source/output dumps into context files. Refer to the location of sensitive material without reproducing it. Check before intentionally sharing or committing any context file.
- Do not overwrite unrelated work or silently dismiss inconsistencies. If a save fails, say so explicitly; do not claim continuity was preserved.

## Context files

Create or maintain these files under `.claude/session-handoff.local/`. Each file should have an `Updated: YYYY-MM-DD HH:MM with time zone` line. Keep entries concise, with dates on decisions and observed test results; remove superseded details when they are no longer useful.

| File | Keep up to date with |
| --- | --- |
| `INDEX.md` | Short entrypoint: current focus, first concrete next action, and relative links to `PROJECT.md`, `DECISIONS.md`, `TASKS.md`, and `VERIFICATION.md`. Keep it short enough to scan immediately. |
| `PROJECT.md` | Stable orientation: project purpose, relevant architecture and paths, build/test commands, and enduring user preferences. |
| `DECISIONS.md` | Dated decisions and the reasons for them; replace outdated decisions with their superseding decision rather than presenting both as current. |
| `TASKS.md` | Active task, requirements and acceptance criteria, completed milestones and files changed, blockers, and specific next steps. Mark incomplete work as incomplete. |
| `VERIFICATION.md` | Commands run, dated observed results, and untested changes. Revalidate or mark earlier results stale when later changes could invalidate them. |

After updating, tell the user where the context directory was saved and whether it is excluded from Git.
