---
name: session-handoff
description: "Use when resuming Claude Code after a reset, saving a checkpoint, or keeping project context across sessions. Maintain local project notes, decisions, tasks, verification, and a prompt-by-prompt change history."
---

# Session handoff

The user's request for this invocation is:

$ARGUMENTS

This is an instruction-only skill: no scripts, hooks, packages, or language runtime are required. Work in the current project, using its Git worktree root if available, otherwise the directory where Claude Code was started. Keep the handoff in `<project-root>/.claude/session-handoff.local/`, not in this skill's repository unless it is the project itself.

## Start or resume

1. In a Git project, check the working tree and branch/HEAD. Read `INDEX.md` first if it exists, then relevant topic files and recent entries in `PROMPT_HISTORY.md`. Verify saved claims against actual files; a recorded test result is not proof it still applies after changes. If files are missing, create them using the layout below. Never invent conversation history that was not saved.
2. Keep notes local by default. If this is a Git project, check whether files under `.claude/session-handoff.local/` are already tracked. If they are, warn the user before writing private context: adding an ignore rule cannot hide tracked files. Otherwise add `/.claude/session-handoff.local/` once to the repository's local exclude file, located with `git rev-parse --git-path info/exclude`; verify Git ignores a file in the directory. Do not edit the shared `.gitignore`, stage, commit, or push notes unless the user explicitly requests it. If exclusion fails, report it before saving potentially sensitive context.
3. If the older `.claude/session-handoff.local.md` exists, read it and carry still-relevant facts into the topic files; leave it intact. Reuse existing topic files and prompt history from earlier versions rather than starting over.
4. Before doing the requested work, add an `in progress` entry for this request in `PROMPT_HISTORY.md`: timestamp, a short safe summary of the request, the next sequential ID (`P-0001`, `P-0002`, ...), and starting branch/HEAD and pre-existing dirty paths when available. Do not copy the raw prompt or attribute pre-existing work to yourself. If there is no specific task, summarize the current state and next action instead of guessing what to implement.

## While working

- Update only the relevant files after each meaningful milestone: a requirement or decision, an edit, a test result, a blocker, or a change in next steps. Update the entry again before responding, marking it `completed`, `blocked`, or still `in progress` with the exact next action. If saving fails, tell the user; never claim a checkpoint was saved when it was not.
- Record which files **you actually changed** for this request and why. Check the starting Git status and the current workspace to avoid crediting yourself for another person's changes. Record verification commands and observed results, or explicitly say they were not run. Treat earlier checks as potentially stale after code or branch changes.
- Keep `INDEX.md` brief and current. Keep decisions with their rationale; mark superseded choices rather than erasing why they were made. Preserve earlier prompt entries. If history grows unwieldy, move older completed entries to dated files under `archive/` and link them from `INDEX.md`; do not discard them.
- Never put credentials, tokens, environment-file contents, private customer data, or large code/output dumps in the handoff. Use short safe summaries and relative file paths. If another session changed a note while you were working, reread and merge rather than overwriting it.

## Local files

Each file begins with an `Updated: YYYY-MM-DD HH:MM with time zone` line after its title. Create only verified content; leave unknown details as unknown.

| File | Purpose |
| --- | --- |
| `INDEX.md` | Short entrypoint: current focus, next action, branch if relevant, and links to the other files. |
| `PROJECT.md` | Stable orientation: architecture, relevant paths and commands, and enduring preferences. |
| `DECISIONS.md` | Dated decisions, reasons, and superseding decisions. |
| `TASKS.md` | Current requirements, completed work, blockers, and concrete next steps. |
| `VERIFICATION.md` | Dated commands, actual results, untested work, and checks made stale by later edits. |
| `PROMPT_HISTORY.md` | Chronological request-to-change entries. Update the current entry at milestones; retain completed entries. |

Use this shape for each prompt-history entry:

```markdown
## P-0001 - YYYY-MM-DD HH:MM with time zone
- Request: Safe, concise summary of the user's instruction.
- Status: in progress
- Starting state: Branch/HEAD and pre-existing dirty paths, if known.
- Changes: None yet; later list relative paths and what changed.
- Checks: Not run yet; later list commands and observed results.
- Outcome / next step: Pending; later record the result or blocker.
```

## Previous installations

If this project used the older hook-based version, its context files remain useful. On request to migrate, compare `.state.json` with `PROMPT_HISTORY.md` and the archives; carry over any entries missing from Markdown before retiring the old helper. Remove **only** the old session-handoff `UserPromptSubmit` and `Stop` hook handlers from `.claude/settings.local.json` and the block between `<!-- session-handoff:start -->` and `<!-- session-handoff:end -->` in `CLAUDE.local.md`. Preserve all other hooks, settings, instructions, and handoff files. Tell the user to restart Claude Code because old hooks may remain loaded in the current session. After that restart, the old `.claude/skills/session-handoff/scripts/handoff.py` can be removed; never delete the topic files or history while cleaning up. If those files are absent, there is nothing to migrate.

This skill works only when invoked and followed: it cannot run on an inactivity timer or guarantee an update after a sudden reset. Invoke `/session-handoff` at the start of each new session and for important new requests; ask it to save a checkpoint before a long break. Tell the user where notes were saved and whether Git excludes them. An optional private backup is sensible if the entire workspace could be deleted, but it is never required or automatic.
