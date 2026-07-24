"""
Builds a formatted Excel cheat sheet from the rankings table: one "Overall" tab (all
players, sorted by overall value-over-replacement rank) plus one tab per position
(QB/RB/WR/TE/K) for the drill-down view, in that fixed order.

Design history:
- v1 used a full-width merged row between groups ("TIER 5", "PICKS 11-20") to match a
  reference screenshot. Broke in practice -- Excel refuses to sort/filter a range with
  merged cells of inconsistent size. Replaced with a plain "Tier" data column instead.
- v2 used STATIC alternating row fills (baked in at generation time, based on tier
  group order). Looked fine in the default sort order, but once sorted by a different
  column in Excel, the banding pattern didn't reflow with it -- Excel moves a row's
  formatting along with its data on a sort, so the zebra stripe ended up looking
  scrambled relative to the new row order, since it was never tied to actual row
  position in the first place. Replaced with Excel CONDITIONAL FORMATTING
  (`=MOD(ROW(),2)=0`), which recalculates from actual row position on every sort/filter,
  so the stripe always reflows correctly no matter how the sheet gets reordered.
- Rookie highlighting (gold) is also conditional formatting, not a static fill, and
  takes priority over the zebra rule (stopIfTrue) so a rookie row doesn't get
  overwritten by the stripe -- both rules read off the "Rookie" column's actual value,
  so this also survives any sort/filter correctly.
- v3 dropped the separate "Pos" column -- genuinely redundant with "Pos Rank" (which
  already starts with the position, e.g. "RB5") and, on the Overall tab, with the
  color-coding too. One column, three signals, was too much repetition.

Styling notes:
- Pos Rank is color-coded per position, Overall tab only (position tabs are already
  single-position). This coloring IS static (not conditional) since it depends on the
  row's own position value, not on row position in the sheet -- correctly travels with
  the row on a native Excel sort either way. The zebra/rookie conditional formatting
  range deliberately skips this column so the position color always shows through.
- Player name bold; Score/Floor/Ceiling always show one decimal via a number format.
- Columns are a bit wider than the data strictly needs, since the AutoFilter dropdown
  arrow eats into the header cell's visible width and was truncating headers otherwise.

Raw 2025 season stats come from the `season_stats` VIEW, derived live from weekly_stats
-- no new ingestion needed. Rush+Rec Yds is computed here (rushing + receiving yards),
not a stored column.

Note on "highlight the column I'm sorting by": clicking a column's letter header
already does this natively in Excel (selects/highlights the whole column, no setup
needed). Making it happen automatically on every sort would require VBA macros
(converting to .xlsm, with the macro-security prompts that come with it) -- not done
here; flagged as an option if the manual click isn't sufficient.

Blurbs (column header "Notes") are left blank for now -- a separate pass (Andrew writes
some, Claude drafts the rest, Andrew approves) planned for after this structure is
confirmed useful.

Usage:
    py scripts/rankings/cheat_sheet.py
"""

import sqlite3
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import FormulaRule

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"
OUTPUT_PATH = PROJECT_ROOT / "content" / "cheat_sheet.xlsx"

SCORING_FORMAT = "ppr"
POSITION_ORDER = ["QB", "RB", "WR", "TE", "K"]
OVERALL_BAND_SIZE = 10  # rows per pick-band group on the Overall tab
TIER_GAP_MULTIPLIER = 1.5  # position tabs: a gap this many times the average = new tier
DECIMAL_FORMAT = "0.0"
SEASON_STATS_YEAR = 2025  # "last year's stats" -- update each offseason

BODY_FONT = Font(name="Arial", size=10)
BOLD_FONT = Font(name="Arial", size=10, bold=True)
HEADER_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="404040")
WHITE_BOLD_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")

ROOKIE_FILL = PatternFill("solid", fgColor="FFF2CC")   # light gold -- conditional, not static
ZEBRA_FILL = PatternFill("solid", fgColor="F2F2F2")    # conditional, not static

# Dark, distinct, white-text-readable tones -- used only on the Overall tab's Pos Rank
# column, since position tabs are already single-position and don't need this.
POSITION_FILLS = {
    "QB": PatternFill("solid", fgColor="7030A0"),  # purple
    "RB": PatternFill("solid", fgColor="385723"),  # dark green
    "WR": PatternFill("solid", fgColor="1F4E78"),  # dark blue
    "TE": PatternFill("solid", fgColor="BF8F00"),  # dark gold
    "K":  PatternFill("solid", fgColor="632423"),  # dark maroon
}

