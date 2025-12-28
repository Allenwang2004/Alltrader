import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sqlite3
import pandas as pd
import time
from connector.okx_kline import OKXKlineFetcher, fetch_futures_klines
from typing import Dict, Any

def get_db_conn(db_path: str = "datawarehouse/kline.db"):
    conn = sqlite3.connect(db_path)
    return conn

def listen_and_store_kline(symbol: str, interval: str, market_type: str = "futures"):
    fetcher = OKXKlineFetcher(market_type=market_type)
    last_timestamp = None
    while True:
        klines = fetch_futures_klines(symbol=symbol, interval=interval, limit=1)
        df = pd.DataFrame(klines, columns=["timestamp", "open_price", "high_price", "low_price", "close_price", "volume"])
        df.rename(columns={
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "volume": "volume",
        }, inplace=True)
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

def create_kline_table(symbol: str, interval: str, db_path: str = "datawarehouse/kline.db"):
    table = f"kline_{symbol.replace('-', '_')}_{interval}"
    conn = get_db_conn(db_path)
    c = conn.cursor()
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            timestamp TEXT PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL
        )
    """)
    conn.commit()
    conn.close()

def insert_kline(symbol: str, interval: str, kline: Dict[str, Any], db_path: str = "datawarehouse/kline.db"):
    table = f"kline_{symbol.replace('-', '_')}_{interval}"
    create_kline_table(symbol, interval, db_path)
    conn = get_db_conn(db_path)
    c = conn.cursor()
    c.execute(f"""
        INSERT OR REPLACE INTO {table} (timestamp, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        kline['timestamp'], kline['open'], kline['high'], kline['low'], kline['close'], kline['volume']
    ))
    conn.commit()
    conn.close()

def fetch_klines_from_db(symbol: str, interval: str, window: int, db_path: str = "datawarehouse/kline.db") -> pd.DataFrame:
    table = f"kline_{symbol.replace('-', '_')}_{interval}"
    create_kline_table(symbol, interval, db_path)
    conn = get_db_conn(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY timestamp DESC LIMIT ?", conn, params=(window,))
    conn.close()
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df

def fetch_multi_interval_closes_from_db(symbol: str, intervals: list, window: int, db_path: str = "datawarehouse/kline.db") -> pd.DataFrame:
    dfs = {}
    for interval in intervals:
        df = fetch_klines_from_db(symbol, interval, window)
        df = df[["timestamp", "close"]].copy()
        df = df.rename(columns={"close": f"close_{interval}"})
        dfs[interval] = df
    # 以最小頻率為主做 merge
    main_interval = intervals[0]
    result = dfs[main_interval]
    for interval in intervals[1:]:
        result = pd.merge_asof(result.sort_values("timestamp"),
                              dfs[interval].sort_values("timestamp"),
                              on="timestamp", direction="backward")
    result = result.reset_index(drop=True)
    return result

if __name__ == "__main__":
    df = fetch_klines_from_db('BTC-USDT', '1m', 10)
    print(df)
