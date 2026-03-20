# ─────────────────────────────────────────────
# analytics.py  —  v1.2 Budget Analytics Module
# ─────────────────────────────────────────────
import os
from datetime import datetime

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

DOWNLOADS      = os.path.join(os.path.expanduser("~"), "Downloads")
SUMMARY_PATH   = os.path.join(DOWNLOADS, "summary_report.csv")
CHART_PATH     = os.path.join(DOWNLOADS, "spending_trends.png")
BANK_CHART_PATH = os.path.join(DOWNLOADS, "spending_by_bank.png")
SUMMARY_TXT    = os.path.join(DOWNLOADS, "spending_summary.txt")

# ── Row 1 featured panels (adjust names to match your actual categories) ──
# Matched case-insensitively; first match wins.
_FEATURED_CATEGORIES = ["Credit Card Payments", "Deposits", "Paychecks/Salary"]

# Categories to exclude from the pivot entirely (non-expense pass-throughs)
_EXCLUDE_CATEGORIES: set[str] = set()   # nothing excluded — featured panels show them all

# Palette
_PALETTE = [
    "#4FC3F7", "#81C784", "#FFB74D", "#F06292", "#CE93D8",
    "#80DEEA", "#FFCC02", "#FF7043", "#A5D6A7", "#90CAF9",
    "#BCAAA4", "#B0BEC5", "#EF9A9A", "#80CBC4", "#FFF176",
]

_BG      = "#0D1117"
_PANEL   = "#111820"
_GRID    = "#1A2230"
_TEXT    = "#E2E8F0"
_SUBTEXT = "#718096"


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _spending_pivot(df: pd.DataFrame, exclude: set[str] | None = None) -> pd.DataFrame:
    """pivot: index=category, columns=Period(month), values=sum(amount)."""
    work = df.copy()
    work["date"]  = pd.to_datetime(work["date"], format="mixed")
    work["month"] = work["date"].dt.to_period("M")
    work = work[work["amount"] > 0]
    if exclude:
        work = work[~work["category"].isin(exclude)]
    pivot = (
        work.groupby(["category", "month"])["amount"]
        .sum()
        .unstack(fill_value=0)
    )
    return pivot.sort_index()


def _fmt_dollar(v: float) -> str:
    return f"${v:,.0f}"


def _resolve_featured(all_categories: list[str]) -> list[str | None]:
    """
    Match _FEATURED_CATEGORIES against the actual category list
    (case-insensitive). Returns a list of 3 resolved names or None if missing.
    """
    lower_map = {c.lower(): c for c in all_categories}
    resolved = []
    for wanted in _FEATURED_CATEGORIES:
        resolved.append(lower_map.get(wanted.lower()))
    return resolved


def _draw_single_panel(ax, x, values, colour, cat, months):
    """Shared renderer for one featured subplot."""
    ax.set_facecolor(_PANEL)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID)
        spine.set_linewidth(0.6)

    ax.yaxis.grid(True, color=_GRID, linewidth=0.7, linestyle="--")
    ax.set_axisbelow(True)

    ax.fill_between(x, values, alpha=0.20, color=colour, zorder=2)
    ax.plot(
        x, values,
        color=colour, linewidth=2.2,
        marker="o", markersize=5.5,
        markerfacecolor=colour, markeredgecolor=_PANEL,
        markeredgewidth=1.4,
        zorder=3,
    )

    for xi, v in zip(x, values):
        if v > 0:
            ax.annotate(
                _fmt_dollar(v),
                xy=(xi, v), xytext=(0, 7),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=6.8, color=colour, fontweight="bold",
            )

    total = values.sum()
    ax.set_title(cat, fontsize=10, fontweight="bold", color=colour, pad=5)
    ax.text(
        0.98, 0.96, f"Total {_fmt_dollar(total)}",
        transform=ax.transAxes,
        ha="right", va="top", fontsize=7.5, color=_SUBTEXT,
    )

    short = [m[-5:] for m in months]   # "YYYY-MM" → keep as-is (already short)
    ax.set_xticks(x)
    ax.set_xticklabels(short, rotation=35, ha="right", fontsize=7, color=_SUBTEXT)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_dollar(v)))
    ax.tick_params(axis="y", labelsize=7, colors=_SUBTEXT, length=0)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(bottom=0)


# ─────────────────────────────────────────────
# 1. SUMMARY REPORT CSV
# ─────────────────────────────────────────────

