# TradingGuard

TradingGuard is a personal trading decision-support and risk-management application. The project is being validated in PAPER mode before any autonomous or broker-connected phase is considered.

## Current operating mode

The active validation path is intentionally **MANUAL + GUARD**:

`Manual BUY intent → Auto Stop Loss → Risk Sizing → Risk Guard → ALLOW = paper execution`

Any result that is not `ALLOW` must not authorize a BUY. Strategy score and market condition remain useful context, but they do not independently authorize manual execution.

The purpose of this phase is to measure whether Risk Guard improves trading quality instead of merely reducing activity. Future evaluation should compare allowed and blocked opportunities using metrics such as loss avoided, false block / missed profit, expectancy, drawdown, profit factor, net P/L, and opportunity capture.

## Safety boundary

- PAPER trading only.
- No live broker/exchange execution.
- No real-money movement.
- No broker credentials are required by the active workflow.
- Broker credentials, if introduced in a future approved phase, must remain backend-only.
- Autonomous paper code may exist as a future/tested capability, but autonomous entry is not the active UI workflow during Manual + Guard validation.
- `ALLOW` is permission to execute a paper action, not a guarantee that the trade will be profitable.

## Architecture

Core modules are separated so they can be audited and tested independently:

`Market Data → Indicators → Strategy / Signal Score → Auto Stop → Risk Sizing → Risk Guard → Paper Trading → Performance Evaluation`

The frontend is a presentation/client layer. Trading decisions, risk calculations, paper accounting, and market-domain rules belong to the backend rather than being duplicated in React.

## Backend

The backend uses FastAPI.

### Run locally

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start the API:
   - `uvicorn backend.app.main:app --reload`
4. Check:
   - `http://127.0.0.1:8000/health`

Important backend areas include:

- `backend/app/market` — market data and normalized OHLCV candles
- `backend/app/indicators` — EMA, RSI, MACD and related calculations
- `backend/app/strategy` — deterministic signal scoring
- `backend/app/risk` — authoritative risk decisions
- `backend/app/backtest` — historical simulation/evaluation
- `backend/app/paper` — virtual paper account and execution workflow
- `backend/app/broker` — future broker boundary/placeholders only; not an active live-money path

## Frontend

The frontend uses React, TypeScript, and Vite.

### Run locally

1. `cd frontend`
2. `npm install`
3. `npm run dev`

The backend base URL can be selected with `VITE_API_URL`. When it is absent, the frontend uses the local development backend.

The dashboard must not fabricate missing balances, risk permission, trade history, or performance values. Backend unavailable/error states should remain explicit.

## Strategy / Signal Score

Strategy is a descriptive assessment layer, not execution authority.

Current evidence contributions are deterministic:

- EMA: bullish `+2`, neutral `0`, bearish `-2`
- RSI: overbought `-1`, oversold `+1`, otherwise `0`
- MACD: bullish `+2`, neutral `0`, bearish `-2`

Raw score range is `-5` through `+5`. The normalized score is descriptive and is **not a probability**.

Assessment thresholds:

- `<= -4`: `STRONG_BEARISH`
- `-3 .. -2`: `BEARISH`
- `-1 .. +1`: `NEUTRAL`
- `+2 .. +3`: `BULLISH`
- `>= +4`: `STRONG_BULLISH`

For the current Manual + Guard experiment, these values provide market context. They do not replace the user's manual BUY intent and do not bypass Risk Guard.

## Risk authority

`MARKET CONDITION != EXECUTION PERMISSION`

Risk Guard is the execution veto authority. A prospective manual paper BUY must have complete, authoritative risk inputs. Missing or invalid safety inputs must fail closed rather than being replaced by fabricated zeros or frontend assumptions.

`PaperTradingConfig.position_size_pct` is capital allocation and must not be treated as risk-per-trade percentage.

Auto Stop determines a defensible technical stop before Risk Sizing derives quantity/risk. Risk Sizing must not move the stop merely to make a desired quantity fit the budget.

## Backtest

The backtest layer is deterministic historical evaluation. It does not place live orders, connect to brokers, optimize parameters, or guarantee future results. Costs/slippage and execution timing are explicit so performance can be evaluated without hidden assumptions.

## Paper trading

Paper trading uses virtual capital only. It is not a broker simulator for real money.

Important constraints include long-only behavior, bounded position handling, explicit execution rules, costs/slippage, and Risk Guard authority over prospective entry.

### Persistence warning

The current paper session is **process-local/in-memory**. Restarting, sleeping, or redeploying the backend can reset paper account state. Cloud access therefore does not yet equal durable 24/7 experiment persistence. Persistent storage is a separate required milestone before long-running evidence collection can be considered reliable.

## Cloud / remote testing

Cloud configuration exists to make PAPER testing reachable without requiring the development laptop to remain on. This does not change the safety boundary: cloud deployment remains PAPER ONLY.

A production-like remote experiment should eventually add persistent storage, service health/heartbeat monitoring, durable trade/opportunity logs, and daily reporting before autonomous paper operation is treated as production-ready.

## Continuous integration

GitHub Actions is configured in `.github/workflows/ci.yml` to run on the integration branch and pull requests to `main`.

CI verifies:

- backend: dependency install + `pytest -q`
- frontend: `npm ci` + production build + lint

A historical local test count is not treated as proof for the current HEAD. The current commit is considered technically verified only when its corresponding CI checks complete successfully.

## Version status

Implemented work spans the V0.5 Risk Engine, V0.6 backtest/profit evaluation, V0.7 paper engine, V0.8 dashboard/cloud integration work, and V0.9 risk-sizing/Auto Stop/manual-guard foundations developed on the integration branch.

Because these changes currently coexist in a broad integration PR, the PR should remain unmerged until the current HEAD receives a clean CI result and the active Manual + Guard behavior is reviewed as the intended release boundary.

## Roadmap gate

The intended validation order is:

`Manual + Guard → evidence collection → Risk Guard evaluation → autonomous PAPER → 24/7 cloud PAPER → persistent LPH/reporting → final audit → broker/exchange sandbox/testnet → very small real capital only after explicit approval`

No later stage is implied to be approved merely because its supporting code exists.

## Disclaimer

TradingGuard is an engineering and personal decision-support project. Backtests, paper results, risk decisions, strategy scores, and autonomous experiments do not guarantee profit or predict future market outcomes with certainty.
