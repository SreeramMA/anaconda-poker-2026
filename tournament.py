"""
IIT Pokerbots 2026 — Round-Robin Tournament Runner
===================================================
Runs every bot against every other bot (once each direction) using the
live engine, then produces a rich visualisation of the results.

Usage:
    python tournament.py [--rounds N] [--small_log]

The bots discovered are every *.py file in the BOTS_FOLDER that is NOT
a known support file (pkbot package, __init__, etc.).
"""

import argparse
import os
import subprocess
import sys
import time
import itertools
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")          # headless-safe; we open the PNG ourselves
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
from tabulate import tabulate

# ─── Configuration ────────────────────────────────────────────────────────────
HERE         = Path(__file__).parent.resolve()
BOTS_FOLDER  = HERE / "bots"
ENGINE_PY    = HERE / "engine.py"
PYTHON_CMD   = str(HERE / "venv312" / "bin" / "python")
RESULTS_DIR  = HERE / "tournament_results"
RESULTS_DIR.mkdir(exist_ok=True)

# Files to skip when auto-discovering bots
IGNORED_FILES = {"example.py", "test.py", "__init__.py"}

# Colour palette for each bot (cycles if more bots than colours)
PALETTE = [
    "#6C63FF", "#FF6584", "#43B89C", "#F7B731",
    "#FC5C65", "#45AAF2", "#A55EEA", "#26DE81",
]

# ─── Bot Discovery ────────────────────────────────────────────────────────────

def discover_bots() -> list[dict]:
    """Return a list of {name, file} dicts for every bot .py found."""
    bots = []
    for p in sorted(BOTS_FOLDER.glob("*.py")):
        if p.name in IGNORED_FILES or p.stem.startswith("_"):
            continue
        # derive a pretty name: smart_bot → SmartBot
        name = "".join(w.capitalize() for w in p.stem.split("_"))
        bots.append({"name": name, "file": p.name})
    return bots


# ─── Single Match ─────────────────────────────────────────────────────────────

def run_match(bot1: dict, bot2: dict, num_rounds: int, small_log: bool) -> dict:
    """
    Temporarily write a config.py, run the engine, and parse final bankrolls.
    Returns {"bot1_bankroll": int, "bot2_bankroll": int, "duration": float}.
    """
    cfg_path = HERE / "_tmp_config.py"
    small_flag = "--small_log" if small_log else ""

    cfg_lines = [
        f'PYTHON_CMD = {repr(PYTHON_CMD)}',
        f'GAME_LOG_FOLDER = {repr(str(RESULTS_DIR / "logs"))}',
        f'BOTS_FOLDER = {repr(str(BOTS_FOLDER))}',
        f'BOT_1_NAME = {repr(bot1["name"])}',
        f'BOT_1_FILE_NAME = {repr(bot1["file"])}',
        f'BOT_2_NAME = {repr(bot2["name"])}',
        f'BOT_2_FILE_NAME = {repr(bot2["file"])}',
    ]
    cfg_path.write_text("\n".join(cfg_lines) + "\n")

    # Patch engine to read our temp config
    env = os.environ.copy()
    env["POKERBOTS_CONFIG"] = str(cfg_path)

    cmd = [PYTHON_CMD, str(ENGINE_PY)]
    if small_log:
        cmd.append("--small_log")

    # We temporarily monkeypatch config import by symlinking — simplest approach
    # is to just replace config.py, run, then restore.
    original_cfg = HERE / "config.py"
    backup_cfg   = HERE / "_config_backup.py"
    original_cfg.rename(backup_cfg)
    cfg_path.rename(original_cfg)

    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(HERE)
        )
        duration = time.perf_counter() - t0
        output  = result.stdout + result.stderr
    finally:
        # Always restore config.py
        original_cfg.rename(cfg_path)
        backup_cfg.rename(original_cfg)
        cfg_path.unlink(missing_ok=True)

    # Parse bankrolls from output
    b1, b2 = 0, 0
    for line in output.splitlines():
        if "Total Bankroll:" in line:
            val = int(line.split(":")[-1].strip())
            if b1 == 0 and val != 0:
                b1 = val
            elif b2 == 0 and val != 0:
                b2 = val
    # Fallback: if both parsed or neither, derive from symmetry
    if b1 != 0 and b2 == 0:
        b2 = -b1

    return {"bot1_bankroll": b1, "bot2_bankroll": b2, "duration": duration, "output": output}


