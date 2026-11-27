# herdr-skill

A Claude Code skill for the [Herdr](https://herdr.dev) terminal app. Herdr already lets an agent split panes and open tabs one command at a time; this skill adds the jobs that take several steps to get right:

- **Even grids.** Herdr's split always halves a pane, so three columns come out 50/25/25. `grid` builds any rows × columns layout and drags the borders until the panes are the same size.
- **One agent per task, each in its own worktree.** Give it a file with one task per line. Each pane gets its own git branch and checkout, and starts `claude` (or any agent) with its task as the first message, so parallel agents never edit the same files.
- **Remote machines.** Open a grid in a new space on any machine Herdr is connected to.
- **Saved setups.** Save your spaces, tabs, folders and programs under a name, and open them again in one step.
- **Safe cleanup.** `close` refuses while an agent is working, an editor is open or a worktree has uncommitted changes. Removing worktrees always keeps their branches.

You ask in your own words ("open a 2x2 grid with claude in each pane", "put these four issues in parallel worktrees"), and Claude runs the right command.

This is an unofficial add-on; it is not made by the Herdr developers.

## Install

In Claude Code:

```
/plugin marketplace add rmoetwil/herdr-skill
/plugin install herdr@herdr-skill
```

Or, without the plugin system, copy `skills/herdr` to `~/.claude/skills/herdr`. The skill folder follows the open Agent Skills format, so other agents that read `SKILL.md` files can use it too.

## Requirements

- The Herdr desktop app, with `herdr-app` and `hc` on your `PATH`. Tested with herdr-app 0.1.18 and hc 0.1.22 on macOS.
- Python 3.9 or later, and git for worktrees.

## Use the script directly

Everything the skill does goes through one script, `skills/herdr/scripts/herd.py`, which prints JSON:

```sh
herd.py grid --rows 2 --cols 3 --name review --argv '["claude"]'
herd.py grid --name fix-auth --folder ~/code/app --tasks tasks.txt --worktrees --base main
herd.py grid --machine my-server --cols 2 --name logs
herd.py save work            # the shown space; --all for every space
herd.py open work
herd.py list
herd.py even --tab TAB_ID
herd.py close --tab TAB_ID --remove-worktrees
```

Setups are stored in `~/.config/herdr-skill/setups/`. They record folders and programs per tab, not the exact split shapes: `open` lays each tab out as an even grid. Agents restart fresh, not resumed.

## Known limits

- Herdr only sizes terminals while its window is on screen. If you build a grid while another app is in front, the panes keep the halving split and the output says `"even": false`; run `herd.py even --tab TAB_ID` with Herdr in front.
- Remote grids are never evened, because Herdr does not report remote terminal sizes.
- Worktrees are created on the local machine only.

## License

MIT
