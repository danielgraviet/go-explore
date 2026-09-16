"""Render workshop figures for docs/whitepaper/returning-to-development-states.md.

Numbers are frozen ledger values (S5, S21). Do not invent series.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs/whitepaper/figures"

WHITE = "#ffffff"

# Daytona brand colors (daytona.io) for matplotlib charts.
DAYTONA_BLUE = "#0880ff"
DAYTONA_GREEN = "#2dcb71"
CLEAN_GRAY = "#6b7280"
BUDGET_RED = "#9f1239"


def write(name: str, svg: str) -> None:
    path = OUT / name
    path.write_text(svg.strip() + "\n", encoding="utf-8")
    print(f"wrote {path}")


def _neurips_style() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "Times", "serif"],
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "legend.fontsize": 8.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 9,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "hatch.color": "black",
            "hatch.linewidth": 0.9,
        }
    )


def _style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)


def _save_mpl(fig, path: Path) -> None:
    import matplotlib.pyplot as plt

    fig.tight_layout(pad=0.35)
    fig.savefig(path, format="svg", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"wrote {path}")


SERIF = "Times New Roman, Times, Liberation Serif, serif"
RULE = "#222222"
FAINT = "#888888"
FOCUS = "#0072b2"


def _glyph_scratch(cx: float, cy: float) -> str:
    x, y = cx - 36, cy - 28
    return f"""
  <rect x="{x}" y="{y}" width="72" height="56" fill="none" stroke="{FAINT}" stroke-width="1.2" stroke-dasharray="4 3"/>
"""


def _glyph_patch(cx: float, cy: float) -> str:
    x, y = cx - 40, cy - 32
    return f"""
  <rect x="{x}" y="{y}" width="38" height="50" fill="{WHITE}" stroke="{RULE}" stroke-width="1.1"/>
  <line x1="{x + 8}" y1="{y + 12}" x2="{x + 30}" y2="{y + 12}" stroke="{RULE}" stroke-width="1"/>
  <line x1="{x + 8}" y1="{y + 20}" x2="{x + 26}" y2="{y + 20}" stroke="{RULE}" stroke-width="1"/>
  <line x1="{x + 8}" y1="{y + 28}" x2="{x + 30}" y2="{y + 28}" stroke="{RULE}" stroke-width="1"/>
  <rect x="{x + 46}" y="{y + 8}" width="36" height="36" fill="{WHITE}" stroke="{RULE}" stroke-width="1.1"/>
  <text x="{x + 64}" y="{y + 30}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{RULE}">±</text>
"""


def _glyph_files(cx: float, cy: float) -> str:
    return f"""
  <rect x="{cx - 28}" y="{cy - 8}" width="48" height="32" fill="{WHITE}" stroke="{RULE}" stroke-width="1.1"/>
  <rect x="{cx - 22}" y="{cy - 18}" width="48" height="32" fill="{WHITE}" stroke="{RULE}" stroke-width="1.1"/>
  <rect x="{cx - 16}" y="{cy - 28}" width="48" height="32" fill="{WHITE}" stroke="{RULE}" stroke-width="1.1"/>
  <line x1="{cx - 6}" y1="{cy - 14}" x2="{cx + 22}" y2="{cy - 14}" stroke="{RULE}" stroke-width="1"/>
  <line x1="{cx - 6}" y1="{cy - 6}" x2="{cx + 16}" y2="{cy - 6}" stroke="{RULE}" stroke-width="1"/>
"""


def _glyph_sandbox(cx: float, cy: float) -> str:
    x, y = cx - 46, cy - 36
    return f"""
  <rect x="{x}" y="{y}" width="92" height="72" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1.6"/>
  <rect x="{x + 10}" y="{y + 12}" width="28" height="20" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>
  <rect x="{x + 14}" y="{y + 8}" width="28" height="20" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>
  <ellipse cx="{x + 64}" cy="{y + 22}" rx="12" ry="6" fill="none" stroke="{FOCUS}" stroke-width="1.1"/>
  <rect x="{x + 52}" y="{y + 22}" width="24" height="14" fill="none" stroke="{FOCUS}" stroke-width="1.1"/>
  <ellipse cx="{x + 64}" cy="{y + 36}" rx="12" ry="6" fill="none" stroke="{FOCUS}" stroke-width="1.1"/>
  <circle cx="{x + 22}" cy="{y + 52}" r="5" fill="none" stroke="{FOCUS}" stroke-width="1.1"/>
  <circle cx="{x + 40}" cy="{y + 52}" r="5" fill="{FOCUS}" fill-opacity="0.15" stroke="{FOCUS}" stroke-width="1.1"/>
