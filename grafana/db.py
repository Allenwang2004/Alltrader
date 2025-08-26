import time
import psycopg2
from binance.client import Client
import os
import dotenv

dotenv.load_dotenv()  # 載入 .env

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# PostgreSQL 連線設定
DB_CONFIG = {
    "host": "localhost",
    "dbname": "grafana",
    "user": "grafana",
    "password": "0321",
    "port": 5434
}

# 建立 Binance Client
client = Client(api_key, api_secret)


def create_table():
    """建立資料表 (只需跑一次)"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS binance_assets (
        id SERIAL PRIMARY KEY,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        spot_balance NUMERIC,
        futures_balance NUMERIC
    );
    """)
    conn.commit()
    cur.close()
    conn.close()


def insert_assets(spot, futures):
    """插入資產數據"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO binance_assets (spot_balance, futures_balance) VALUES (%s, %s)",
        (spot, futures)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_spot_balance():
    """抓取現貨資產總值 (折合 USDT)"""
    account_info = client.get_account()
    total_usdt = 0.0

    for balance in account_info['balances']:
        asset = balance['asset']
        amount = float(balance['free']) + float(balance['locked'])

        if amount == 0:
            continue

        if asset == "USDT":
            total_usdt += amount
        else:
            # 嘗試用 <Asset>USDT 交易對換算
            symbol = f"{asset}USDT"
            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                price = float(ticker["price"])
                total_usdt += amount * price
            except Exception:
                # 如果沒有 USDT 交易對 (例如 BETH)，就跳過
                pass

    return total_usdt


def get_futures_balance():
    """抓取合約總資產 (USDT)"""
    account_info = client.futures_account()
    return float(account_info['totalWalletBalance'])


if __name__ == "__main__":
    create_table()
    while True:
        try:
            spot = get_spot_balance()
            futures = get_futures_balance()
            insert_assets(spot, futures)
            print(f"[OK] Inserted Spot={spot:.2f} USDT, Futures={futures:.2f} USDT")
        except Exception as e:
            print("Error:", e)
        time.sleep(30)  # 每 30 秒更新一次