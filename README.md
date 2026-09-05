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

## Current status

This project currently provides the initial modular architecture, mock dashboard data, health endpoint, and a simulated market data engine. It deliberately does not include live trading, broker integration, order execution, or indicator logic beyond the normalized market data layer.
