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
    # Per-position override for the games threshold above. Added 2026-07-26: kickers
    # with as few as 8-24 games were outranking established kickers with 90+ games --
    # the K position has a much smaller, more tightly-scored pool than other positions
    # (every kicker scores in a narrow band), so VOR swings much more easily on a small,
    # possibly-lucky sample there than it does at, say, RB or WR. Positions not listed
    # here just use the plain "min_games_for_full_confidence" value above.
    "min_games_for_full_confidence_by_position": {
        "K": 24,
    },
    # Same idea, for shrink strength itself: raising the games threshold alone still
    # leaves a global 0.5 strength, which caps out at only 50% pulled toward the
    # average even at zero games -- not enough to stop a hot small sample (e.g. 9
    # games) from still outranking established kickers. K needs a much stronger pull.
    "low_sample_shrinkage_strength_by_position": {
        "K": 0.9,
    },
    # A player below THIS many games is excluded from scoring entirely (not just
    # heavily shrunk) -- distinct from min_games_for_full_confidence above, which
    # controls how STRONGLY a low-sample player gets pulled toward the positional
    # average, not whether they're scored at all. Added 2026-08-24: Phil Mafah (1 game,
    # a Week 18 finale where teams commonly rest starters and backups get run) still
    # shrunk toward the positional AVERAGE -- a generous prior for a player we know
    # almost nothing about -- landing him at "barely above replacement" (RB24) instead
    # of near the bottom, where a genuinely unproven player belongs. A 1-2 game sample
    # is closer to no information than to "this guy is roughly average," so below this
    # threshold a player is dropped rather than scored with a false sense of confidence.
    "min_games_to_score": 2,
    "min_games_to_score_by_position": {},  # per-position override, same pattern as above -- none needed yet

    # --- Opportunity bonus ---
    # How much extra weight underlying opportunity (target_share, wopr) gets on top of
    # raw fantasy points. This is what lets the formula catch a player whose role/usage
    # is trending up before their counting stats fully reflect it yet.
    "opportunity_weight": 0.15,

    # --- Rookie baseline (players with zero weekly_stats, this year's draft class only) ---
    # Draft capital substitutes for performance history: baseline = positional_avg *
    # multiplier, where multiplier = min(cap, max(floor, 1 - (pick-1)/scale)). Pick 1 at
    # a position gets close to the full positional average (subject to the cap below);
    # deep picks approach the floor.
    "rookie_draft_capital_scale": 250,
    "rookie_score_floor_multiplier": 0.05,
    # Per-position cap on the multiplier itself (default 1.0 = no cap, i.e. a pick-1
    # rookie can reach the full positional average). Added 2026-07-26: rookie QBs
    # (Fernando Mendoza, Ty Simpson) were landing in the real QB1-10 range purely off
    # high draft capital, which doesn't match reality -- rookie QBs historically have a
    # much rockier first-year transition than rookie RBs (who often produce
    # immediately), so the same draft-capital curve shouldn't apply evenly across
    # positions. Deliberately left at 1.0 (unchanged) for RB/WR/TE/K per Andrew's call
    # -- examine those positions on their own before adjusting them.
    "rookie_position_multiplier_cap": {
        "QB": 0.5,
    },
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