"""


def fig1_state() -> str:
    panels = [
        ("a", "Retry from scratch", "original repository", _glyph_scratch),
        ("b", "Text and git patch", "notes, source diffs", _glyph_patch),
        ("c", "Filesystem", "files on disk", _glyph_files),
        ("d", "Full sandbox snapshot", "live machine", _glyph_sandbox),
    ]
    left, top, width, height = 28, 18, 186, 168
    gap = 16
    parts = []
    for i, (letter, title, sub, glyph) in enumerate(panels):
        x = left + i * (width + gap)
        stroke = FOCUS if letter == "d" else RULE
        sw = 1.5 if letter == "d" else 1.0
        fill = "#f3f7fb" if letter == "d" else WHITE
        cx, cy = x + width / 2, top + 72
        parts.append(
            f'<rect x="{x}" y="{top}" width="{width}" height="{height}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )
        parts.append(glyph(cx, cy))
        parts.append(
            f'<text x="{x + 10}" y="{top + 18}" font-family="{SERIF}" font-size="13" font-style="italic" fill="{RULE}">({letter})</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{top + height + 22}" text-anchor="middle" font-family="{SERIF}" font-size="13" fill="{RULE}">{title}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{top + height + 40}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{FAINT}">{sub}</text>'
        )
    arrow_y = 246
    x0 = left
    x1 = left + 4 * width + 3 * gap
    return f"""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 268" role="img" aria-labelledby="t1 d1">
  <title id="t1">What the next attempt starts from</title>
  <desc id="d1">Four methods of carrying state between coding-agent attempts: retry from scratch, text and git patch, filesystem, and full sandbox snapshot.</desc>
  <rect width="840" height="268" fill="{WHITE}"/>
  <defs>
    <marker id="fig1arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="{RULE}"/>
    </marker>
  </defs>
  {"".join(parts)}
  <line x1="{x0}" y1="{arrow_y}" x2="{x1}" y2="{arrow_y}" stroke="{RULE}" stroke-width="1" marker-end="url(#fig1arrow)"/>
  <text x="{(x0 + x1) / 2}" y="{arrow_y + 16}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{FAINT}">more inherited state</text>
</svg>
"""


def _glyph_archive(cx: float, cy: float, *, highlight: tuple[int, int] | None, newborn: bool = False) -> str:
    cell_w, cell_h, gap = 22, 16, 5
    cols, rows = 3, 2
    total_w = cols * cell_w + (cols - 1) * gap
    total_h = rows * cell_h + (rows - 1) * gap
    x0 = cx - total_w / 2
    y0 = cy - total_h / 2
    parts = []
    for row in range(rows):
        for col in range(cols):
            x = x0 + col * (cell_w + gap)
            y = y0 + row * (cell_h + gap)
            is_hi = highlight == (col, row)
            is_new = newborn and col == 2 and row == 1
            stroke = FOCUS if is_hi or is_new else RULE
            fill = "#d6e8f5" if is_hi else ("#f3f7fb" if is_new else WHITE)
            sw = 1.4 if is_hi or is_new else 1.0
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w}" height="{cell_h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            )
            if is_new:
                parts.append(
                    f'<text x="{x + cell_w / 2:.1f}" y="{y + 12:.1f}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{FOCUS}">+</text>'
                )
    return "\n".join(parts)


def _glyph_restore(cx: float, cy: float) -> str:
    x, y = cx - 38, cy - 28
    return f"""
  <rect x="{x}" y="{y}" width="76" height="56" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1.5"/>
  <rect x="{x + 8}" y="{y + 10}" width="22" height="14" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>
  <rect x="{x + 12}" y="{y + 6}" width="22" height="14" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>
  <ellipse cx="{x + 54}" cy="{y + 16}" rx="10" ry="5" fill="none" stroke="{FOCUS}" stroke-width="1"/>
  <rect x="{x + 44}" y="{y + 16}" width="20" height="10" fill="none" stroke="{FOCUS}" stroke-width="1"/>
  <ellipse cx="{x + 54}" cy="{y + 26}" rx="10" ry="5" fill="none" stroke="{FOCUS}" stroke-width="1"/>
  <circle cx="{x + 18}" cy="{y + 42}" r="4" fill="{FOCUS}" fill-opacity="0.15" stroke="{FOCUS}" stroke-width="1"/>
