---
name: session-handoff
description: "Resume Claude Code after a reset using a local project handoff, or save a checkpoint before stopping. Use when continuing work across sessions, preserving decisions, recording progress, or recovering context after inactivity."
---

# Session handoff

The user's request for this invocation is:

$ARGUMENTS

Use this workflow in the project where Claude Code was started. The durable handoff is `<project-root>/.claude/session-handoff.local.md`. The project root is the Git worktree root if there is one, otherwise the current working directory. Do not store the handoff in this skill's repository unless that repository is the project being worked on.

## At the start of an invocation

1. Locate the project root and read the handoff if it exists. If it does not, create it using the format below, recording only facts you can verify from the user's instructions and the project. Never invent prior conversation or claim that unsaved context was recovered.
2. Check the current working tree (`git status --short` if this is a Git project) and the files relevant to the pending task. Treat the handoff as a lead, not as proof that a change exists or a test passed. Resolve discrepancies against the actual workspace; ask the user if the intended direction is still unclear. The user's latest instructions take precedence.
3. Keep the handoff local by default. In a Git project, if it is not already ignored, add the exact root-anchored path `/.claude/session-handoff.local.md` to the repository's local exclude file (`git rev-parse --git-path info/exclude`), not to a tracked `.gitignore`. Do not duplicate an existing rule. If the handoff is already tracked, tell the user; an exclude rule cannot make a tracked file private. Do not untrack, stage, commit, or push it without explicit instructions. If local exclusion fails, report that failure before writing potentially sensitive context.
4. If the request is to save a checkpoint, update the handoff and stop. If there is a task, briefly orient yourself from the handoff and workspace, then do the task. If there is no specific task, summarize the current state and next action rather than guessing what to implement.

## While working

- Update the handoff after each meaningful milestone: a new user requirement or decision, a completed edit, a test result, a blocker, or a change in next steps. Update it again before your final response. Do not rely on an inactivity timer or an end-of-session hook: the session may reset without warning.
- Keep a useful snapshot, not a full chat transcript. Record what a new agent needs to continue: exact relative file paths, why decisions were made, commands and their observed results, unresolved questions, and a concrete next step. Distinguish verified results from plans and from untested work. Preserve still-relevant information when rewriting the snapshot.
- Never copy secrets, tokens, credentials, environment-file contents, private customer data, or large source/output dumps into the handoff. Refer to the location of sensitive material without reproducing it. Check before intentionally sharing or committing any handoff.
- Do not overwrite unrelated work or silently dismiss inconsistencies. If a save fails, say so explicitly; do not claim continuity was preserved.

## Handoff format

Create or maintain these sections in `.claude/session-handoff.local.md`; omit empty sections, and keep older milestones only while they are still useful:

```markdown
# Session handoff

Updated: YYYY-MM-DD HH:MM with time zone

## Goal and user requirements
- Current task, acceptance criteria, and user preferences.

## Project orientation
- Relevant relative paths, entry points, and commands to run.

## Decisions and completed work
- What changed, where, and why; distinguish saved changes from proposals.

## Verification
- Commands run and actual outcomes; identify anything not tested.

## Open issues and next steps
- Blockers, unanswered questions, and the first concrete action to take next.

## Recent checkpoints
- Date/time: concise milestone or important change in direction.
```

After updating the file, tell the user where the handoff was saved and whether it is excluded from Git.
