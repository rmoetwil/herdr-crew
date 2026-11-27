# herdr-crew

A skill for Claude Code, OpenCode and the Antigravity CLI for running a crew of agents in the [Herdr](https://herdr.dev) desktop app. Herdr already lets an agent split panes and open tabs one command at a time; this skill adds the jobs that take several steps to get right:

- **Even grids.** Herdr's split always halves a pane, so three columns come out 50/25/25. `grid` builds any rows × columns layout and drags the borders until the panes are the same size.
- **One agent per task, each in its own worktree.** Give it a file with one task per line. Each pane gets its own git branch and checkout, and starts `claude` (or any agent) with its task as the first message, so parallel agents never edit the same files.
- **A different agent per pane.** `--programs '["claude", "claude", "agy", "opencode"]'` starts any mix of programs, one per pane.
- **Remote machines.** Open a grid in a new space on any machine Herdr is connected to.
- **Saved setups.** Save your spaces, tabs, folders and programs under a name, and open them again in one step.
- **Safe cleanup.** `close` refuses while an agent is working, an editor is open or a worktree has uncommitted changes. Removing worktrees always keeps their branches.

You ask in your own words ("open a 2x2 grid with claude in each pane", "put these four issues in parallel worktrees"), and the agent runs the right command.

This is an unofficial add-on; it is not made by the Herdr developers. Herdr ships its own official skill, [`herdr`](https://github.com/herdrdev/herdr/tree/master/skills/herdr), for the `herdr` terminal UI. This one has a different name so both can be installed side by side, and it drives the desktop app (`herdr-app`).

## Install

### Claude Code


```
/plugin marketplace add rmoetwil/herdr-crew
/plugin install herdr-crew@herdr-crew
```

Or, without the plugin system, copy `skills/herdr-crew` to `~/.claude/skills/herdr-crew`. The skill folder follows the open Agent Skills format, so other agents that read `SKILL.md` files can use it too.

### OpenCode

OpenCode has no skill installer, so clone the repository and link the skill folder into OpenCode's global skills folder. A `git pull` then updates it:

```sh
git clone https://github.com/rmoetwil/herdr-crew.git ~/code/herdr-crew
mkdir -p ~/.config/opencode/skills
ln -s ~/code/herdr-crew/skills/herdr-crew ~/.config/opencode/skills/herdr-crew
```

For one project only, link it into that project's `.opencode/skills/` instead. OpenCode also reads `~/.claude/skills/`, so a copy installed there for Claude Code works in OpenCode too. A Claude Code plugin install does not, because it lives in Claude Code's plugin folder.

The model must support tool calling. Smaller local models may not pick the skill on their own; naming it in the request ("use the herdr-crew skill to ...") helps.

### Antigravity CLI

Clone the repository and install it as a plugin. Antigravity converts the Claude Code plugin and copies it to `~/.gemini/config/plugins/herdr-crew`:

```sh
git clone https://github.com/rmoetwil/herdr-crew.git ~/code/herdr-crew
agy plugin install ~/code/herdr-crew
```

To update, run `git pull` in the clone and the same `agy plugin install` again: it replaces the installed copy. `agy plugin list` shows the installed version. `agy plugin install` takes a local folder, not a GitHub URL.

Without the plugin system, copy the skill folder instead, into `~/.gemini/config/skills/`, into `~/.agents/skills/` (which OpenCode reads too), or into a project's `.agents/skills/`. Copy it: a symbolic link did not load in a project's `.agents/skills/` when tested.

### More than one agent on the same computer

Use one install per tool: the Claude Code plugin, a symlink in `~/.config/opencode/skills/` for OpenCode, and `agy plugin install` for Antigravity. Each tool then reads only its own copy. Do not combine the Antigravity plugin with a copy in `~/.agents/skills/`: Antigravity would find two skills named `herdr-crew`, and the copies can drift to different versions.

In print mode (`agy -p`), Antigravity cannot ask for permission, so allow the commands the skill runs, for example `agy --settings '{"permissions":{"allow":["command(python3)","command(herdr-app)"]}}' -p "..."`.

## Requirements

- The Herdr desktop app, with `herdr-app` and `hc` on your `PATH`. Tested with herdr-app 0.1.18 and hc 0.1.22 on macOS.
- Python 3.9 or later, and git for worktrees.

## Use the script directly

Everything the skill does goes through one script, `skills/herdr-crew/scripts/herd.py`, which prints JSON:

```sh
herd.py grid --rows 2 --cols 3 --name review --argv '["claude"]'
herd.py grid --rows 2 --cols 2 --name crew --programs '["claude", "claude", "agy", "opencode"]'
herd.py grid --name fix-auth --folder ~/code/app --tasks tasks.txt --worktrees --base main
herd.py grid --machine my-server --cols 2 --name logs
herd.py save work            # the shown space; --all for every space
herd.py open work
herd.py list
herd.py even --tab TAB_ID
herd.py close --tab TAB_ID --remove-worktrees
```

Setups are stored in `~/.config/herdr-crew/setups/`. They record folders and programs per tab, not the exact split shapes: `open` lays each tab out as an even grid. Agents restart fresh, not resumed.

## Known limits

- Herdr only sizes terminals while its window is on screen. If you build a grid while another app is in front, the panes keep the halving split and the output says `"even": false`; run `herd.py even --tab TAB_ID` with Herdr in front.
- Remote grids are never evened, because Herdr does not report remote terminal sizes.
- Worktrees are created on the local machine only.

## License

MIT