"""


def _glyph_explore(cx: float, cy: float) -> str:
    x, y = cx - 40, cy - 22
    return f"""
  <rect x="{x}" y="{y}" width="36" height="28" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1.3"/>
  <circle cx="{x + 18}" cy="{y + 14}" r="3" fill="{FOCUS}"/>
  <path d="M {x + 40} {y + 14} C {x + 52} {y + 14}, {x + 58} {y - 6}, {x + 72} {y - 8}" fill="none" stroke="{RULE}" stroke-width="1.2"/>
  <circle cx="{x + 50}" cy="{y + 10}" r="2.4" fill="{RULE}"/>
  <circle cx="{x + 62}" cy="{y + 0}" r="2.4" fill="{RULE}"/>
  <circle cx="{x + 74}" cy="{y - 8}" r="2.4" fill="{FOCUS}"/>
"""


def fig2_pipeline() -> str:
    box_w, box_h = 250, 118
    ax, ay = 90, 20
    bx, by = 500, 20
    cx, cy = 500, 168
    dx, dy = 90, 168
    boxes = [
        (ax, ay, "a", "Select", "from archive", _glyph_archive(ax + box_w / 2, ay + 58, highlight=(1, 0))),
        (bx, by, "b", "Go to state", "restore snapshot", _glyph_restore(bx + box_w / 2, by + 58)),
        (cx, cy, "c", "Explore", "from state", _glyph_explore(cx + box_w / 2, cy + 58)),
        (dx, dy, "d", "Update archive", "new snapshots", _glyph_archive(dx + box_w / 2, dy + 58, highlight=None, newborn=True)),
    ]
    parts = []
    for x, y, letter, title, sub, glyph in boxes:
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" fill="{WHITE}" stroke="{RULE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + 10}" y="{y + 18}" font-family="{SERIF}" font-size="13" font-style="italic" fill="{RULE}">({letter})</text>'
        )
        parts.append(glyph)
        parts.append(
            f'<text x="{x + box_w / 2}" y="{y + box_h - 18}" text-anchor="middle" font-family="{SERIF}" font-size="13" fill="{RULE}">{title}</text>'
        )
        parts.append(
            f'<text x="{x + box_w / 2}" y="{y + box_h - 4}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{FAINT}">{sub}</text>'
        )

    def arrow(x1: float, y1: float, x2: float, y2: float) -> str:
        return (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{RULE}" '
            f'stroke-width="1.2" marker-end="url(#fig2arrow)"/>'
        )

    arrows = [
        arrow(ax + box_w, ay + box_h / 2, bx, by + box_h / 2),
        arrow(bx + box_w / 2, by + box_h, cx + box_w / 2, cy),
        arrow(cx, cy + box_h / 2, dx + box_w, dy + box_h / 2),
        arrow(dx + box_w / 2, dy, ax + box_w / 2, ay + box_h),
    ]
    return f"""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 308" role="img" aria-labelledby="t2 d2">
  <title id="t2">Go-Explore over sandbox snapshots</title>
  <desc id="d2">Select a snapshot from the archive, restore it, explore from that machine, and write new snapshots back to the archive.</desc>
  <rect width="840" height="308" fill="{WHITE}"/>
  <defs>
    <marker id="fig2arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="{RULE}"/>
    </marker>
  </defs>
  {"".join(parts)}
  {"".join(arrows)}
