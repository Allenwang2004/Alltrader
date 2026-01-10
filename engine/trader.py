import sys, os, time, pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Type
from connector.okx_order import OKXOrderClient
from engine.online.oms import OrderManager, wait_order_filled
from engine.online.rms import RiskManager
from connector.okx_kline import OKXKlineFetcher, fetch_futures_klines
from connector.okx_ws_ticker import OKXWsTicker
from datawarehouse.kline_db import insert_kline, fetch_klines_from_db, listen_and_store_kline, fetch_multi_interval_closes_from_db
from strategy.longstrategy import LongStrategy

class TradingState:
    SIGNAL = 'signal'
    OMS = 'oms'
    RMS = 'rms'

def trading_main(strategy_cls: Type, api_key: str, api_secret: str, passphrase: str, symbol: str, intervals: list, window: int = 100, qty: float = 1):
    okx_client = OKXOrderClient(api_key, api_secret, passphrase)
    ws = OKXWsTicker(symbol)
    ws.start()
    order_manager = OrderManager(okx_client)
    risk_manager = RiskManager()
    state = TradingState.SIGNAL
    position = 0
    entry_price = None
    print("Starting trading state machine...")
    while True:
        if state == TradingState.SIGNAL:
            # db_read_time = time.time()
            df_15m = fetch_klines_from_db(symbol, '15m', window)
            df_1h = fetch_klines_from_db(symbol, '1H', window)
            # db_end_time = time.time()
            # print(f"[SIGNAL] DB read time: {db_end_time - db_read_time:.2f}s")
            strategy = strategy_cls()
            # generate_singals_start = time.time()
            signal = strategy.generate_signals(df_1h, df_15m)
            # generate_singals_end = time.time()
            # print(f"[SIGNAL] Signal generation time: {generate_singals_end - generate_singals_start:.2f}s")
            current_price = ws.get_last_price()
            if signal == 1:
                order_side = 'long'
            elif signal == -1:
                order_side = 'short'
            else:
                time.sleep(1)
                continue
            state = TradingState.OMS
            oms_action = order_side
            oms_qty = qty
            oms_price = current_price
        elif state == TradingState.OMS:
            print(f"[OMS] execute order: {oms_action}")
            if oms_action == 'long':
                resp = order_manager.open_long(symbol, oms_qty)
            elif oms_action == 'short':
                resp = order_manager.open_short(symbol, oms_qty)
            elif oms_action == 'close_long':
                resp = order_manager.close_position(symbol, oms_qty, position_side='long')
            elif oms_action == 'close_short':
                resp = order_manager.close_position(symbol, oms_qty, position_side='short')
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
                    state = TradingState.SIGNAL
                    continue
            else:
                print("[OMS] No order_id found in response, moving to SIGNAL state")
                state = TradingState.SIGNAL
                continue
            if oms_action in ('long', 'short'):
                position = 1 if oms_action == 'long' else -1
                entry_price = oms_price
                risk_manager.reset()
                state = TradingState.RMS
            elif oms_action.startswith('close'):
                position = 0
                entry_price = None
                state = TradingState.SIGNAL
        elif state == TradingState.RMS:
            current_price = ws.get_latest_price()
            print(f"[RMS] entry={entry_price} price={current_price} pos={position}")
            if risk_manager.should_add_position(entry_price, current_price, position):
                qty = risk_manager.add_position(current_price, base_qty=qty)
                if qty:
                    print(f"[RMS] adding position, qty={qty}")
                    oms_action = 'long' if position == 1 else 'short'
                    oms_qty = qty
                    oms_price = current_price
                    state = TradingState.OMS
                    continue

            if risk_manager.check_take_profit(current_price, position):
                print("[RMS] taking profit, closing position")
                oms_action = 'close_long' if position == 1 else 'close_short'
                oms_qty = qty  # 假設全平
                oms_price = current_price
                state = TradingState.OMS
                continue
            time.sleep(1)

if __name__ == "__main__":
    api_key = os.getenv("OKX_API_KEY")
    api_secret = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_API_PASSPHRASE")
    symbol = "BTC-USDT"
    intervals = ['15m', '1H']
    trading_main(LongStrategy, api_key, api_secret, passphrase, symbol, intervals)