# ─── Tournament Logic ─────────────────────────────────────────────────────────

def run_tournament(bots: list[dict], num_rounds: int, small_log: bool) -> dict:
    """
    Run all pairwise matchups (each pair plays once):
    Returns a nested results dict and per-bot aggregate stats.
    """
    n = len(bots)
    pairs = list(itertools.combinations(range(n), 2))
    total = len(pairs)

    # result[i][j] = bankroll bot_i earned when playing bot_j
    result_matrix = defaultdict(lambda: defaultdict(int))
    win_matrix    = defaultdict(lambda: defaultdict(int))   # 1 = i beat j
    match_logs    = []

    print(f"\n{'─'*60}")
    print(f"  ~~ ANACONDA ROUND-ROBIN TOURNAMENT ~~")
    print(f"  {n} bots · {total} matchups · {num_rounds} rounds each")
    print(f"{'─'*60}\n")

    for idx, (i, j) in enumerate(pairs, 1):
        b1, b2 = bots[i], bots[j]
        print(f"  [{idx:>2}/{total}]  {b1['name']:>16}  vs  {b2['name']:<16}", end="", flush=True)
        res = run_match(b1, b2, num_rounds, small_log)
        br1, br2 = res["bot1_bankroll"], res["bot2_bankroll"]
        t       = res["duration"]

        result_matrix[i][j] += br1
        result_matrix[j][i] += br2
        win_matrix[i][j] = 1 if br1 > br2 else (0 if br1 < br2 else None)
        win_matrix[j][i] = 1 if br2 > br1 else (0 if br2 < br1 else None)
        match_logs.append((b1["name"], b2["name"], br1, br2, t))

        winner = b1["name"] if br1 > br2 else (b2["name"] if br2 > br1 else "TIE")
        print(f"  ->  {br1:>+8,}  /  {br2:>+8,}    [{t:.1f}s]  WIN: {winner}")

    # Aggregate per-bot stats
    stats = {}
    for i, bot in enumerate(bots):
        total_br    = sum(result_matrix[i].values())
        wins        = sum(1 for j in range(n) if j != i and win_matrix[i][j] == 1)
        losses      = sum(1 for j in range(n) if j != i and win_matrix[i][j] == 0)
        stats[i] = {
            "name":       bot["name"],
            "total_bankroll": total_br,
            "wins":       wins,
            "losses":     losses,
            "matches":    n - 1,
            "avg_bankroll": total_br / max(n - 1, 1),
        }

    return {
        "stats":          stats,
        "result_matrix":  result_matrix,
        "win_matrix":     win_matrix,
        "match_logs":     match_logs,
        "bots":           bots,
    }


# ─── Visualisation ────────────────────────────────────────────────────────────

