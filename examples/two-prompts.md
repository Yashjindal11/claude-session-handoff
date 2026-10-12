# Two-prompt handoff example

This is illustrative; it does not run a Claude Code session.

1. From the project root, install the skill using the commands in the [README](../README.md), then restart Claude Code.
2. Ask: `/session-handoff Resume from the saved handoff, then: add login tests.`
3. Before Claude starts working, the prompt hook creates `P-0001` with status `in progress` and a safe placeholder instead of the raw prompt. Claude checks the repository, updates `TASKS.md`, runs the tests, and finalizes `P-0001`. The resulting `PROMPT_HISTORY.md` might contain:

   ```text
   ## P-0001 - 2026-10-12T21:00+05:30
   - Prompt: Add login tests.
   - Status: completed
   - Changes:
     - `tests/login.test.ts` - Added invalid-token coverage.
   - Checks:
     - `npm test -- login` - passed (HEAD `abc123`).
   - Outcome / next step: Tests added; review the login error copy next.
   ```

4. The Claude conversation resets, but `.claude/session-handoff.local/` remains. Start a new session and ask: `/session-handoff Resume from the saved handoff, then: review the login error copy.`
5. The new prompt hook creates `P-0002`. Claude reads `INDEX.md`, checks the actual working tree against the recorded branch/HEAD, and consults the recent history. It updates `TASKS.md` and `P-0002` as it works; it does not assume `P-0001`'s test result still applies if code has since changed.

If the first session stops unexpectedly before step 3 finishes, `P-0001` remains `in progress`. The next session should reconcile it with the real files rather than claiming it completed. A Stop-hook reminder on a normal response helps catch an unfinished entry, but cannot protect a sudden shutdown.
