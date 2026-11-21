#!/usr/bin/env python3
"""GTA VI trophy earn-rate forecaster (make.fun: gta6-trophy-rarity-forecast-01).

Reads a case file (the house's recorded history of Exophase earn rates for
every PS5 trophy of GTA VI) and writes, for each trophy, five quantiles of
its earn rate at the case's target time.

Model, per trophy:
  * Work on the logit scale, where the score (pinball loss) is measured.
  * Fit a weighted straight line of logit(rate) against ln(1 + hours since
    release): earn rates grow fast right after launch and saturate, and the
    log-time axis bends the line the same way. Recent reads weigh more.
  * Shrink the fitted slope toward the persistence forecast (last rate), so
    a quiet series stays quiet and a noisy one is not extrapolated wildly.
  * Spread: a random-walk term that grows with the square root of the
    horizon (as in the house baseline), plus the fit's own residual scale,
    plus a constant allowance for the step jumps Exophase makes when it
    refreshes its counts.
  * A trophy nobody has earned yet gets a small prior from the tracked
    player count (its rate is below one earner over the player base) with a
    wide spread, instead of a hard zero.

Standard library only, no network. Runs in well under a second per case.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

Z = [-1.6448536269514722, -0.6744897501960817, 0.0,
     0.6744897501960817, 1.6448536269514722]
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def logit_pct(rate_pct, players):
    """Logit of an earn rate given in percent, with a counting floor.

    A printed rate of 0 means fewer than one tracked earner, so the floor
    sits at half an earner over the player base (in percent), and never
    above the smallest printable step of 0.01 percent.
    """
    floor_pct = min(0.005, 50.0 / max(players, 1))
    p = clamp(rate_pct, floor_pct, 99.99) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit_pct(y):
    p = 1.0 / (1.0 + math.exp(-clamp(y, -30.0, 30.0)))
    return clamp(p * 100.0, 0.0, 100.0)


def weighted_line(xs, ys, ws):
    """Weighted least squares y ~ a + b*x; returns (a, b, residual_std)."""
    sw = sum(ws)
    if sw <= 0:
        return ys[-1], 0.0, 0.0
    mx = sum(w * x for x, w in zip(xs, ws)) / sw
    my = sum(w * y for y, w in zip(ys, ws)) / sw
    sxx = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    if sxx <= 1e-12:
        return my, 0.0, 0.0
    sxy = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    b = sxy / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    var = sum(w * r * r for r, w in zip(resid, ws)) / sw
    return a, b, math.sqrt(max(var, 0.0))


def forecast_trophy(series, target_hours, horizon_days):
    """series: list of (hours_since_release, rate_pct, players_tracked).

    Returns the five quantile rates (percent) at the target.
    """
    last_rate = series[-1][1]
    last_players = series[-1][2]
    persist = logit_pct(last_rate, last_players)

    xs = [math.log1p(h) for h, _, _ in series]
    ys = [logit_pct(r, n) for _, r, n in series]
    # Recent reads weigh more: a 24 h half-life by age before the last read.
    last_h = series[-1][0]
    ws = [0.5 ** ((last_h - h) / 24.0) for h, _, _ in series]

    a, b, resid_std = weighted_line(xs, ys, ws)
    # Shrink the slope: with few effective reads the line is mostly noise.
    eff_n = (sum(ws) ** 2) / max(sum(w * w for w in ws), 1e-12)
    b_shrunk = b * eff_n / (eff_n + 6.0)
    b_shrunk = clamp(b_shrunk, -0.35, 2.0)

    x_target = math.log1p(target_hours)
    trend = a + b_shrunk * x_target + (b - b_shrunk) * xs[-1] * 0.0
    # Re-anchor the shrunk line at the last observed point so the forecast
    # starts from where the rate actually is, not from the fitted level.
    trend = ys[-1] + b_shrunk * (x_target - xs[-1])

    if last_rate <= 0.0:
        # Nobody tracked has earned it yet: keep the median near the
        # counting floor and let the spread do the talking.
        median = persist + 0.35 * math.sqrt(max(horizon_days, 0.0))
        sigma = math.sqrt((0.5 * math.sqrt(max(horizon_days, 0.0))) ** 2 + 0.9 ** 2)
    else:
        # Blend the trend with persistence; log-time already saturates, so
        # the trend leads, but never fully leaves the last read behind.
        median = 0.7 * trend + 0.3 * persist
        walk = 0.5 * math.sqrt(max(horizon_days, 0.0))
        sigma = math.sqrt(walk ** 2 + resid_std ** 2 + 0.25 ** 2)
    sigma = clamp(sigma, 0.35, 2.4)
    median = clamp(median, logit_pct(0.0, last_players) - 0.5, 6.9)

    qs = [inv_logit_pct(median + z * sigma) for z in Z]
    qs = [round(q, 4) for q in qs]
    for i in range(1, len(qs)):
        if qs[i] < qs[i - 1]:
            qs[i] = qs[i - 1]
    return qs


def forecast_case(case):
    trophies = case["trophies"]
    history = sorted(case["history"], key=lambda r: r["slot"])
    release = parse_time(case["game"]["release_date"] + "T00:00:00Z")
    target = parse_time(case["target"])
    target_hours = (target - release).total_seconds() / 3600.0
    last_time = parse_time(history[-1]["slot"])
    horizon_days = max((target - last_time).total_seconds() / 86400.0, 0.0)

    rows = []
    for idx, trophy in enumerate(trophies):
        series = []
        for read in history:
            at = parse_time(read["slot"])
            hours = (at - release).total_seconds() / 3600.0
            series.append((hours, float(read["rates"][idx]),
                           int(read["players_tracked"])))
        rows.append({"id": trophy["id"],
                     "q": forecast_trophy(series, target_hours, horizon_days)})
    return {"trophies": rows}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    if not names and len(sys.argv) > 1:
        names = [os.path.basename(sys.argv[1])]
        in_dir = os.path.dirname(os.path.abspath(sys.argv[1]))
    for name in names:
        with open(os.path.join(in_dir, name), encoding="utf-8") as fh:
            case = json.load(fh)
        result = forecast_case(case)
        out_name = case["id"] + ".out"
        with open(os.path.join(out_dir, out_name), "w", encoding="utf-8") as fh:
            json.dump(result, fh, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