</svg>
"""


def fig3_headline(path: Path) -> None:
    """NeurIPS-style grouped bar chart via matplotlib (ledger S5)."""
    import matplotlib.pyplot as plt
    import numpy as np

    # Frozen headline counts (S5). Do not revise.
    tasks = [
        "git-multibranch",
        "extract-elf",
        "heap-crash",
        "code-from-image",
        "text-editing",
    ]
    retry = np.array([5, 4, 3, 3, 2])
    branch = np.array([1, 3, 1, 1, 0])

    _neurips_style()
    fig, ax = plt.subplots(figsize=(6.75, 2.85), dpi=150)
    x = np.arange(len(tasks))
    width = 0.36

    bars_retry = ax.bar(
        x - width / 2,
        retry,
        width,
        label="Independent retry (17/25)",
        color=DAYTONA_BLUE,
        edgecolor="black",
        linewidth=0.6,
        zorder=3,
    )
    bars_branch = ax.bar(
        x + width / 2,
        branch,
        width,
        label="Snapshot branching (6/25)",
        color=DAYTONA_GREEN,
        edgecolor="black",
        linewidth=0.6,
        hatch="///",
        zorder=3,
    )

    ax.set_ylabel("Seeds solved (out of 5)")
    ax.set_xticks(x)
    ax.set_xticklabels(tasks, rotation=15, ha="right")
    ax.set_yticks(range(6))
    ax.set_ylim(0, 5.55)
    ax.set_xlim(-0.55, len(tasks) - 0.45)
    _style_axes(ax)
    ax.yaxis.grid(True, linestyle=":", linewidth=0.6, color="#bbbbbb", zorder=0)
    ax.legend(
        frameon=False,
        loc="upper right",
        handlelength=1.4,
        handletextpad=0.5,
        borderaxespad=0.2,
    )

    for bars in (bars_retry, bars_branch):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{int(h)}/5",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#222222",
            )

    _save_mpl(fig, path)


def fig4_warehouse(path: Path) -> None:
    """NeurIPS-style bar chart for warehouse representation ablation (S21)."""
    import matplotlib.pyplot as plt
    import numpy as np

    # Frozen S21 totals. Do not revise.
    labels = ["Clean start", "Git diff only", "Full snapshot"]
    solved = np.array([0, 0, 4])
    colors = [CLEAN_GRAY, DAYTONA_BLUE, DAYTONA_GREEN]
    hatches = ["", "", "///"]

    _neurips_style()
    fig, ax = plt.subplots(figsize=(5.4, 2.9), dpi=150)
    x = np.arange(len(labels))
    bars = ax.bar(
        x,
        solved,
        width=0.62,
        color=colors,
        edgecolor="black",
        linewidth=0.6,
        zorder=3,
    )
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)

    ax.set_ylabel("Seeds solved (out of 5)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_yticks(range(6))
    ax.set_ylim(0, 5.55)
    ax.set_xlim(-0.55, len(labels) - 0.45)
    _style_axes(ax)
    ax.yaxis.grid(True, linestyle=":", linewidth=0.6, color="#bbbbbb", zorder=0)

    for bar, n in zip(bars, solved):
        ax.annotate(
            f"{int(n)}/5",
            xy=(bar.get_x() + bar.get_width() / 2, n),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#222222",
        )

    _save_mpl(fig, path)


def fig5_tokens(path: Path) -> None:
    """NeurIPS-style token scatter for warehouse arms (S21)."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    # (seed, arm, tokens, outcome) — frozen S21. Do not revise.
    rows = [
        (0, "clean", 74033, "failed"),
        (0, "diff", 163850, "failed"),
        (0, "snapshot", 22724, "solved"),
        (1, "clean", 101982, "failed"),
        (1, "diff", 35664, "failed"),
        (1, "snapshot", 32651, "failed"),
        (2, "clean", 25634, "failed"),
        (2, "diff", 173179, "failed"),
        (2, "snapshot", 41416, "solved"),
        (3, "clean", 49345, "failed"),
        (3, "diff", 215966, "budget"),
        (3, "snapshot", 33526, "solved"),
        (4, "clean", 35566, "failed"),
        (4, "diff", 48961, "failed"),
        (4, "snapshot", 21348, "solved"),
    ]
    arm_color = {
        "clean": CLEAN_GRAY,
        "diff": DAYTONA_BLUE,
        "snapshot": DAYTONA_GREEN,
    }
    arm_offset = {"clean": 0.18, "diff": 0.0, "snapshot": -0.18}
    budget_cap = 200_000

    _neurips_style()
    fig, ax = plt.subplots(figsize=(6.75, 3.1), dpi=150)

    for seed, arm, tokens, outcome in rows:
        y = seed + arm_offset[arm]
        color = arm_color[arm]
        if outcome == "solved":
            ax.scatter(
                tokens,
                y,
                s=55,
                marker="o",
                facecolors=color,
                edgecolors="black",
                linewidths=0.7,
                zorder=3,
            )
        elif outcome == "budget":
            ax.scatter(
                tokens,
                y,
                s=55,
                marker="s",
                facecolors="white",
                edgecolors=BUDGET_RED,
                linewidths=1.4,
                zorder=3,
            )
        else:
            ax.scatter(
                tokens,
                y,
                s=55,
                marker="o",
                facecolors="white",
                edgecolors=color,
                linewidths=1.3,
                zorder=3,
            )

    ax.axvline(
        budget_cap,
        color="#888888",
        linestyle="--",
        linewidth=0.9,
        zorder=1,
    )
    ax.text(
        budget_cap + 3500,
        2.0,
        "200k cap",
        ha="left",
        va="center",
        fontsize=7.5,
        color="#555555",
        rotation=90,
    )

    ax.set_xlabel("Tokens used")
    ax.set_ylabel("Seed")
    ax.set_yticks(range(5))
    ax.set_yticklabels([f"{i}" for i in range(5)])
    ax.set_ylim(-0.45, 4.7)
    ax.set_xlim(0, 230_000)
    ax.set_xticks([0, 50_000, 100_000, 150_000, 200_000])
    ax.set_xticklabels(["0", "50k", "100k", "150k", "200k"])
    _style_axes(ax)
    ax.xaxis.grid(True, linestyle=":", linewidth=0.6, color="#bbbbbb", zorder=0)

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=CLEAN_GRAY,
            markeredgecolor="black",
            markersize=7,
            label="Clean",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=DAYTONA_BLUE,
            markeredgecolor="black",
            markersize=7,
            label="Git diff",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=DAYTONA_GREEN,
            markeredgecolor="black",
            markersize=7,
            label="Snapshot",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="white",
            markeredgecolor="#444444",
            markersize=7,
            markeredgewidth=1.3,
            label="Failed",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor="white",
            markeredgecolor=BUDGET_RED,
            markersize=7,
            markeredgewidth=1.3,
            label="Budget exhausted",
        ),
    ]
    ax.legend(
        handles=legend_handles,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.18),
        ncol=len(legend_handles),
        handletextpad=0.3,
        columnspacing=1.0,
        borderaxespad=0.0,
    )

    fig.subplots_adjust(top=0.82)
    fig.savefig(path, format="svg", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"wrote {path}")

