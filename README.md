# Live Trade

Live Trade is a lightweight Python trading toolbox for backtesting and live trading with multiple exchanges (OKX, Binance). It includes:

- CLI / TUI interface (Textual) for selecting exchange, entering API keys, selecting strategy and symbols.
- Backtesting engine and simple strategy templates (MACD, entry/exit strategies).
- Online trading runner with modular OMS (Order Manager) and RMS (Risk Manager).
- Datawarehouse utilities to persist K-line (candlestick) data to SQLite and re-load for strategies.
- Connector modules for OKX (REST + WebSocket) and Binance (partial).

This repository is intended as a developer playground and a small production-capable runner for algorithmic strategy research.

## Project Layout

- `cli_tui.py` - Textual TUI application for interactive control (select exchange, provide API keys, choose strategy, start recording symbols, start trading).
- `engine/` - Core engine modules
	- `backtest/` - Backtesting harness and Strategy base class
	- `trader.py` - Online trading state-machine runner (signal → OMS → RMS)
	- `online/oms.py` - Order manager (ensures orders are placed and confirmed)
	- `online/rms.py` - Risk manager (position sizing, add-position, take-profit logic)
- `strategy/` - Strategy templates (MACD, simple entry/exit, long/short examples)
- `connector/` - Exchange connectors and utilities
	- `okx_order.py` - OKX REST order client (signed requests)
	- `okx_kline.py` - OKX Kline fetcher (REST, paginated)
	- `okx_ws_ticker.py` - OKX WebSocket ticker for live prices
	- `binance_*` - Binance helpers (partial)
- `datawarehouse/kline_db.py` - SQLite helpers for storing and retrieving K-line data
- `test/` - Unit tests for connectors and key functions

## Quickstart

1. Create a virtual environment and install dependencies (example using pip):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the Textual TUI (CLI):

```bash
python cli_tui.py
```

From the TUI you can:
- Select exchange and input API keys (OKX passphrase is required for OKX)
- Select a strategy and set a trading symbol
- Start continuous K-line recording for a symbol+interval (stores to `datawarehouse/kline.db`)
- Start live trading (the app will spawn the `trading_main` runner in background)

## Backtesting

Backtesting tools live under `engine/backtest`. Example usage:

```python
from engine.backtest.backtest import Backtester
from strategy.macd_strategy import MACDStrategy

# load historical data into a pandas DataFrame and run
bt = Backtester(df, MACDStrategy)
results = bt.run()
```

## Backtest UI

Run the Streamlit UI for backtesting and performance charts:

```bash
streamlit run app/backtest_ui.py
```

In the UI, upload a 1m CSV (must contain `timestamp` or `ts` column), select a strategy, set parameters, and click "執行回測".

## Online Trading Architecture

The online trading runner uses a single state machine (`trading_main`) to ensure only one component is active at a time:

- SIGNAL: fetches multi-interval K-line data and asks the strategy for signals
- OMS: order manager places market orders and waits for confirmation/fill
- RMS: risk manager monitors price via WebSocket and handles add-position / take-profit, which can call OMS again

This design ensures only one thread is performing actions at a time while still allowing asynchronous components (e.g., WebSocket) to feed data.

## Datawarehouse (SQLite)

Use `datawarehouse.kline_db` to store and load K-lines. Key functions:

- `insert_kline(symbol, interval, kline)` - store one K-line record
- `fetch_klines_from_db(symbol, interval, window)` - load the latest `window` rows
- `fetch_multi_interval_closes_from_db(symbol, intervals, window)` - returns a combined DataFrame with close columns for multiple intervals (e.g., `close_1h`, `close_15m`)

Stored DB path: `datawarehouse/kline.db` by default.

## OKX Notes

- OKX signing requires your API key, secret and the passphrase you set when creating the API key. Ensure system time is accurate (NTP) to avoid signature errors.
- For demo trading use the OKX demo site and demo API credentials.
- If you see `Invalid Sign`, check that you are using the correct base URL / endpoint and that passphrase, API key and secret match the account.

## Troubleshooting

- HTTP 400 on K-line fetch: ensure `after`/`before` params are timestamps in milliseconds (OKX expects numeric timestamps for paginated ranges).
- OKX `Invalid Sign`: check API key/secret/passphrase and ensure timestamp formatting and signature algorithm match OKX docs.
- If the TUI reports `trading is running`, the background trading thread is already active; stop the app and restart to reset.

## Tests

Run tests in the `test/` folder with pytest:

```bash
pytest -q
```

## Development Notes

- The project is intentionally modular: replace strategy classes or connector implementations without changing the runner.
- If you add new strategies, ensure the `utils/strategy_utils.py` is updated to expose them to the TUI.

If you'd like, I can also:
- Add CLI flags to `cli_tui.py` to preconfigure intervals and windows
- Add a small README section showing how to create OKX demo API keys
- Add unit tests for `fetch_multi_interval_closes_from_db`
