import sys, os, time, pandas as pd
from queue import Queue
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Type
from connector.okx_order import OKXOrderClient
from engine.online.oms import OrderManager, wait_order_filled
from engine.online.rms import RiskManager
from connector.okx_kline import OKXKlineFetcher, fetch_futures_klines
from connector.okx_ws_ticker import OKXWsTicker, OKXWsKline
from datawarehouse.kline_db import insert_kline, fetch_klines_from_db, listen_and_store_kline, fetch_multi_interval_closes_from_db
from strategy.longstrategy import LongStrategy
from engine.state import TimeframeState

class TradingState:
    SIGNAL = 'signal'
    OMS = 'oms'
    RMS = 'rms'

def trading_main(strategy_cls: Type, api_key: str, api_secret: str, passphrase: str, symbol: str, intervals: list, window: int = 100, qty: float = 0.01):
    okx_client = OKXOrderClient(api_key, api_secret, passphrase)
    ws = OKXWsTicker(symbol)
    ws.start()
    state = TimeframeState()
    q_15m = Queue()
    q_1h = Queue()

    print("[INIT] fetching REST klines")
    for k in fetch_futures_klines(symbol=symbol, interval="15m", limit=window):
        state.m15.append(_normalize_kline(k))
    for k in fetch_futures_klines(symbol=symbol, interval="1H", limit=window):
        state.h1.append(_normalize_kline(k))
    print("[INIT] REST done")

    ws_15m = OKXWsKline(symbol, "15m", q_15m)
    ws_1h = OKXWsKline(symbol, "1H", q_1h)
    ws_15m.start()
    ws_1h.start()
    order_manager = OrderManager(okx_client)
    risk_manager = RiskManager()
    state_machine = TradingState.SIGNAL
    position = 0
    entry_price = None
    print("Starting trading state machine...")
    while True:
        if state_machine == TradingState.SIGNAL:
            # update latest klines from websocket queues
            while not q_15m.empty():
                bar = q_15m.get()
                state.m15.append(_normalize_kline(bar))
                print("[MAIN] new 15m bar", bar.get("close", bar.get("close_price")))

            while not q_1h.empty():
                bar = q_1h.get()
                state.h1.append(_normalize_kline(bar))
                print("[MAIN] new 1h bar", bar.get("close", bar.get("close_price")))

            df_15m = pd.DataFrame(state.m15.get_all())
            df_1h = pd.DataFrame(state.h1.get_all())

            if df_15m.empty or df_1h.empty:
                time.sleep(1)
                continue

            strategy = strategy_cls()
            signal = strategy.generate_signals(df_15m, df_1h)
            current_price = ws.get_last_price()
            if signal == 1:
                order_side = 'long'
            elif signal == -1:
                order_side = 'short'
            else:
                time.sleep(1)
                continue
            state_machine = TradingState.OMS
            oms_action = order_side
            oms_qty = qty
            oms_price = current_price
        elif state_machine == TradingState.OMS:
            prev_position = position
            total_qty = sum(p["qty"] for p in risk_manager.positions)
            print(f"[OMS] execute order: {oms_action}")
            if oms_action == 'long':
                resp = order_manager.open_long(symbol, oms_qty)
            elif oms_action == 'short':
                resp = order_manager.open_short(symbol, oms_qty)
            elif oms_action == 'close_long':
                resp = order_manager.close_position(symbol, total_qty, position_side='long')
            elif oms_action == 'close_short':
                resp = order_manager.close_position(symbol, total_qty, position_side='short')
            else:
                resp = None
            order_id = None
            # Extract order_id from response
            if resp and 'data' in resp and len(resp['data']) > 0:
                order_id = resp['data'][0].get('ordId')
            if order_id:
                filled = wait_order_filled(okx_client, symbol, order_id)
                if not filled:
                    print("[OMS] order is not filled in time, retrying...")
                    state_machine = TradingState.SIGNAL
                    continue
            else:
                print("[OMS] No order_id found in response, moving to SIGNAL state")
                state_machine = TradingState.SIGNAL
                continue
            if oms_action in ('long', 'short'):
                if prev_position == 0:
                    position = 1 if oms_action == 'long' else -1
                    entry_price = oms_price
                    risk_manager.reset()
                    risk_manager.add_position(entry_price, base_qty=oms_qty)
                else:
                    # adding to existing position
                    risk_manager.add_position(oms_price, base_qty=oms_qty)
                state_machine = TradingState.RMS
            elif oms_action.startswith('close'):
                position = 0
                entry_price = None
                state_machine = TradingState.SIGNAL
        elif state_machine == TradingState.RMS:
            current_price = ws.get_last_price()
            print(f"[RMS] entry={entry_price} price={current_price} pos={position}")
            if risk_manager.should_add_position(entry_price, current_price, position):
                add_qty = risk_manager.get_next_qty(base_qty=qty)
                if add_qty:
                    print(f"[RMS] adding position, qty={add_qty}")
                    oms_action = 'long' if position == 1 else 'short'
                    oms_qty = add_qty
                    oms_price = current_price
                    state_machine = TradingState.OMS
                    continue

            if risk_manager.check_take_profit(current_price, position):
                print("[RMS] taking profit, closing position")
                oms_action = 'close_long' if position == 1 else 'close_short'
                total_qty = sum(p["qty"] for p in risk_manager.positions)
                oms_qty = total_qty
                oms_price = current_price
                state_machine = TradingState.OMS
                continue
            time.sleep(1)

def _normalize_kline(k: dict) -> dict:
    if 'timestamp' in k:
        ts = k['timestamp']
        open_price = k.get('open_price', k.get('open'))
        high_price = k.get('high_price', k.get('high'))
        low_price = k.get('low_price', k.get('low'))
        close_price = k.get('close_price', k.get('close'))
        volume = k.get('volume', 0)
    else:
        ts = k.get('ts')
        open_price = k.get('open')
        high_price = k.get('high')
        low_price = k.get('low')
        close_price = k.get('close')
        volume = k.get('volume', 0)

    return {
        'timestamp': pd.to_datetime(ts, unit='ms'),
        'open': float(open_price),
        'high': float(high_price),
        'low': float(low_price),
        'close': float(close_price),
        'volume': float(volume)
    }

if __name__ == "__main__":
    api_key = os.getenv("OKX_API_KEY")
    api_secret = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_API_PASSPHRASE")
    symbol = "BTC-USDT"
    intervals = ['15m', '1H']
    trading_main(LongStrategy, api_key, api_secret, passphrase, symbol, intervals)
