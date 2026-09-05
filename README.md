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
Indicators (future phase)

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
Strategy (future)
    ↓
Risk Engine (future)

### EMA

The EMA implementation uses a standard multiplier of $2 / (period + 1)$ and seeds the first valid EMA with the SMA of the first `period` values. Warm-up positions remain `None` until the seed is available.

### RSI

The RSI implementation uses Wilder-style smoothing with a documented flat-market behavior: when both average gain and average loss are zero, the RSI resolves to `50`. This keeps the neutral case explicit and deterministic. The RSI stays within the 0 to 100 range for valid inputs and uses warm-up placeholders until enough data exists.

### MACD

The MACD implementation uses the EMA layer for the fast and slow components, then derives the signal line from the MACD values and the histogram as `MACD - Signal`. Default periods are fast = 12, slow = 26, and signal = 9. Warm-up values remain `None` until the required EMA windows are valid.

### Scope and safety

The current market data remains simulated and offline by design. Indicator output is a mathematical transformation of historical or mock data only, and it is not a prediction, trade signal, recommendation, or risk decision.

## Current status

This project currently provides the initial modular architecture, mock dashboard data, a simulated market data engine, and a deterministic indicator layer with EMA, RSI, and MACD calculations. It deliberately does not include live trading, broker integration, order execution, signal scoring, or prediction logic.
