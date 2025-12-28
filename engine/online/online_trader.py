import time
import pandas as pd
from typing import Type
from connector.okx_order import OKXOrderClient
from connector.okx_kline import OKXKlineFetcher
from grafana.db import insert_kline, fetch_klines_from_db
from strategy.simple_entry_exit_strategy import SimpleEntryExitStrategy
import threading

def listen_and_store_kline(symbol: str, interval: str, market_type: str = "futures"):
    """
    持續監聽最新 kline 並存入資料庫。
    每個 interval 取最新一根，存入 DB。
    """
    fetcher = OKXKlineFetcher(market_type=market_type)
    last_timestamp = None
    while True:
        klines = fetcher.fetch_klines(symbol=symbol, interval=interval, limit=1)
        df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
        ts = df['timestamp'].iloc[-1]
        if ts != last_timestamp:
            insert_kline(symbol, interval, df.iloc[-1].to_dict())
            last_timestamp = ts
            print(f"已存入新K線: {ts}")
        else:
            print("尚無新K線")
        # 休息到下個 interval
        if interval.endswith('m'):
            sleep_sec = int(interval[:-1]) * 60
        elif interval.endswith('H'):
            sleep_sec = int(interval[:-1]) * 3600
        else:
            sleep_sec = 60
        time.sleep(sleep_sec)

def run_online_trading(strategy_cls: Type, api_key: str, api_secret: str, passphrase: str, symbol: str, interval: str = "5m", market_type: str = "futures", window: int = 100):
    okx_client = OKXOrderClient(api_key, api_secret, passphrase)
    position = 0
    print("開始實盤監聽與交易...")
    while True:
        # 從 DB 取最新 window 根K線
        df = fetch_klines_from_db(symbol, interval, window)
        if df is None or len(df) < window:
            print("資料不足，等待更多K線...")
            time.sleep(10)
            continue
        strategy = strategy_cls()
        signal = strategy.generate_signals(df).iloc[-1]
        print(f"最新訊號: {signal}")
        # 下單邏輯
        if signal == 1 and position <= 0:
            print("做多開倉")
            # okx_client.open_long(symbol, ...)
            position = 1
        elif signal == -1 and position >= 0:
            print("做空開倉")
            # okx_client.open_short(symbol, ...)
            position = -1
        elif signal == 0 and position != 0:
            print("平倉")
            # okx_client.close_position(symbol, ...)
            position = 0
        else:
            print("持倉不變")
        time.sleep(10)


if __name__ == "__main__":
    # 啟動監聽與交易（需分開執行或用多執行緒/多程序）
    # 這裡僅示範單程序邏輯，實務建議分開啟動
    symbol = "BTC-USDT"
    interval = "5m"
    t1 = threading.Thread(target=listen_and_store_kline, args=(symbol, interval, "futures"), daemon=True)
    t1.start()
    # run_online_trading(
    #     strategy_cls=SimpleEntryExitStrategy,
    #     api_key="YOUR_API_KEY",
    #     api_secret="YOUR_API_SECRET",
    #     passphrase="YOUR_PASSPHRASE",
    #     symbol=symbol,
    #     interval=interval,
    #     market_type="futures",
    #     window=100
    # )