COLUMNS = [
    ("Rank", "rank", 8),
    ("Player", "full_name", 25),
    ("Pos Rank", "pos_rank_label", 11),
    ("Team", "current_team", 8),
    ("Tier", "tier_label", 13),
    ("Score", "score", 10),
    ("Games", "games_played", 9),
    ("Floor", "floor", 9),
    ("Ceiling", "ceiling", 10),
    ("Pass Yds", "passing_yards", 11),
    ("Pass TD", "passing_tds", 10),
    ("Rush Att", "rush_attempts", 11),
    ("Rush Yds", "rushing_yards", 11),
    ("Rush TD", "rushing_tds", 10),
    ("Targets", "targets", 10),
    ("Rec", "receptions", 8),
    ("Rec Yds", "receiving_yards", 10),
    ("Rec TD", "receiving_tds", 9),
    ("R+R Yds", "rush_rec_yards", 11),
    ("Rookie", "is_rookie_baseline", 10),
    ("Notes", "blurb", 40),
]
NUM_COLS = len(COLUMNS)
DECIMAL_KEYS = {"score", "floor", "ceiling"}
SEASON_STAT_KEYS = {
    "passing_yards", "passing_tds", "rush_attempts", "rushing_yards", "rushing_tds",
    "targets", "receptions", "receiving_yards", "receiving_tds", "rush_rec_yards",
}


def col_idx_for(header: str) -> int:
    return [i for i, (h, _k, _w) in enumerate(COLUMNS, start=1) if h == header][0]


PLAYER_COL_IDX = col_idx_for("Player")
POS_RANK_COL_IDX = col_idx_for("Pos Rank")
ROOKIE_COL_IDX = col_idx_for("Rookie")
ROOKIE_COL_LETTER = get_column_letter(ROOKIE_COL_IDX)


def fetch_rankings(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        """
        SELECT r.rank, p.full_name, p.position, p.current_team, r.positional_rank,
               r.score, r.games_played, r.floor, r.ceiling, r.is_rookie_baseline, r.blurb,
               s.passing_yards, s.passing_tds, s.carries AS rush_attempts,
               s.rushing_yards, s.rushing_tds, s.targets, s.receptions,
               s.receiving_yards, s.receiving_tds
        FROM rankings r
        JOIN players p ON r.gsis_id = p.gsis_id
        LEFT JOIN season_stats s ON s.gsis_id = r.gsis_id AND s.season = ?
        WHERE r.scoring_format = ?
        ORDER BY r.rank
        """,
        (SEASON_STATS_YEAR, SCORING_FORMAT),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    for r in rows:
        r["pos_rank_label"] = f"{r['position']}{r['positional_rank']}"
        for key in SEASON_STAT_KEYS - {"rush_rec_yards"}:
            r[key] = r[key] or 0
        r["rush_rec_yards"] = r["rushing_yards"] + r["receiving_yards"]
    return rows


def compute_score_gap_tiers(rows_sorted_by_score_desc: list[dict]) -> list[int]:
    """Assigns a tier index per row based on natural gaps in score, not a fixed group
    size -- a new tier starts where there's a real drop-off in value at this position,
    not an arbitrary row count."""
    if len(rows_sorted_by_score_desc) <= 1:
        return [0] * len(rows_sorted_by_score_desc)

    scores = [r["score"] for r in rows_sorted_by_score_desc]
    gaps = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]
    avg_gap = sum(gaps) / len(gaps) if gaps else 0
    threshold = max(avg_gap * TIER_GAP_MULTIPLIER, 0.1)  # floor avoids noise from tiny/float gaps

    tiers = [0]
    current_tier = 0
    for gap in gaps:
        if gap > threshold:
            current_tier += 1
        tiers.append(current_tier)
    return tiers


def write_data_row(ws, row_idx: int, r: dict, color_code_positions: bool) -> None:
    position_fill = POSITION_FILLS.get(r["position"])

    for col_idx, (_header, key, _width) in enumerate(COLUMNS, start=1):
        value = r[key]
        if key == "is_rookie_baseline":
            value = "Yes" if value else ""
        elif key in DECIMAL_KEYS and value is not None:
            value = round(value, 1)

        cell = ws.cell(row=row_idx, column=col_idx, value=value)

        if color_code_positions and col_idx == POS_RANK_COL_IDX and position_fill:
            cell.fill = position_fill
            cell.font = WHITE_BOLD_FONT
        else:
            cell.font = BOLD_FONT if col_idx == PLAYER_COL_IDX else BODY_FONT

        if key in DECIMAL_KEYS:
            cell.number_format = DECIMAL_FORMAT


