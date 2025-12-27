import time
import pandas as pd
from typing import Type
from connector.okx_order import OKXOrderClient
from connector.okx_kline import OKXKlineFetcher

def run_live_trading(strategy_cls: Type, api_key: str, api_secret: str, passphrase: str, symbol: str, interval: str = "1m", market_type: str = "futures", window: int = 100):
    okx_client = OKXOrderClient(api_key, api_secret, passphrase)
    kline_fetcher = OKXKlineFetcher(market_type=market_type)
    position = 0
    print("開始實盤交易 (僅示範訊號與下單流程)...")
    while True:
        klines = kline_fetcher.fetch_klines(symbol=symbol, interval=interval, limit=window)
        df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
        df['close'] = df['close'].astype(float)
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
        time.sleep(60)  # 每分鐘輪詢一次

if __name__ == "__main__":
    # 範例: 實盤用 SimpleEntryExitStrategy
    from strategy.simple_entry_exit_strategy import SimpleEntryExitStrategy
    run_live_trading(
        strategy_cls=SimpleEntryExitStrategy,
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
        passphrase="YOUR_PASSPHRASE",
        symbol="BTC-USDT-SWAP",
        interval="1m",
        market_type="futures",
        window=100
    )