def build_summary_report(df: pd.DataFrame) -> pd.DataFrame:
    pivot = _spending_pivot(df)
    pivot.columns = [str(p) for p in pivot.columns]
    pivot["Grand Total"] = pivot.sum(axis=1)
    totals = pivot.sum(axis=0).rename("GRAND TOTAL")
    pivot  = pd.concat([pivot, totals.to_frame().T])
    pivot.index.name = "category"
    pivot.to_csv(SUMMARY_PATH)
    print(f"📊  Summary report → {SUMMARY_PATH}")
    return pivot


# ─────────────────────────────────────────────
# 2. TWO-ROW SUBPLOT CHART
#    Row 1: 3 featured panels  (Payment ,Deposits, Paychecks)
#    Row 2: master multi-line chart for all remaining categories
# ─────────────────────────────────────────────

def build_spending_chart(df: pd.DataFrame) -> None:
    pivot = _spending_pivot(df)
    if pivot.empty:
        print("[ANALYTICS] No spending data to chart.")
        return

    months     = [str(p) for p in pivot.columns]
    x          = np.arange(len(months))
    all_cats   = pivot.index.tolist()

    featured   = _resolve_featured(all_cats)        # list of 3 (name or None)
    rest_cats  = all_cats                           # master chart shows everything

    # Date range for title
    dates     = pd.to_datetime(df["date"], format="mixed")
    date_from = dates.min().strftime("%b %Y")
    date_to   = dates.max().strftime("%b %Y")
    date_range = f"{date_from} – {date_to}" if date_from != date_to else date_from

    # ── Figure + GridSpec ─────────────────────
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(18, 10))
    fig.patch.set_facecolor(_BG)

    gs = gridspec.GridSpec(
        2, 3,
        figure=fig,
        hspace=0.52,
        wspace=0.28,
        height_ratios=[1, 1.1],
    )

    fig.suptitle(
        f"Month-over-Month Spending by Category  ·  {date_range}",
        fontsize=17, fontweight="bold", color=_TEXT, y=1.02,
    )

    # ── Row 1: featured panels ─────────────────
    for col_idx, cat in enumerate(featured):
        ax = fig.add_subplot(gs[0, col_idx])
        if cat is None:
            ax.set_facecolor(_PANEL)
            ax.text(
                0.5, 0.5, "No data",
                ha="center", va="center",
                color=_SUBTEXT, fontsize=10,
                transform=ax.transAxes,
            )
            ax.set_title(
                _FEATURED_CATEGORIES[col_idx],
                fontsize=10, fontweight="bold", color=_SUBTEXT, pad=5,
            )
            for spine in ax.spines.values():
                spine.set_edgecolor(_GRID)
            ax.set_xticks([])
            ax.set_yticks([])
            continue

        colour = _PALETTE[col_idx % len(_PALETTE)]
        values = pivot.loc[cat].values.astype(float)
        _draw_single_panel(ax, x, values, colour, cat, months)

    # ── Row 2: master chart (remaining categories) ─
    ax_master = fig.add_subplot(gs[1, :])   # span all 3 columns
    ax_master.set_facecolor(_PANEL)
    for spine in ax_master.spines.values():
        spine.set_edgecolor(_GRID)
        spine.set_linewidth(0.6)
    ax_master.yaxis.grid(True, color=_GRID, linewidth=0.7, linestyle="--")
    ax_master.set_axisbelow(True)

    if rest_cats:
        for j, cat in enumerate(rest_cats):
            colour = _PALETTE[(len(featured) + j) % len(_PALETTE)]
            values = pivot.loc[cat].values.astype(float)

            ax_master.fill_between(x, values, alpha=0.07, color=colour, zorder=2)
            ax_master.plot(
                x, values,
                color=colour, linewidth=2.0,
                marker="o", markersize=5,
                markerfacecolor=colour, markeredgecolor=_PANEL,
                markeredgewidth=1.3,
                label=cat, zorder=3,
            )

            # Label last point only to keep it clean
            last_v = values[-1]
            if last_v > 0:
                ax_master.annotate(
                    _fmt_dollar(last_v),
                    xy=(x[-1], last_v), xytext=(6, 0),
                    textcoords="offset points",
                    ha="left", va="center",
                    fontsize=7.2, color=colour, fontweight="bold",
                )

        ax_master.legend(
            loc="upper left",
            fontsize=8,
            framealpha=0.15,
            edgecolor="#2D3748",
            facecolor="#1A202C",
            labelcolor=_TEXT,
            ncol=max(1, len(rest_cats) // 5 + 1),
            handlelength=1.5,
        )
    else:
        ax_master.text(
            0.5, 0.5, "All categories shown above",
            ha="center", va="center",
            color=_SUBTEXT, fontsize=11,
            transform=ax_master.transAxes,
        )

    ax_master.set_title("All Other Categories", fontsize=11, fontweight="bold", color=_TEXT, pad=6)
    ax_master.set_xticks(x)
    ax_master.set_xticklabels(months, rotation=30, ha="right", fontsize=8, color=_SUBTEXT)
    ax_master.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_dollar(v)))
    ax_master.tick_params(axis="y", labelsize=8, colors=_SUBTEXT, length=0)
    ax_master.tick_params(axis="x", length=0)
    ax_master.set_ylim(bottom=0)

    # ── Watermark ──────────────────────────────
    fig.text(
        0.99, -0.01, "BudgetAggregator v1.2",
        ha="right", va="bottom",
        fontsize=7, color="#2D3748",
    )

    fig.savefig(CHART_PATH, dpi=160, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    print(f"📈  Spending chart  → {CHART_PATH}")


# ─────────────────────────────────────────────
# 3. TEXT SUMMARY
# ─────────────────────────────────────────────

def build_text_summary(df: pd.DataFrame) -> None:
    pivot  = _spending_pivot(df)
    months = [str(p) for p in pivot.columns]

    if pivot.empty or len(months) == 0:
        return

    totals_by_cat   = pivot.sum(axis=1).sort_values(ascending=False)
    totals_by_month = pivot.sum(axis=0)
    grand_total     = totals_by_cat.sum()

    top_month       = str(totals_by_month.idxmax())
    top_month_total = totals_by_month.max()

    # Month-over-month swings for last two months
    mom_lines = []
    if len(months) >= 2:
        prev_m, last_m = months[-2], months[-1]
        for cat in pivot.index:
            prev_v = pivot.loc[cat, prev_m]
            last_v = pivot.loc[cat, last_m]
            if prev_v > 0:
                pct = (last_v - prev_v) / prev_v * 100
                mom_lines.append((cat, prev_v, last_v, pct))
        mom_lines.sort(key=lambda r: abs(r[3]), reverse=True)

    total_rows = len(df)
    uncat_rows = (df["category"] == "Uncategorized").sum() if "category" in df.columns else 0
    uncat_pct  = uncat_rows / total_rows * 100 if total_rows else 0

    lines = [
        "=" * 52,
        "  BUDGET SUMMARY  —  BudgetAggregator v1.2",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 52,
        "",
        f"  Grand Total Spending : {_fmt_dollar(grand_total)}",
        f"  Months Covered       : {len(months)}  ({months[0]} → {months[-1]})",
        f"  Transactions         : {total_rows:,}",
        f"  Uncategorized        : {uncat_rows:,}  ({uncat_pct:.1f}%)",
        "",
        "── TOP CATEGORIES ──────────────────────────",
    ]

    for rank, (cat, amt) in enumerate(totals_by_cat.items(), 1):
        pct = amt / grand_total * 100
        bar = "█" * int(pct / 2)
        lines.append(f"  {rank:>2}. {cat:<18} {_fmt_dollar(amt):>10}  {pct:5.1f}%  {bar}")

    lines += [
        "",
        "── BUSIEST MONTH ───────────────────────────",
        f"  {top_month}  →  {_fmt_dollar(top_month_total)}",
        "",
        "── MONTH-OVER-MONTH  ({prev_m} → {last_m}) ──".format(
            prev_m=months[-2] if len(months) >= 2 else "N/A",
            last_m=months[-1],
        ),
    ]

    if mom_lines:
        for cat, prev_v, last_v, pct in mom_lines[:6]:
            arrow = "▲" if pct >= 0 else "▼"
            lines.append(
                f"  {cat:<18}  {_fmt_dollar(prev_v):>9} → {_fmt_dollar(last_v):>9}  "
                f"{arrow} {abs(pct):.1f}%"
            )
    else:
        lines.append("  (only one month of data)")

    lines += ["", "=" * 52, ""]

    text = "\n".join(lines)
    with open(SUMMARY_TXT, "w") as f:
        f.write(text)

    print(f"📝  Text summary    → {SUMMARY_TXT}")
    print()
    print(text)


# ─────────────────────────────────────────────
# 4. BANK SPENDING CHART  (stock-style, green/red segments)
# ─────────────────────────────────────────────

def build_bank_chart(df: pd.DataFrame) -> None:
    work = df.copy()
    work["date"]  = pd.to_datetime(work["date"], format="mixed")
    work["month"] = work["date"].dt.to_period("M")
    work = work[work["amount"] > 0]

    if "source_bank" not in work.columns or work.empty:
        print("[ANALYTICS] No bank data for bank chart.")
        return

    # Total spending per bank per month
    bank_pivot = (
        work.groupby(["source_bank", "month"])["amount"]
        .sum()
        .unstack(fill_value=0)
    )

    banks  = bank_pivot.index.tolist()
    months = [str(p) for p in bank_pivot.columns]
    x      = np.arange(len(months))

    dates     = work["date"]
    date_from = dates.min().strftime("%b %Y")
    date_to   = dates.max().strftime("%b %Y")
    date_range = f"{date_from} – {date_to}" if date_from != date_to else date_from

    # Base colours per bank (neutral — segments will be green/red)
    _BANK_BASE = ["#90CAF9", "#FFB74D", "#CE93D8", "#80DEEA"]

    _UP   = "#00E676"   # green  — spending went up   (more outflow)
    _DOWN = "#FF1744"   # red    — spending went down  (less outflow)
    _FLAT = "#718096"

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_PANEL)

    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID)
        spine.set_linewidth(0.6)

    ax.yaxis.grid(True, color=_GRID, linewidth=0.7, linestyle="--")
    ax.set_axisbelow(True)

    for bi, bank in enumerate(banks):
        values     = bank_pivot.loc[bank].values.astype(float)
        base_color = _BANK_BASE[bi % len(_BANK_BASE)]

        # Draw segment-by-segment with green/red colouring
        for i in range(len(x) - 1):
            v0, v1 = values[i], values[i + 1]
            seg_color = _UP if v1 > v0 else (_DOWN if v1 < v0 else _FLAT)
            ax.plot(
                [x[i], x[i + 1]], [v0, v1],
                color=seg_color, linewidth=2.6, zorder=3, solid_capstyle="round",
            )
            # Glow pass
            ax.plot(
                [x[i], x[i + 1]], [v0, v1],
                color=seg_color, linewidth=7, alpha=0.12, zorder=2,
            )

        # Markers coloured by direction vs previous point
        for i, v in enumerate(values):
            if i == 0:
                dot_color = base_color
            else:
                dot_color = _UP if v > values[i - 1] else (_DOWN if v < values[i - 1] else _FLAT)
            ax.scatter(x[i], v, color=dot_color, s=55, zorder=4,
                       edgecolors=_PANEL, linewidths=1.5)

        # Value label above each point
        for i, v in enumerate(values):
            if v > 0:
                ax.annotate(
                    _fmt_dollar(v),
                    xy=(x[i], v), xytext=(0, 9),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=7.2, color=base_color, fontweight="bold",
                )

        # Legend proxy line — single "Combined" entry for all banks
        grand = bank_pivot.values.sum()
        lbl   = f"Combined  (total {_fmt_dollar(grand)})" if bi == 0 else "_nolegend_"
        ax.plot([], [], color=base_color, linewidth=2.6, label=lbl)

    # ── Legend for up/down ──────────────────────
    ax.plot([], [], color=_UP,   linewidth=2.5, label="▲ Spending up")
    ax.plot([], [], color=_DOWN, linewidth=2.5, label="▼ Spending down")

    ax.legend(
        loc="upper left",
        fontsize=8.5,
        framealpha=0.15,
        edgecolor="#2D3748",
        facecolor="#1A202C",
        labelcolor=_TEXT,
        handlelength=1.5,
    )

    ax.set_title(
        f"Monthly Spending by Bank  ·  {date_range}",
        fontsize=14, fontweight="bold", color=_TEXT, pad=10,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=30, ha="right", fontsize=8.5, color=_SUBTEXT)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_dollar(v)))
    ax.tick_params(axis="y", labelsize=8.5, colors=_SUBTEXT, length=0)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(bottom=0)

    fig.text(
        0.99, -0.02, "BudgetAggregator v1.2",
        ha="right", va="bottom", fontsize=7, color="#2D3748",
    )

    plt.tight_layout()
    fig.savefig(BANK_CHART_PATH, dpi=160, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    print(f"🏦  Bank chart      → {BANK_CHART_PATH}")


# ─────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def run_analytics(df: pd.DataFrame) -> None:
    """
    Called automatically at the end of budget_engine.run_pipeline().
    Can also be used standalone:

        import pandas as pd
        from analytics import run_analytics
        run_analytics(pd.read_csv("~/Downloads/budget_master.csv"))
    """
    print("\n[ANALYTICS] Running v1.2 analytics...")
    build_summary_report(df)
    build_text_summary(df)
    build_spending_chart(df)
    build_bank_chart(df)
    print("[ANALYTICS] Done.\n")