def apply_conditional_formatting(ws, last_row: int, color_code_positions: bool) -> None:
    """Zebra striping and rookie highlighting as live Excel rules (not baked-in fills),
    so they read off actual row position / the Rookie column value and stay correct no
    matter how the user sorts or filters afterward. Skips the Pos Rank column on the
    Overall tab so the position color-coding always shows through."""
    last_col_letter = get_column_letter(NUM_COLS)

    if color_code_positions:
        # Skip the single Pos Rank column, cover everything else in two pieces.
        ranges = [f"A2:{get_column_letter(POS_RANK_COL_IDX - 1)}{last_row}",
                  f"{get_column_letter(POS_RANK_COL_IDX + 1)}2:{last_col_letter}{last_row}"]
    else:
        ranges = [f"A2:{last_col_letter}{last_row}"]

    for rng in ranges:
        # Rookie rule first with stopIfTrue -- a rookie row shows gold and the zebra
        # rule below is skipped for it, rather than the stripe painting over the gold.
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'${ROOKIE_COL_LETTER}2="Yes"'], fill=ROOKIE_FILL, stopIfTrue=True),
        )
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=["MOD(ROW(),2)=0"], fill=ZEBRA_FILL),
        )


def write_sheet(ws, rows: list[dict], sort_key: str, band_mode: str) -> None:
    rows = sorted(rows, key=lambda r: r[sort_key])
    color_code_positions = band_mode == "fixed_rows"  # Overall tab only

    if band_mode == "score_gap":
        band_indices = compute_score_gap_tiers(rows)
        label_fn = lambda idx: f"Tier {idx + 1}"
    else:  # "fixed_rows" -- Overall tab, grouped by row position (already sorted by overall rank)
        band_indices = [i // OVERALL_BAND_SIZE for i in range(len(rows))]
        label_fn = lambda idx: f"Picks {idx * OVERALL_BAND_SIZE + 1}-{(idx + 1) * OVERALL_BAND_SIZE}"

    for r, band_idx in zip(rows, band_indices):
        r["tier_label"] = label_fn(band_idx)

    for col_idx, (header, _key, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.freeze_panes = "A2"

    for i, r in enumerate(rows):
        write_data_row(ws, i + 2, r, color_code_positions)

    last_row = len(rows) + 1
    ws.auto_filter.ref = f"A1:{get_column_letter(NUM_COLS)}{last_row}"
    apply_conditional_formatting(ws, last_row, color_code_positions)


def write_legend(ws) -> None:
    ws.column_dimensions["A"].width = 90
    lines = [
        "Legend",
        "",
        "Score: value over replacement (VOR) -- how much better this player is than the last",
        "  realistically-startable player at their position, not raw fantasy points.",
        "Pos Rank: rank within the player's own position, prefixed with position (RB1, RB2, etc.)",
        "  -- no separate Pos column since this already conveys it (and color does too, on Overall).",
        "Tier (position tabs): players roughly interchangeable in value -- a new tier means a real",
        f"  gap in score, not a fixed group size. Tier (Overall tab): every {OVERALL_BAND_SIZE} picks,",
        "  roughly draft-round-sized chunks -- not tied to value gaps, just a readability grouping.",
        "Floor / Ceiling: 25th / 75th percentile of this player's own weekly scores (recent history)",
        "Games: number of games in the historical window used to compute the score",
        f"Pass/Rush/Rec stats: full {SEASON_STATS_YEAR} season totals. R+R Yds = rushing + receiving",
        "  yards combined (useful for pass-catching RBs).",
        "Rookie (highlighted gold): this year's draft class with zero games played -- score is a",
        "  baseline derived from draft position only, not actual performance. Treat with more",
        "  caution than a performance-based score. Highlighting is a live rule, so it stays correct",
        "  no matter how you sort/filter.",
        "Pos Rank colors (Overall tab only): QB purple, RB green, WR blue, TE gold, K maroon.",
        "Every column is filterable/sortable -- use the dropdown arrows on the header row. Clicking a",
        "  column's letter (above the header row) selects/highlights that whole column.",
        "Notes: left blank for now -- a future pass adds player notes here.",
        "",
        f"Generated from scoring_format='{SCORING_FORMAT}'. Re-run scoring.py after changing",
        "weights_config.py, then re-run this script to refresh the sheet.",
    ]
    for i, line in enumerate(lines, start=1):
        cell = ws.cell(row=i, column=1, value=line)
        cell.font = Font(name="Arial", size=10, bold=(i == 1))


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = fetch_rankings(conn)
    finally:
        conn.close()

    if not rows:
        raise SystemExit(f"No rankings found for scoring_format='{SCORING_FORMAT}' -- run scoring.py first.")

    wb = Workbook()

    overall = wb.active
    overall.title = "Overall"
    write_sheet(overall, rows, sort_key="rank", band_mode="fixed_rows")

    available_positions = {r["position"] for r in rows}
    for position in POSITION_ORDER:
        if position not in available_positions:
            continue
        ws = wb.create_sheet(position)
        position_rows = [r for r in rows if r["position"] == position]
        write_sheet(ws, position_rows, sort_key="positional_rank", band_mode="score_gap")

    legend = wb.create_sheet("Legend")
    write_legend(legend)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT_PATH)
    print(f"Wrote {len(rows)} players across {len(available_positions)} position tabs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
