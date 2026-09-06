# TradingGuard

TradingGuard is a personal trading decision-support and risk-management application designed to evaluate market conditions without assuming future market movements can be predicted with certainty.

## Architecture overview

- Market data ingestion
- Technical indicator calculation
- Signal scoring and strategy evaluation
- Risk engine
- Paper trading workflow
- Performance evaluation and backtesting

The architecture is intentionally modular so that each component can be tested independently and evolved without introducing live trading behavior prematurely.

## Market Data Engine

The market data layer follows a provider-agnostic pattern:

MarketDataProvider
        ↓
MockMarketDataProvider
        ↓
Normalized OHLCV candles
        ↓
Technical indicators

This engine is designed to return normalized OHLCV data with consistent fields such as timestamp, symbol, timeframe, open, high, low, close, and volume. The current implementation uses simulated candle data only and must not be treated as real market information.

> The mock candle data in this phase is intentionally deterministic and offline. It is for development, local testing, and future indicator work only.

## Backend

The backend is a FastAPI service that exposes the application API and keeps future broker credentials on the server side only.

### Run the backend

1. Create and activate a virtual environment:
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.venv\Scripts\Activate.ps1`
   - macOS/Linux:
     - `python -m venv .venv`
     - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start the API:
   - `uvicorn backend.app.main:app --reload`
4. Confirm the health route:
   - `http://127.0.0.1:8000/health`

### Backend modules

- `backend/app/market` for market data access and normalized OHLCV candles
- `backend/app/indicators` for technical indicators
- `backend/app/strategy` for signal scoring and strategy logic
- `backend/app/risk` for risk management
- `backend/app/broker` for eventual broker integration placeholders only
- `backend/app/backtest` for historical simulation and evaluation

## Frontend

The frontend is built with React, TypeScript, and Vite. It currently uses mock data to render a trading dashboard.

### Run the frontend

1. Open a terminal in `frontend/`
2. Install dependencies:
   - `npm install`
3. Start the dev server:
   - `npm run dev`
4. Open the local Vite URL shown in the terminal.

## Security notes

- Broker API keys are never exposed to the React frontend.
- Broker credentials belong only in backend-controlled environment settings.
- No live order execution or broker automation is included in this initial architecture.
- No API keys or secrets are required for the current market data mock layer.

## Technical Indicators Engine

The indicator layer consumes the normalized market-data candles and produces mathematical transformations without creating trading decisions.

Market Data
    ↓
Indicators
    ↓
Strategy / Signal Score
    ↓
Risk Engine
    ↓
Paper Trading

### EMA

The EMA implementation uses a standard multiplier of $2 / (period + 1)$ and seeds the first valid EMA with the SMA of the first `period` values. Warm-up positions remain `None` until the seed is available.

### RSI

The RSI implementation uses Wilder-style smoothing with a documented flat-market behavior: when both average gain and average loss are zero, the RSI resolves to `50`. This keeps the neutral case explicit and deterministic. The RSI stays within the 0 to 100 range for valid inputs and uses warm-up placeholders until enough data exists.

### MACD

The MACD implementation uses the EMA layer for the fast and slow components, then derives the signal line from the MACD values and the histogram as `MACD - Signal`. Default periods are fast = 12, slow = 26, and signal = 9. Warm-up values remain `None` until the required EMA windows are valid.

## Strategy / Signal Score

The strategy layer is a read-only assessment layer. It evaluates indicator snapshots for evidence, produces a deterministic raw score, and records which conditions contributed to that score. It does not buy, sell, place orders, or authorize execution.

### Scoring rules

- EMA
  - bullish: +2 when `ema_fast > ema_slow`
  - neutral: 0 when `ema_fast == ema_slow`
  - bearish: -2 when `ema_fast < ema_slow`
- RSI
  - overbought: -1 when `rsi >= 70`
  - oversold: +1 when `rsi <= 30`
  - neutral: 0 when `30 < rsi < 70`
- MACD
  - bullish: +2 when `macd > macd_signal`
  - neutral: 0 when `macd == macd_signal`
  - bearish: -2 when `macd < macd_signal`

The raw score is the sum of all evidence contributions and stays within the range of -5 to +5.

### Normalized score

- `-5` maps to `0`
- `0` maps to `50`
- `+5` maps to `100`
- intermediate scores are linearly mapped within that range

Normalized score is NOT probability. It is a descriptive scale for signal posture only.

### Assessment thresholds

