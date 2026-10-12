# Claude Session Handoff

An instruction-only [Claude Code skill](https://code.claude.com/docs/en/skills) for projects where a terminal conversation resets but files persist. Claude keeps concise local notes about the project, decisions, current work, checks, and which user request led to which changes. **No Python, packages, hooks, or project-specific runtime are needed.**

## Install in a project

From that project's root:

```sh
mkdir -p .claude/skills/session-handoff
curl -fsSL https://raw.githubusercontent.com/Yashjindal11/claude-session-handoff/v1.2.0/skill/SKILL.md \
  -o .claude/skills/session-handoff/SKILL.md
```

Alternatively, copy [skill/SKILL.md](skill/SKILL.md) to `.claude/skills/session-handoff/SKILL.md`. Start a new Claude Code session from the project so the skill is discovered. This installation works regardless of the language used by the project.

## Use it

At the start of a new session:

```text
/session-handoff Resume from the saved handoff, then: <your task>
```

For an important new request in the same session, invoke it again with the new task. To save without starting another task:

```text
/session-handoff Save a checkpoint of the current work.
```

The skill asks Claude to create and update these files in `.claude/session-handoff.local/`:

```text
INDEX.md           Short entrypoint and next action
PROJECT.md         Project orientation and lasting preferences
DECISIONS.md       Decisions and rationale
TASKS.md           Active work and blockers
VERIFICATION.md    Commands, results, and stale checks
PROMPT_HISTORY.md  Dated entries linking requests to actual changes
```

Claude should check the real working tree before trusting old notes, start an `in progress` entry before work, update relevant files at milestones, and record the outcome before responding. In a Git project it should exclude the handoff directory locally, without changing the shared `.gitignore`. No Git action or backup repository is required from the user.

**This is intentionally simpler, but less automatic than the older version.** There is no hook or background process to capture prompts or force a save. A reset can lose progress since the last checkpoint, and Claude must actually follow the skill instructions. The history uses safe summaries, not full transcripts. If the entire project directory disappears, so do local notes; a private backup is optional, not required.

## Upgrading from the older hook-based version

The handoff files and their history are still useful. Install the new skill, then ask:

```text
/session-handoff Migrate this project from the older hook-based handoff. Keep all context files; remove only the old handoff hooks and marked local reminder.
```

Claude should first check whether the old `.state.json` contains entries missing from the Markdown history, then remove only the old session-handoff handlers from `.claude/settings.local.json` and the `session-handoff:start` / `session-handoff:end` block in `CLAUDE.local.md`. Preserve unrelated settings and instructions. **Restart Claude Code** after that cleanup; hooks from the old session might still be active until restart. The retired helper under `.claude/skills/session-handoff/scripts/` can then be removed. Do not remove `.claude/session-handoff.local/` or its archived history. Older release tags remain available for people who still use them.

## License

MIT. See [LICENSE](LICENSE).