def _glyph_budget(cx: float, cy: float) -> str:
    y = cy - 18
    # retry: three equal slices
    x0 = cx - 52
    parts = [
        f'<rect x="{x0}" y="{y}" width="20" height="36" fill="{WHITE}" stroke="{RULE}" stroke-width="1"/>',
        f'<rect x="{x0 + 22}" y="{y}" width="20" height="36" fill="{WHITE}" stroke="{RULE}" stroke-width="1"/>',
        f'<rect x="{x0 + 44}" y="{y}" width="20" height="36" fill="{WHITE}" stroke="{RULE}" stroke-width="1"/>',
        f'<rect x="{x0 + 78}" y="{y + 10}" width="12" height="26" fill="#d6e8f5" stroke="{FOCUS}" stroke-width="1.2"/>',
        f'<rect x="{x0 + 92}" y="{y + 18}" width="12" height="18" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>',
        f'<rect x="{x0 + 106}" y="{y + 18}" width="12" height="18" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>',
    ]
    return "\n".join(parts)


def _glyph_sticky(cx: float, cy: float) -> str:
    x, y = cx - 18, cy - 28
    return f"""
  <rect x="{x}" y="{y}" width="36" height="48" fill="{WHITE}" stroke="{RULE}" stroke-width="1.1"/>
  <line x1="{x + 8}" y1="{y + 12}" x2="{x + 28}" y2="{y + 12}" stroke="{RULE}" stroke-width="1"/>
  <line x1="{x + 8}" y1="{y + 20}" x2="{x + 24}" y2="{y + 20}" stroke="{RULE}" stroke-width="1"/>
  <line x1="{x + 10}" y1="{y + 30}" x2="{x + 26}" y2="{y + 42}" stroke="{FOCUS}" stroke-width="1.4"/>
  <line x1="{x + 26}" y1="{y + 30}" x2="{x + 10}" y2="{y + 42}" stroke="{FOCUS}" stroke-width="1.4"/>
  <path d="M {x + 40} {y + 16} C {x + 58} {y + 8}, {x + 58} {y + 48}, {x + 22} {y + 50}" fill="none" stroke="{RULE}" stroke-width="1.1" marker-end="url(#fig6arrow)"/>
"""