- raw <= -4: `STRONG_BEARISH`
- raw -3 through -2: `BEARISH`
- raw -1 through +1: `NEUTRAL`
- raw +2 through +3: `BULLISH`
- raw >= +4: `STRONG_BULLISH`

### Readiness and look-ahead protection

A `StrategyResult` is ready only when all required indicator values are present:
- `ema_fast`
- `ema_slow`
- `rsi`
- `macd`
- `macd_signal`

The service requires chronological, non-duplicate timestamps and does not use future values in the current evaluation. This is a no-look-ahead design.

### Safety and scope

- BULLISH does NOT mean BUY.
- BEARISH does NOT mean SELL.
- Strategy output does NOT authorize a trade.
- Current market data is simulated.
- This layer intentionally excludes broker logic, execution logic, AI/ML, credentials, and API keys.

### Scope and safety

The current market data remains simulated and offline by design. Indicator output and strategy assessment are mathematical transformations of mock or historical data only, and they are not predictions, trade recommendations, or risk decisions.

## V0.6 Backtest and Profit Evaluation

The V0.6 layer is a deterministic historical evaluation engine. It is intentionally a calculation-only module and does not place live orders, connect to brokers, optimize parameters, or assume future knowledge.

### Scope and conventions

- Long-only historical simulation only.
- No leverage and no short positions.
- Execution is next-bar open, with signal timestamps remaining tied to the originating bar and the actual fill on the next bar open.
- Transaction costs and slippage are applied explicitly to entry and exit notional amounts.
- A position is closed on the first bearish or neutral exit signal, executed on the following bar, or forcibly at the last available close if the data ends while the trade remains open.
- `INSUFFICIENT_DATA` never opens or closes a position and does not fabricate a signal.
- Realized-equity drawdown is computed from the timeline of completed trade equity values.
- `profit_factor` is `None` when there are no gross losses, which matches a zero-loss scenario rather than a dividing-by-zero result.
- Historical performance is not a guarantee of future results and must not be treated as a live trading recommendation.

This V0.6 engine is separate from the V0.5 risk engine. Risk remains a read-only gate on strategy quality, while backtesting is the historical performance evaluation layer that measures the realized impact of those signals.

## V0.7 Paper Trading Engine

The V0.7 paper trading engine simulates account activity with virtual capital only. It is a deterministic, calculation-only layer that consumes completed candles, existing strategy results, and existing V0.5 risk results. It does not connect to a broker or exchange, place real orders, use API keys, move money, or provide live execution.

### Scope and authority

- Paper trading is long-only with at most one open position.
- A new position requires `data_ready == True`, a `BULLISH` or `STRONG_BULLISH` assessment, `RiskDecision.ALLOW`, paper trading enabled, and no open or pending position.
- `WARNING` and `BLOCK` never authorize entry. Risk remains authoritative; paper trading does not duplicate or reinterpret the risk engine.
- There is no leverage, margin, short selling, pyramiding, averaging down, martingale behavior, or strategy optimization.

### Sequential execution

- Entry and exit signals are scheduled as explicit pending actions.
- Pending actions execute on the next received candle OPEN, with adverse slippage applied to the effective entry or exit price.
- The first pending entry or exit owns execution and cannot be replaced by later equivalent signals.
- Transaction costs are charged on entry and exit, and position sizing includes the entry fee without allowing cash to become negative.
- `INSUFFICIENT_DATA` neither opens nor closes a position and does not fabricate a signal.

The account exposes virtual cash, realized equity, open position state, pending actions, closed trades, and transaction costs. Performance metrics use realized closed trades only; unrealized profit and loss is not marked to market. A reset clears the account, pending actions, trade journal, costs, and event chronology.

The current V0.7 session is process-local and in memory. Restarting the backend clears paper state. There is no persistence and no multi-user support.

### Backtest versus paper trading

V0.6 backtesting evaluates a historical candle sequence and reports deterministic performance metrics. V0.7 paper trading processes sequential events into a virtual account without real execution. Neither version guarantees future results or provides live trading functionality.

## Current status

This project currently provides the initial modular architecture, mock dashboard data, a simulated market data engine, deterministic indicator calculations, a read-only strategy scoring layer with EMA, RSI, and MACD evidence, a deterministic V0.6 backtest/performance evaluation engine, and a V0.7 in-memory paper trading engine. It deliberately does not include live trading, broker integration, order execution, AI-powered prediction, or credentialed access.
