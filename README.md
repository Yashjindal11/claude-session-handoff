# Claude Session Handoff

A [Claude Code skill](https://code.claude.com/docs/en/skills) for environments such as MARS where the conversation resets but project files survive. It maintains **local, regularly updated** project context: decisions, tasks, verification, and a prompt-by-prompt change history. The public repository contains reusable instructions and tools, not your project's notes.

## Install in an existing project

Run these commands from the project root (the worktree root in a Git project). Requires Python 3.9+ on Linux or macOS; Git is optional. No GitHub login or backup repository is needed.

```sh
mkdir -p .claude/skills/session-handoff/scripts
curl -fsSL https://raw.githubusercontent.com/Yashjindal11/claude-session-handoff/v1.1.0/skill/SKILL.md \
  -o .claude/skills/session-handoff/SKILL.md
curl -fsSL https://raw.githubusercontent.com/Yashjindal11/claude-session-handoff/v1.1.0/skill/scripts/handoff.py \
  -o .claude/skills/session-handoff/scripts/handoff.py
python3 .claude/skills/session-handoff/scripts/handoff.py install
```

The versioned URLs pin an installation to known files. Rerun these commands to upgrade an older installation. The installer does not overwrite your existing local instructions or hook settings: it adds a short, marked block to `CLAUDE.local.md` and merges two hooks into `.claude/settings.local.json`. It is safe to rerun. **Restart Claude Code** after installing so the new instructions and hooks load. If either existing file is invalid or the local handoff is tracked by Git, installation stops with an error rather than erasing it or storing private context in a tracked path.

For non-Git projects, files remain in the working directory. For Git projects, the installer excludes the context directory, `CLAUDE.local.md`, and `.claude/settings.local.json` using the repository's local Git exclude file, not its shared `.gitignore`. You can commit the installed skill itself to share it with teammates; their local handoffs stay separate.

## One short prompt per new session

```text
/session-handoff Resume from the saved handoff, then: <your task>
```

To save without a new task:

```text
/session-handoff Save a checkpoint of the current work.
```

The `UserPromptSubmit` hook begins a numbered, **raw-prompt-free** entry before each turn. An always-loaded local reminder tells Claude to update the relevant files after milestones. The `Stop` hook requests a final checkpoint if the entry remains open; it allows stopping after one reminder to avoid an infinite loop. Hooks can also run on scheduled or automated turns, not just messages typed by a person.

The local files are:

```text
.claude/session-handoff.local/
├── INDEX.md           # Start here: current focus, next step, links
├── PROJECT.md         # Architecture, paths, commands, preferences
├── DECISIONS.md       # Dated decisions and superseded choices
├── TASKS.md           # Active work, milestones, blockers
├── VERIFICATION.md    # Observed test results and stale checks
├── PROMPT_HISTORY.md  # Recent request-to-change entries
└── archive/           # Older completed entries, by month
```

The helper also keeps an internal state file and lock in that excluded directory. Topic-file updates use a SHA-256 precondition and atomic replacement so overlapping sessions cannot silently overwrite each other's work. History updates take a file lock. `status` reports the starting and current branch/HEAD and flags checks when the worktree changes after they were recorded. The helper cannot determine whether a reported test actually ran or distinguish every human edit from an agent edit; Claude must inspect the real workspace.

On first use after the older single-file version, the installer retains `.claude/session-handoff.local.md` and links to it from `INDEX.md`. Ask Claude to transfer still-relevant facts to the new topic files; it must not fabricate missing earlier prompts.

## Try it

The [two-prompt walkthrough](examples/two-prompts.md) shows the files after a task, a reset, and a resumed task. To test the helper without a Claude Code account:

```sh
python3 -m unittest discover -s tests -v
```

Tests simulate hook inputs, interrupted and completed prompts, concurrent sessions, Git exclusions, migration, archives, and stale writes. Running inside Claude Code is still necessary to confirm that your particular MARS version supports the hooks; use `/context` to check that `CLAUDE.local.md` loaded.

## Privacy, backups, and limits

The helper does **not** copy the raw prompt into the handoff; Claude should save only a safe summary. Do not include credentials, private customer data, environment-file contents, or large code dumps in the context files. Their local Git exclusion is not a security boundary if you deliberately copy, stage, or upload them.

If MARS deletes the entire working directory, these local files disappear too. If that is a concern, you *may* periodically copy the directory to a private location or private repository after reviewing it for sensitive content. **Backups and Git operations are optional**, never automatic, and are not required for normal use.

This is not a background recorder. A sudden reset or interruption can lose progress made since the last checkpoint, and the Stop hook does not run on a user interrupt or API error. The beginning of the next prompt should still show an in-progress entry; Claude must inspect and reconcile it with the actual workspace. The tool supports Python 3.9+ on Linux/macOS and uses only the standard library.

## License

MIT. See [LICENSE](LICENSE).
