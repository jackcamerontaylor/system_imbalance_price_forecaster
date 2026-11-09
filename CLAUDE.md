# CLAUDE.md - project context

Read this first each session, then `docs/DECISIONS.md` and `docs/PROGRESS.md`.

## Goal
Day-ahead GB System Imbalance Price (SIP, £/MWh) forecaster. For a UK day D, forecast every
half-hour settlement period, as would have been known at **07:00 and 09:00 UK time on D-1**.
Python, managed with **uv**; eventually runnable as a script via Docker/compose.
Brief: `docs/BRIEF.md`. Data catalogue: `candidate_data/README.md`.

## Working rules
- **Do only what the user asks.** Currently: exploration in `notebooks/`. Do not write modelling
  code, packages or tests unprompted.
- Raw timestamps are UTC; "day" and run times are UK local (`Europe/London`). Clock-change days
  have 46/50 periods.
- Avoid look-ahead: only use information available at the run cutoff.
- Never commit CSVs (git-ignored, >100 MB).
- Do not mention hiring/interview context anywhere in the repo (README, docs, commits).

## Commands
```
uv sync
uv run python -m sip_forecaster backtest | forecast --day YYYY-MM-DD | holdout
```

## Memory files (keep these updated when asked / at the end of a work chunk)
- `docs/DECISIONS.md` - decision log.
- `docs/PROGRESS.md` - what was done, findings, open questions, next steps.
