"""
Tunable parameters for the rankings engine (scoring.py). Change numbers here and
re-run scoring.py -- most tuning should never require touching scoring.py's logic.

This is the file to edit after reviewing real rankings output and disagreeing with
where a player landed. Work backwards from the disagreement to which parameter below
is most likely responsible, adjust it, and re-run.
"""

WEIGHTS = {
    # --- Scoring format ---
    "scoring_format": "ppr",  # "ppr" or "half_ppr" -- which fantasy_points column to score from

    # --- Recency eligibility ---
    # A player with zero games in this many seasons before the reference season is
    # excluded from scoring entirely (almost certainly retired/out of the league).
    # This matters because a recency-weighted AVERAGE can't distinguish "recently
    # active" from "long retired" on its own -- averaging cancels out any constant
    # per-player scale factor, so two players with identical stats but from different
    # (internally uniform) seasons would otherwise score identically. A hard
    # eligibility cutoff is simpler and more honest than trying to fake this with decay math.
    "eligibility_window_seasons": 2,

    # --- Recency weighting (within an eligible player's own game log) ---
    # Recent games predict next season better than old ones (injuries, aging, role
    # changes). Both are decay factors applied per "step" back in time -- 1.0 = no
    # decay (everything counts equally); lower = older data matters less.
    "season_decay_rate": 0.65,   # multiplies weight for each season further back
    "week_decay_rate": 0.97,     # multiplies weight for each week further back within a season

    # --- Sample size handling ---
    # A player with only a handful of games shouldn't be judged purely on their
    # (small-sample, noisy) rate stats. Below this many games in the weighted window,
    # their score gets pulled toward the positional average -- shrinkage_strength of
    # 0 = no pulling at all, 1 = fully replaced by the positional average.
    "min_games_for_full_confidence": 8,
    "low_sample_shrinkage_strength": 0.5,

    # --- Opportunity bonus ---
    # How much extra weight underlying opportunity (target_share, wopr) gets on top of
    # raw fantasy points. This is what lets the formula catch a player whose role/usage
    # is trending up before their counting stats fully reflect it yet.
    "opportunity_weight": 0.15,
}

# Rough replacement-level rank per position, used for value-over-replacement (VOR)
# scoring when building one overall cross-position board -- i.e. "how much better is
# this player than the guy you could have had for free/late" rather than just raw
# points. Tune these to your actual league size/format; defaults assume a 12-team
# league with standard roster requirements.
REPLACEMENT_RANK = {
    "QB": 12,
    "RB": 30,
    "WR": 36,
    "TE": 12,
    "K": 12,
}
