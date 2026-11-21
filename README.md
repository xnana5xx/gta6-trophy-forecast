# gta6-trophy-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/xnana5xx/gta6-trophy-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/xnana5xx/gta6-trophy-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts, for each of GTA VI's 55 PS5 trophies, five quantiles (5/25/50/75/95%) of its earn rate at a case's target time, scored by pinball loss on the logit scale. Per trophy, main.py fits a weighted straight line of logit(earn rate) against log-time since release (recent Exophase reads weigh more), shrinks the slope toward the persistence forecast, re-anchors at the last observed rate, and blends trend with persistence by horizon. The spread combines a square-root-of-horizon random walk, the fit's residual scale, and an allowance for Exophase's step refreshes; a trophy nobody has earned yet gets a counting-floor prior from the tracked player count instead of a hard zero. Standard library only, no network, runs in well under a second per case.

## Run it

```sh
MAKEFUN_INPUT_DIR=<dir with .in case files> MAKEFUN_OUTPUT_DIR=<output dir> python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=raa4b3k9&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
