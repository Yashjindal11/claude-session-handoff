# Claude Session Handoff

A small [Claude Code skill](https://code.claude.com/docs/en/skills) for continuing a project when a terminal session resets or loses its conversation context. It keeps **local, regularly updated** project context files, so a new session can read the important decisions, edits, verification, and next steps. Designed for environments such as MARS where files persist even if the Claude session does not.

The public repository contains only the reusable instructions. Your project context is **not** uploaded here. The skill is prompt-driven, not a background recorder: a sudden reset can still lose work since the last checkpoint. It updates the relevant files after meaningful milestones and before a normal response; you can also save on demand.

## Install in a project

From the root of the project you work on in MARS:

```sh
mkdir -p .claude/skills/session-handoff
curl -fsSL https://raw.githubusercontent.com/Yashjindal11/claude-session-handoff/main/skill/SKILL.md \
  -o .claude/skills/session-handoff/SKILL.md
```

Alternatively, copy [`skill/SKILL.md`](skill/SKILL.md) to `.claude/skills/session-handoff/SKILL.md`. Install it in each project that needs handoffs. Start Claude Code from that project so it discovers the skill.

## Tiny prompt for each new Claude Code session

```text
/session-handoff Resume from the saved handoff, then: <your instructions>
```

For example:

```text
/session-handoff Resume from the saved handoff, then: finish the login tests.
```

To save right now without starting another task:

```text
/session-handoff Save a checkpoint of the current work.
```

On first use, the skill creates this directory at the project root:

```text
.claude/session-handoff.local/
├── INDEX.md         # Short entrypoint and links to the other files
├── PROJECT.md       # Project orientation and enduring preferences
├── DECISIONS.md     # Decisions and their rationale
├── TASKS.md         # Active work, milestones, blockers, next steps
└── VERIFICATION.md  # Commands, results, and remaining checks
```

Later sessions read `INDEX.md` and the other files, check them against the real workspace, and continue your request. The skill updates only the relevant files as work progresses. If you previously used the single-file version, it migrates useful information from `.claude/session-handoff.local.md` without deleting that file.

In Git projects, the skill adds the context directory to the **local Git exclude file** so it remains untracked without changing the project's shared `.gitignore`. The installed skill can be committed to your project if you want teammates to use it; the context stays local by default. If you explicitly choose to version the context, review it for sensitive information first and remove its local exclusion or force-add the files yourself.

The files summarize important context rather than attempting to recreate every message. They do not replace committed code, tests, or a review of the current working tree. If the project directory is deleted between sessions, the local context disappears too; back it up separately if you need that level of durability.

## License

MIT. See [LICENSE](LICENSE).
