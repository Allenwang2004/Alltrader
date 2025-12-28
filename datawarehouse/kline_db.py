import sqlite3
import pandas as pd
from typing import Dict, Any

def get_db_conn(db_path: str = "datawarehouse/kline.db"):
    conn = sqlite3.connect(db_path)
    return conn

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
            volume REAL,
            turnover REAL
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
        INSERT OR REPLACE INTO {table} (timestamp, open, high, low, close, volume, turnover)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        kline['timestamp'], kline['open'], kline['high'], kline['low'], kline['close'], kline['volume'], kline['turnover']
    ))
    conn.commit()
    conn.close()

def fetch_klines_from_db(symbol: str, interval: str, window: int, db_path: str = "datawarehouse/kline.db") -> pd.DataFrame:
    table = f"kline_{symbol.replace('-', '_')}_{interval}"
    conn = get_db_conn(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY timestamp DESC LIMIT ?", conn, params=(window,))
    conn.close()
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df
