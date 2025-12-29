import sys, os, time, pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Type
from connector.okx_order import OKXOrderClient
from engine.online.oms import OrderManager
from engine.online.rms import RiskManager
from connector.okx_kline import OKXKlineFetcher, fetch_futures_klines
from connector.okx_ws_ticker import OKXWsTicker
from datawarehouse.kline_db import insert_kline, fetch_klines_from_db, listen_and_store_kline, fetch_multi_interval_closes_from_db
from strategy.long import LongStrategy

class TradingState:
    SIGNAL = 'signal'
    OMS = 'oms'
    RMS = 'rms'

def wait_order_filled(order_client, symbol, order_id, poll_interval=1, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        info = order_client.get_order(symbol, order_id=order_id)
        status = info.get('data', [{}])[0].get('state')
        if status in ('filled', 'partially_filled', 'success', '2'):  # 2=成交
            return True
        time.sleep(poll_interval)
    return False

def trading_main(strategy_cls: Type, api_key: str, api_secret: str, passphrase: str, symbol: str, intervals: list, window: int = 100):
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
            df_15m = fetch_klines_from_db(symbol, '15m', window)
            df_1H = fetch_klines_from_db(symbol, '1H', window)
            strategy = strategy_cls()
            signal = strategy.generate_signals(df_15m, df_1H).iloc[-1]
            current_price = ws.get_last_price()
            print(f"Latest signal: {signal}")
            if signal == 1:
                order_side = 'long'
            elif signal == -1:
                order_side = 'short'
            else:
                time.sleep(5)
                continue
            state = TradingState.OMS
            oms_action = order_side
            oms_qty = 1
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
            if resp and 'data' in resp and len(resp['data']) > 0:
                order_id = resp['data'][0].get('ordId')
            if order_id:
                filled = wait_order_filled(okx_client, symbol, order_id)
                if not filled:
                    print("[OMS] 訂單未成交，重試/跳過...")
                    state = TradingState.SIGNAL
                    continue
            else:
                print("[OMS] 無法取得 order_id 重試/跳過...")
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
                qty = risk_manager.add_position(current_price, 1)
                if qty:
                    print(f"[RMS] 補倉 qty={qty}")
                    oms_action = 'long' if position == 1 else 'short'
                    oms_qty = qty
                    oms_price = current_price
                    state = TradingState.OMS
                    continue
            # 止盈
            if risk_manager.check_take_profit(current_price, position):
                print("[RMS] 觸發止盈，全部平倉")
                oms_action = 'close_long' if position == 1 else 'close_short'
                oms_qty = 1  # 假設全平
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
