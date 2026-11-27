#!/usr/bin/env python3
"""Arrange Herdr from the command line: grids, saved setups and cleanup.

  herd.py grid   [--rows R --cols C] [--name N] [--folder DIR]
                 [--space ID | --machine M] [--argv JSON] [--tasks FILE]
                 [--worktrees [--base REF] [--branch-prefix P]] [--focus false]
  herd.py save   NAME [--space ID ...] [--all]
  herd.py open   NAME
  herd.py list
  herd.py even   --tab ID
  herd.py close  (--tab ID | --space ID) [--remove-worktrees] [--force]

Every command prints what it made or did as JSON.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Outside the skill folder: a plugin's folder is replaced on every update.
SETUPS = Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "herdr-crew" / "setups"
WORKTREES = Path(os.path.expanduser("~/.herdr/worktrees"))
SHELLS = {"zsh", "bash", "sh", "fish", "dash", "ksh", "-zsh", "-bash"}


class Fail(Exception):
    pass


# ---------- talking to Herdr ----------

def run(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise Fail(f"{' '.join(cmd[:3])}: {(p.stdout + p.stderr).strip()}")
    return p.stdout


def do(command, **args):
    """herdr-app do <command> with the given arguments; returns the reply."""
    cmd = ["herdr-app", "do", command]
    for k, v in args.items():
        if v is None:
            continue
        cmd += [f"--{k}", json.dumps(v) if isinstance(v, (list, dict, bool)) else str(v)]
    reply = json.loads(run(*cmd))
    if "error" in reply:
        raise Fail(f"{command}: {reply['error']}")
    return reply


def ls():
    return json.loads(run("herdr-app", "ls"))["spaces"]


def status():
    return json.loads(run("herdr-app", "status"))


def term(address):
    return json.loads(run("hc", "get", address))


def find_tab(tab_id):
    for s in ls():
        for t in s["tabs"]:
            if t["id"] == tab_id:
                return s, t
    raise Fail(f"no tab {tab_id}")


def find_space(space_id):
    for s in ls():
        if s["id"] == space_id:
            return s
    raise Fail(f"no space {space_id}")


def pane_of(terminal):
    for s in ls():
        for t in s["tabs"]:
            for x in t["terminals"]:
                if x["terminal"] == terminal:
                    return x["pane"]
    raise Fail(f"no pane shows terminal {terminal}")


def launch(argv, machine):
    """Herdr itself runs argv in a login shell (zsh -lic '"$@"; exec "$0" -li'),
    which stays as the pane's shell when the program exits."""
    return argv or None


def program(d):
    """The program in a terminal from hc get: the foreground process, with
    Herdr's login-shell wrapper taken off."""
    argv = (d.get("foreground") or {}).get("argv") or d.get("argv") or []
    if len(argv) > 4 and argv[1] == "-lic" and argv[2].startswith('"$@"'):
        argv = argv[4:]
    name = os.path.basename(argv[0]) if argv else None
    return (None, None) if not name or name in SHELLS else (name, argv)


# ---------- building a grid in a tab ----------

def shape(n, rows=None, cols=None):
    if rows and cols:
        return rows, cols
    if rows:
        return rows, math.ceil(n / rows)
    if cols:
        return math.ceil(n / cols), cols
    cols = math.ceil(math.sqrt(n))
    return math.ceil(n / cols), cols