def _glyph_handoff(cx: float, cy: float) -> str:
    x = cx - 52
    y = cy - 28
    return f"""
  <rect x="{x}" y="{y}" width="52" height="44" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1.4"/>
  <rect x="{x + 8}" y="{y + 8}" width="16" height="12" fill="{WHITE}" stroke="{FOCUS}" stroke-width="1"/>
  <ellipse cx="{x + 38}" cy="{y + 14}" rx="8" ry="4" fill="none" stroke="{FOCUS}" stroke-width="1"/>
  <rect x="{x + 30}" y="{y + 14}" width="16" height="8" fill="none" stroke="{FOCUS}" stroke-width="1"/>
  <ellipse cx="{x + 38}" cy="{y + 22}" rx="8" ry="4" fill="none" stroke="{FOCUS}" stroke-width="1"/>
  <circle cx="{x + 78}" cy="{y + 22}" r="16" fill="none" stroke="{FAINT}" stroke-width="1.2" stroke-dasharray="3 2"/>
"""


def _glyph_weak_select(cx: float, cy: float) -> str:
    return _glyph_archive(cx, cy, highlight=(2, 0), newborn=False) + f"""
  <text x="{cx + 28}" y="{cy - 14}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{FOCUS}">✓</text>
"""


def fig6_failures() -> str:
    panels = [
        ("a", "Budget split", "root vs children", _glyph_budget),
        ("b", "Sticky wrong state", "faithful mistakes", _glyph_sticky),
        ("c", "Handoff cost", "machine, not memory", _glyph_handoff),
        ("d", "Weak selection", "busy ≠ solved", _glyph_weak_select),
    ]
    left, top, width, height = 28, 18, 186, 168
    gap = 16
    parts = []
    for i, (letter, title, sub, glyph) in enumerate(panels):
        x = left + i * (width + gap)
        cx, cy = x + width / 2, top + 72
        parts.append(
            f'<rect x="{x}" y="{top}" width="{width}" height="{height}" fill="{WHITE}" stroke="{RULE}" stroke-width="1"/>'
        )
        parts.append(glyph(cx, cy))
        parts.append(
            f'<text x="{x + 10}" y="{top + 18}" font-family="{SERIF}" font-size="13" font-style="italic" fill="{RULE}">({letter})</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{top + height + 22}" text-anchor="middle" font-family="{SERIF}" font-size="13" fill="{RULE}">{title}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{top + height + 40}" text-anchor="middle" font-family="{SERIF}" font-size="11" fill="{FAINT}">{sub}</text>'
        )
    return f"""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 248" role="img" aria-labelledby="t6 d6">
  <title id="t6">Four failure modes of snapshot search</title>
  <desc id="d6">Budget split, sticky wrong state, handoff cost, and weak selection.</desc>
  <rect width="840" height="248" fill="{WHITE}"/>
  <defs>
    <marker id="fig6arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="{RULE}"/>
    </marker>
  </defs>
  {"".join(parts)}
</svg>
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("fig1-what-is-preserved.svg", fig1_state())
    write("fig2-search-pipeline.svg", fig2_pipeline())
    fig3_headline(OUT / "fig3-headline-solve-rates.svg")
    fig4_warehouse(OUT / "fig4-warehouse-arms.svg")
    fig5_tokens(OUT / "fig5-warehouse-tokens.svg")
    write("fig6-failure-modes.svg", fig6_failures())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
