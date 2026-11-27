---
name: herdr-crew
description: Arrange the Herdr desktop app (herdr-app) from the command line. Use when asked to open, split, arrange, save, list, reopen or close Herdr spaces, tabs, panes, terminals or saved setups, such as "a 2x2 grid with claude in each pane", "four agents on these tasks, each in its own worktree", "a pane on my server" or "save this setup". Also use for a plain request to open a program, shell, terminal, tab or pane while this session runs inside Herdr (`HC_TERMINAL_ID` is set), even when Herdr is not named, such as "open opencode in a terminal".
---

# Herdr crew

Herdr is the terminal app this session may be running in. `herdr-app` changes what the window shows; `hc` runs, reads and talks to the terminals behind it. `scripts/herd.py` in this skill's folder does the multi-step jobs below; it prints JSON, and on failure `{"error": ...}` with exit code 1. It is not on the `PATH`: `herd.py` below is short for `python3 <this skill's folder>/scripts/herd.py`, with the folder that holds this `SKILL.md`.

When `HC_TERMINAL_ID` is set, this session runs inside Herdr: open every requested terminal, tab or pane in Herdr, never in a separate terminal application.

## Steps

1. Read the current guide before the first command in a session: `herdr-app --skill`. It is the source of truth for single commands; `herdr-app commands` lists every argument. For starting, reading or messaging agents without changing the screen, read `hc --skill`.
2. Inspect with `herdr-app ls` (spaces, tabs, terminals, pane IDs, machines) and `herdr-app status` (the shown space and tab). Act on IDs from there.
3. Pick the job:

   | Job | Command |
   | --- | --- |
   | One program in a new tab | `herdr-app do terminal.open --argv '["opencode"]' --folder DIR --place tab --name OpenCode` (leave out `--argv` for a plain shell) |
   | One program in a split pane | the same with `--place right` or `--place down`, beside the focused pane |
   | Close one pane | `herdr-app do pane.close --pane ID` (see Gotchas: this stops its program) |
   | Grid of terminals | `herd.py grid --rows 2 --cols 2 --name review [--folder DIR] [--argv '["claude"]']` |
   | A different program per pane | `herd.py grid --rows 2 --cols 2 --name crew --programs '["claude", "claude", "agy", "opencode"]'` |
   | One agent per task, each on its own branch | `herd.py grid --name fix-auth --folder REPO --tasks FILE --worktrees [--base main]` |
   | Grid on another machine | `herd.py grid --machine NAME --cols 2 --name remote` (`hc machine ls` lists machines) |
   | Save spaces as a setup | `herd.py save NAME [--space ID ...] [--all]` (default: the shown space) |
   | Open a setup / list setups | `herd.py open NAME` / `herd.py list` |
   | Even out a grid later | `herd.py even --tab ID` |
   | Close a tab or space | `herd.py close --tab ID` or `--space ID`, plus `--remove-worktrees` for worktree grids |

4. Done when `herdr-app ls` shows the expected tabs and panes and `herdr-app shot <temp dir>/herdr.png` looks right. Look at the picture before reporting; if you cannot view images, check the `herdr-app ls` output instead and say the screenshot was not checked.

## Grids

- Without `--space` or `--machine`, the grid opens in the **shown** space, on that space's machine. `--focus false` puts the previously shown tab back afterwards.
- `--programs`: one entry per pane in grid order (left to right, top to bottom). An entry is a command on the pane's PATH (`"opencode"`), a list with arguments (`["claude", "--model", "opus"]`) or `null` for a plain shell. It replaces `--argv`, and sizes the grid to its length unless `--rows`/`--cols` are given. With `--tasks`, give one program per task: each pane gets its program plus its task.
- `--tasks FILE`: one task per line (`#` lines skipped). Each pane gets `argv` plus its task as the last argument, so `claude` starts with that first message. The grid sizes itself to the number of tasks unless `--rows`/`--cols` are given. `--argv` defaults to `["claude"]` with tasks or worktrees.
- `--worktrees`: pane *n* gets branch `<prefix>-n` (prefix: `--branch-prefix`, default the `--name`) checked out at `~/.herdr/worktrees/<repo>/<branch>`, where Herdr's own New/Open/Remove worktree menu finds it. It works on this computer only, and stops before creating anything if a branch or folder already exists. Use it whenever two or more agents will edit the same repo.
- `"even": false` in the output means the panes keep Herdr's halving split (three columns: 50/25/25). The window only sizes terminals while it is on screen, and never reports sizes for remote ones. Tell the user, and run `herd.py even --tab ID` once Herdr is in front.

## Setups

Saved in `~/.config/herdr-crew/setups/NAME.json`: each space's name, machine and tabs, and each terminal's folder and program. Agents are saved by name only (`claude`, `codex`), without session IDs; other programs keep their full command line. Split shapes are not saved: `open` lays each tab out as an even grid. It skips a space whose name and machine are already open.

## Closing

`close` refuses, and lists why, when an agent is working or blocked, a non-agent program is running (an editor, `top`), or a worktree has uncommitted changes. Show the user that list and let them decide; pass `--force` only when they say so. `--remove-worktrees` removes only clean worktrees and always keeps their branches.

## Gotchas

- Herdr runs every `argv` inside a login shell (`zsh -lic '"$@"; exec "$0" -li'`), so a pane returns to a shell when its program exits. "Open X in a shell" therefore needs no extra step: start X with `--argv` as usual, without typing it into a plain shell.
- `pane.close` stops the pane's program: its terminal ends as `finished`, not parked. Unlike `herd.py close`, it does not check for unfinished work, so check `hc get <terminal>` first when the pane runs something you did not start.
- `pane.resize` works only on the shown tab, and moves the border on the named side outward: grow a pane with `right`/`down`, shrink it by growing its neighbour `left`/`up`.
- `hc get` lacks `foreground` for some programs (macOS hides `top`'s); fall back to its `argv`.
- Leave the user's other tabs alone; close only what you opened.