def visualise(data: dict, out_path: Path):
    bots   = data["bots"]
    stats  = data["stats"]
    n      = len(bots)
    names  = [bots[i]["name"] for i in range(n)]
    colors = [PALETTE[i % len(PALETTE)] for i in range(n)]

    # Sort by total bankroll descending for leaderboard
    ranked = sorted(stats.values(), key=lambda s: s["total_bankroll"], reverse=True)

    fig = plt.figure(figsize=(18, 14), facecolor="#0F0F1A")
    fig.suptitle(
        "ANACONDA POKERBOTS  -  ROUND-ROBIN TOURNAMENT RESULTS",
        fontsize=18, fontweight="bold", color="white", y=0.98
    )
    gs = GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.38,
                  top=0.93, bottom=0.07, left=0.07, right=0.97)

    ax_bar   = fig.add_subplot(gs[0, :2])   # Total bankroll bar chart
    ax_heat  = fig.add_subplot(gs[0, 2])    # Win/loss heat-map
    ax_ranks = fig.add_subplot(gs[1, 0])    # Win counts
    ax_avg   = fig.add_subplot(gs[1, 1])    # Avg bankroll per match
    ax_table = fig.add_subplot(gs[1, 2])    # Leaderboard table

    bg = "#1A1A2E"
    for ax in [ax_bar, ax_heat, ax_ranks, ax_avg, ax_table]:
        ax.set_facecolor(bg)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")

    def style_ax(ax, title):
        ax.set_title(title, color="white", fontsize=11, fontweight="bold", pad=8)
        ax.tick_params(colors="white", labelsize=8)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    # ── 1. Total Bankroll Bar ──────────────────────────────────────────────────
    rnames = [s["name"] for s in ranked]
    rbrs   = [s["total_bankroll"] for s in ranked]
    rcols  = [colors[names.index(s["name"])] for s in ranked]
    bars   = ax_bar.barh(rnames, rbrs, color=rcols, edgecolor="#222244", height=0.6)
    ax_bar.axvline(0, color="white", linewidth=0.8, alpha=0.4)
    for bar, val in zip(bars, rbrs):
        xpos = val + (max(rbrs) * 0.01 if val >= 0 else min(rbrs) * 0.01)
        ax_bar.text(xpos, bar.get_y() + bar.get_height() / 2,
                    f"{val:+,}", va="center", color="white", fontsize=8, fontweight="bold")
    style_ax(ax_bar, "Total Bankroll (All Matchups)")
    ax_bar.set_xlabel("Chips")
    ax_bar.invert_yaxis()

    # ── 2. Head-to-Head Heat Map ───────────────────────────────────────────────
    heat = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            if i != j:
                heat[i, j] = data["result_matrix"][i][j]

    im = ax_heat.imshow(heat, cmap="RdYlGn", aspect="auto",
                        vmin=np.nanmin(heat), vmax=np.nanmax(heat))
    ax_heat.set_xticks(range(n)); ax_heat.set_xticklabels(names, rotation=45, ha="right", fontsize=7, color="white")
    ax_heat.set_yticks(range(n)); ax_heat.set_yticklabels(names, fontsize=7, color="white")

    for i in range(n):
        for j in range(n):
            if i != j:
                val = heat[i, j]
                ax_heat.text(j, i, f"{int(val):+,}" if abs(val) < 1e6 else f"{val/1000:+.0f}k",
                             ha="center", va="center", fontsize=6,
                             color="white" if abs(val) > np.nanmax(heat) * 0.5 else "#cccccc")
            else:
                ax_heat.text(j, i, "—", ha="center", va="center", fontsize=8, color="#555577")

    plt.colorbar(im, ax=ax_heat, fraction=0.046, pad=0.04).ax.tick_params(colors="white", labelsize=7)
    style_ax(ax_heat, "Head-to-Head Bankroll\n(row beats col → green)")

    # ── 3. Win Count Bar ──────────────────────────────────────────────────────
    wins_sorted = sorted(stats.values(), key=lambda s: s["wins"], reverse=True)
    wnames = [s["name"] for s in wins_sorted]
    wcols  = [colors[names.index(s["name"])] for s in wins_sorted]
    wvals  = [s["wins"] for s in wins_sorted]
    lvals  = [s["losses"] for s in wins_sorted]
    x      = np.arange(len(wnames))
    w      = 0.35
    ax_ranks.bar(x - w/2, wvals, w, label="Wins",   color=wcols, edgecolor="#222244", alpha=0.9)
    ax_ranks.bar(x + w/2, lvals, w, label="Losses", color="#555577", edgecolor="#222244", alpha=0.7)
    ax_ranks.set_xticks(x); ax_ranks.set_xticklabels(wnames, rotation=30, ha="right", fontsize=7)
    ax_ranks.legend(facecolor=bg, labelcolor="white", fontsize=7)
    style_ax(ax_ranks, "Wins / Losses per Bot")

    # ── 4. Average Bankroll per Match ────────────────────────────────────────
    avg_sorted = sorted(stats.values(), key=lambda s: s["avg_bankroll"], reverse=True)
    anames = [s["name"] for s in avg_sorted]
    acols  = [colors[names.index(s["name"])] for s in avg_sorted]
    avals  = [s["avg_bankroll"] for s in avg_sorted]
    ax_avg.bar(anames, avals, color=acols, edgecolor="#222244")
    ax_avg.axhline(0, color="white", linewidth=0.8, alpha=0.4)
    ax_avg.set_xticks(range(len(anames)))
    ax_avg.set_xticklabels(anames, rotation=30, ha="right", fontsize=7)
    style_ax(ax_avg, "Avg Bankroll per Matchup")
    ax_avg.set_ylabel("Chips")

    # ── 5. Leaderboard Table ─────────────────────────────────────────────────
    ax_table.axis("off")
    headers = ["#", "Bot", "W", "L", "Total BR", "Avg BR"]
    rows = []
    medals = {1: "(1st)", 2: "(2nd)", 3: "(3rd)"}
    for place, s in enumerate(ranked, 1):
        rows.append([
            f"{place} {medals.get(place, '')}",
            s["name"], s["wins"], s["losses"],
            f"{s['total_bankroll']:+,}",
            f"{s['avg_bankroll']:+,.0f}",
        ])
    tbl = ax_table.table(
        cellText=rows, colLabels=headers,
        loc="center", cellLoc="center"
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_facecolor("#12122A" if r == 0 else ("#1E1E35" if r % 2 == 0 else "#16162A"))
        cell.set_text_props(color="white" if r > 0 else "#A0A0FF", fontweight="bold" if r == 0 else "normal")
        cell.set_edgecolor("#333355")
    ax_table.set_title("Leaderboard", color="white", fontsize=11, fontweight="bold", pad=8)

    # ── Footer ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.01,
             f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ·  IIT Pokerbots 2026",
             ha="center", color="#555577", fontsize=8)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [CHART]  Visualisation saved -> {out_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def print_summary(data: dict):
    stats  = data["stats"]
    ranked = sorted(stats.values(), key=lambda s: s["total_bankroll"], reverse=True)
    rows   = [[
        s["name"], s["wins"], s["losses"],
        f"{s['total_bankroll']:+,}", f"{s['avg_bankroll']:+,.0f}"
    ] for s in ranked]
    print("\n" + "═"*60)
    print("  FINAL LEADERBOARD")
    print("═"*60)
    print(tabulate(rows, headers=["Bot", "W", "L", "Total Bankroll", "Avg/Match"],
                   tablefmt="fancy_grid", stralign="center", numalign="center"))


def main():
    parser = argparse.ArgumentParser(description="Run a round-robin Anaconda Pokerbots tournament.")
    parser.add_argument("--rounds",    type=int, default=1000, help="Rounds per matchup (default: 1000)")
    parser.add_argument("--small_log", action="store_true",    help="Use compressed engine logs")
    args = parser.parse_args()

    bots = discover_bots()
    if len(bots) < 2:
        print("❌  Need at least 2 bots in the bots/ folder.")
        sys.exit(1)

    print(f"\n  Discovered {len(bots)} bot(s): {', '.join(b['name'] for b in bots)}")

    data = run_tournament(bots, args.rounds, args.small_log)
    print_summary(data)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"tournament_{ts}.png"
    visualise(data, out_path)

    # Open the image automatically
    subprocess.run(["open", str(out_path)], check=False)


if __name__ == "__main__":
    main()
