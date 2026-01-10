import time
import ccxt
import pandas as pd

def fetch_ohlcv_paginated(
    exchange,
    symbol: str,
    timeframe: str = "15m",
    since_ms: int | None = None,
    until_ms: int | None = None,
    limit: int = 300,
    max_candles: int = 50000,
):
    all_rows = []
    tf_ms = exchange.parse_timeframe(timeframe) * 1000

    if since_ms is None:
        raise ValueError("建議一定要傳 since_ms 否則回傳範圍看交易所預設。")

    cursor = since_ms

    while True:
        if until_ms is not None and cursor >= until_ms:
            break
        if len(all_rows) >= max_candles:
            break

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)

        if not ohlcv:
            break

        all_rows.extend(ohlcv)

        last_ts = ohlcv[-1][0]
        next_cursor = last_ts + tf_ms

        if next_cursor <= cursor:
            break

        cursor = next_cursor
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


if __name__ == "__main__":
    ex = ccxt.okx({
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",
        },
    })

    ex.load_markets()

    symbol = "BTC/USDT:USDT"
    if symbol not in ex.markets:
        raise ValueError(f"Symbol not found in markets: {symbol}. 你可印 ex.symbols 找正確 symbol。")

    now = ex.milliseconds()
    since = now - 90 * 24 * 60 * 60 * 1000

    df = fetch_ohlcv_paginated(
        exchange=ex,
        symbol=symbol,
        timeframe="1m",
        since_ms=since,
        until_ms=None,
        limit=300,
        max_candles=50000,
    )

    df.to_csv("data/BTC_USDT_1m_okx_swap.csv", index=False)