def fill(tab_id, root_terminal, cells, rows, cols, machine):
    """The tab holds one terminal (cells[0]); add the rest as a grid filled
    row by row, label each terminal with its cell, then even the sizes.
    Each cell is {folder, argv}. Returns (pane IDs row by row, evened)."""
    n = len(cells)
    do("tab.select", id=tab_id)
    time.sleep(1)  # let the window lay the tab out
    panes, terms = {0: pane_of(root_terminal)}, {0: root_terminal}

    def add(index, beside, place):
        do("pane.focus", pane=panes[beside])
        c = cells[index]
        r = do("terminal.open", place=place, folder=c.get("folder"),
               argv=launch(c.get("argv"), machine))
        panes[index], terms[index] = r["pane"], r["terminal"]

    for c in range(1, min(cols, n)):
        add(c, c - 1, "right")
    for c in range(min(cols, n)):
        for r in range(1, rows):
            if r * cols + c < n:
                add(r * cols + c, (r - 1) * cols + c, "down")
    for i, t in terms.items():  # lets `herd.py even` find the grid again
        run("hc", "label", t, f"herd.cell={i // cols},{i % cols}")

    time.sleep(0.5)
    grid = [[panes[r * cols + c] for c in range(cols) if r * cols + c < n]
            for r in range(rows)]
    cellmap = {(i // cols, i % cols): (panes[i], terms[i]) for i in range(n)}
    return grid, (False if machine else even_grid(cellmap))


DEFAULT = (120, 40)  # what hc reports for a terminal the window never sized


def even_grid(cells):
    """cells: {(row, col): (pane, terminal)}. Even the columns, then the rows
    in each column. Returns False when the sizes are not live: the window
    only resizes terminals while it is on screen."""
    sizes = [term(t) for _, t in cells.values()]
    if any((d["cols"], d["rows"]) == DEFAULT for d in sizes):
        return False
    cols = sorted({c for _, c in cells})
    top = [cells[(min(r for r, c2 in cells if c2 == c), c)] for c in cols]
    even([t for _, t in top], [p for p, _ in top], "cols")
    for c in cols:
        col = [cells[k] for k in sorted(k for k in cells if k[1] == c)]
        even([t for _, t in col], [p for p, _ in col], "rows")
    return True


def even(terms, panes, dim):
    """pane.split and terminal.open halve a pane, so three panes in a row come
    out 50/25/25. pane.resize moves the border on the named side outward:
    grow pane i with right/down, shrink it by growing pane i+1 left/up."""
    if len(panes) < 2:
        return
    grow, back = ("right", "left") if dim == "cols" else ("down", "up")
    size = lambda i: term(terms[i])[dim]
    want = sum(size(i) for i in range(len(panes))) // len(panes)
    ppc = 8 if dim == "cols" else 20  # first guess at pixels per cell
    for i in range(len(panes) - 1):
        for _ in range(4):
            have = size(i)
            if abs(have - want) <= 1:
                break
            px = abs(want - have) * ppc
            if want > have:
                do("pane.resize", pane=panes[i], direction=grow, px=px)
            else:
                do("pane.resize", pane=panes[i + 1], direction=back, px=px)
            time.sleep(0.3)
            now = size(i)
            if now != have:
                ppc = max(1, px // abs(now - have))


# ---------- grid ----------

def git(repo, *args):
    return run("git", "-C", str(repo), *args).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "grid"


def cmd_grid(a):
    tasks = []
    if a.tasks:
        lines = Path(a.tasks).read_text().splitlines()
        tasks = [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]
    argv = json.loads(a.argv) if a.argv else (["claude"] if tasks or a.worktrees else None)
    n = len(tasks) or (a.rows or 2) * (a.cols or 2)
    rows, cols = shape(n, a.rows, a.cols)
    n = min(n, rows * cols) if not tasks else n
    if tasks and len(tasks) > rows * cols:
        raise Fail(f"{len(tasks)} tasks do not fit {rows}x{cols}")

    # Without --space or --machine, Herdr puts the tab in the shown space.
    space = find_space(a.space or status()["space"]) if not a.machine else None
    machine = a.machine or space["machine"]
    folder = a.folder or (space["folder"] if space and machine else None) or \
        (os.getcwd() if not machine else None)
    cells = [{"folder": folder, "argv": (argv + [tasks[i]]) if argv and i < len(tasks) else argv}
             for i in range(n)]

    made = []
    if a.worktrees:
        if machine:
            raise Fail("--worktrees works on this computer only")
        repo = Path(git(folder, "rev-parse", "--show-toplevel"))
        base = a.base or "HEAD"
        prefix = a.branch_prefix or slug(a.name)
        branches = [f"{prefix}-{i + 1}" for i in range(n)]
        for b in branches:  # check everything before creating anything
            if subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet",
                               f"refs/heads/{b}"], capture_output=True).returncode == 0:
                raise Fail(f"branch {b} already exists; pick another --branch-prefix")
            if (WORKTREES / repo.name / b.replace("/", "-")).exists():
                raise Fail(f"{WORKTREES / repo.name / b} already exists")
        for i, b in enumerate(branches):
            path = WORKTREES / repo.name / b.replace("/", "-")
            path.parent.mkdir(parents=True, exist_ok=True)
            git(repo, "worktree", "add", "-b", b, str(path), base)
            cells[i]["folder"] = str(path)
            made.append({"branch": b, "folder": str(path)})

    before = status()["tab"]
    first = cells[0]
    if a.machine:
        r = do("space.new", name=a.name, tab=a.name, machine=a.machine,
               folder=first["folder"], argv=launch(first["argv"], machine), focus=True)
    else:
        r = do("tab.new", name=a.name, space=a.space, folder=first["folder"],
               argv=launch(first["argv"], machine), focus=True)
    tab_id = r["tab"]
    grid, evened = fill(tab_id, r["terminal"], cells, rows, cols, machine)
    if a.focus == "false":
        do("tab.select", id=before)
    out = {"tab": tab_id, "space": r.get("space"), "panes": grid, "even": evened,
           "worktrees": made}
    if not evened:
        out["note"] = NOT_EVEN
    print(json.dumps(out, indent=2))


NOT_EVEN = ("sizes not evened: the window only sizes terminals while it is on screen "
            "(and never for remote ones); run `herd.py even --tab ID` with Herdr in front")


def cmd_even(a):
    _, tab = find_tab(a.tab)
    do("tab.select", id=a.tab)
    time.sleep(1)
    cells = {}
    for x in tab["terminals"]:
        cell = term(x["terminal"]).get("labels", {}).get("herd.cell")
        if not cell:
            raise Fail(f"{x['terminal']} has no herd.cell label: only grids made by herd.py can be evened")
        r, c = map(int, cell.split(","))
        cells[(r, c)] = (x["pane"], x["terminal"])
    evened = even_grid(cells)
    print(json.dumps({"tab": a.tab, "even": evened} | ({} if evened else {"note": NOT_EVEN}), indent=2))


# ---------- save / open / list ----------

def capture(space):
    tabs = []
    for t in space["tabs"]:
        terms = []
        for x in t["terminals"]:
            d = term(x["terminal"])
            name, argv = program(d)
            if name and x.get("app"):  # an agent: its arguments hold session IDs
                argv = [name]
            terms.append({"folder": d.get("cwd"), "argv": argv})
        tabs.append({"name": t["name"], "terminals": terms})
    return {"name": space["name"], "machine": space["machine"],
            "folder": space["folder"] or None, "tabs": tabs}


def cmd_save(a):
    spaces = ls()
    if a.all:
        chosen = spaces
    else:
        ids = a.space or [status()["space"]]
        chosen = [s for s in spaces if s["id"] in ids]
        if len(chosen) != len(ids):
            raise Fail("unknown space ID; see herdr-app ls")
    setup = {"spaces": [capture(s) for s in chosen]}
    SETUPS.mkdir(parents=True, exist_ok=True)
    path = SETUPS / f"{a.name}.json"
    path.write_text(json.dumps(setup, indent=2) + "\n")
    print(json.dumps({"saved": str(path), "spaces": [s["name"] for s in chosen]}, indent=2))


def cmd_open(a):
    path = SETUPS / f"{a.name}.json"
    if not path.exists():
        raise Fail(f"no setup {a.name}; saved: {', '.join(p.stem for p in SETUPS.glob('*.json'))}")
    setup = json.loads(path.read_text())
    have = {(s["name"], s["machine"]) for s in ls()}
    opened, skipped, uneven, first_tab = [], [], [], None
    for sp in setup["spaces"]:
        if (sp["name"], sp["machine"]) in have:
            skipped.append(sp["name"])
            continue
        machine = sp["machine"]
        for k, tab in enumerate(sp["tabs"]):
            cells = [{"folder": x["folder"], "argv": x["argv"]} for x in tab["terminals"]] or [{"folder": sp["folder"], "argv": None}]
            c0 = cells[0]
            if k == 0:
                r = do("space.new", name=sp["name"], tab=tab["name"], folder=c0["folder"],
                       machine=machine or "", argv=launch(c0["argv"], machine), focus=True)
                space_id = r["space"]
            else:
                r = do("tab.new", name=tab["name"], space=space_id, folder=c0["folder"],
                       argv=launch(c0["argv"], machine), focus=True)
            rows, cols = shape(len(cells))
            _, evened = fill(r["tab"], r["terminal"], cells, rows, cols, machine)
            if not evened and len(cells) > 2:
                uneven.append(r["tab"])
            first_tab = first_tab or r["tab"]
        opened.append(sp["name"])
    if first_tab:
        do("tab.select", id=first_tab)
    out = {"opened": opened, "already_open": skipped}
    if uneven:
        out |= {"uneven_tabs": uneven, "note": NOT_EVEN}
    print(json.dumps(out, indent=2))


def cmd_list(a):
    out = {}
    for p in sorted(SETUPS.glob("*.json")):
        out[p.stem] = [s["name"] + (f" @ {s['machine']}" if s["machine"] else "")
                       for s in json.loads(p.read_text())["spaces"]]
    print(json.dumps(out, indent=2))


# ---------- close ----------

def cmd_close(a):
    if a.tab:
        space, tab = find_tab(a.tab)
        tabs = [tab]
    else:
        space = find_space(a.space)
        tabs = space["tabs"]
    problems, worktrees = [], set()
    for t in tabs:
        for x in t["terminals"]:
            label = f"{t['name']}/{x['terminal']}"
            if x.get("status") in ("working", "blocked"):
                problems.append(f"{label}: {x.get('app')} is {x['status']}")
            d = term(x["terminal"])
            name, _ = program(d)
            if not x.get("app") and name:
                problems.append(f"{label}: {name} is running")
            cwd = d.get("cwd") or ""
            if not space["machine"] and cwd.startswith(str(WORKTREES) + "/"):
                top = git(cwd, "rev-parse", "--show-toplevel")
                worktrees.add(top)
    for w in sorted(worktrees):
        if git(w, "status", "--porcelain"):
            problems.append(f"{w}: uncommitted changes")
    if problems and not a.force:
        print(json.dumps({"closed": False, "problems": problems,
                          "hint": "finish or save that work, or pass --force"}, indent=2))
        sys.exit(1)

    if a.tab:
        do("tab.close", id=a.tab, confirmed=True)
    else:
        do("space.close", id=a.space, confirmed=True)

    removed, kept = [], []
    for w in sorted(worktrees):
        branch = git(w, "branch", "--show-current")
        if a.remove_worktrees and not git(w, "status", "--porcelain"):
            main = git(w, "rev-parse", "--path-format=absolute", "--git-common-dir")
            git(Path(main).parent, "worktree", "remove", w)
            removed.append({"folder": w, "branch_kept": branch})
        else:
            kept.append({"folder": w, "branch": branch})
    print(json.dumps({"closed": True, "problems_overridden": problems if a.force else [],
                      "worktrees_removed": removed, "worktrees_kept": kept}, indent=2))


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grid", help="a new tab split into an even grid")
    g.add_argument("--rows", type=int)
    g.add_argument("--cols", type=int)
    g.add_argument("--name", default="grid")
    g.add_argument("--folder")
    g.add_argument("--space")
    g.add_argument("--machine", help="make a new space on this machine (hc machine ls)")
    g.add_argument("--argv", help='JSON list, e.g. \'["claude"]\'')
    g.add_argument("--tasks", help="file with one task per line; each pane gets the next")
    g.add_argument("--worktrees", action="store_true", help="a git worktree and branch per pane")
    g.add_argument("--base", help="commit the worktree branches start from (default HEAD)")
    g.add_argument("--branch-prefix", help="branches are <prefix>-1, -2, ... (default: the name)")
    g.add_argument("--focus", default="true", choices=["true", "false"])

    s = sub.add_parser("save", help="save spaces as a named setup")
    s.add_argument("name")
    s.add_argument("--space", action="append")
    s.add_argument("--all", action="store_true")

    o = sub.add_parser("open", help="open a saved setup")
    o.add_argument("name")

    sub.add_parser("list", help="list saved setups")

    e = sub.add_parser("even", help="even out a grid made by herd.py")
    e.add_argument("--tab", required=True)

    c = sub.add_parser("close", help="close a tab or space after checking for unfinished work")
    c.add_argument("--tab")
    c.add_argument("--space")
    c.add_argument("--remove-worktrees", action="store_true")
    c.add_argument("--force", action="store_true")

    a = p.parse_args()
    if a.cmd == "close" and bool(a.tab) == bool(a.space):
        p.error("close needs exactly one of --tab or --space")
    if a.cmd == "grid" and a.machine and a.space:
        p.error("give --space or --machine, not both")
    try:
        {"grid": cmd_grid, "save": cmd_save, "open": cmd_open,
         "list": cmd_list, "close": cmd_close, "even": cmd_even}[a.cmd](a)
    except Fail as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
