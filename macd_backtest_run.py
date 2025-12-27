import pandas as pd
from connector.okx_kline import OKXKlineFetcher
from strategy.simple_entry_exit_strategy import SimpleEntryExitStrategy
from engine.backtest.backtest import Backtester

def run_macd_backtest(symbol: str, interval: str = "1H", market_type: str = "futures", limit: int = 300):
    fetcher = OKXKlineFetcher(market_type=market_type)
    # 取得 K 線資料
    klines = fetcher.fetch_klines(symbol=symbol, interval=interval, limit=limit)
    # 假設回傳為 list of list: [timestamp, open, high, low, close, volume, ...]
    df = pd.DataFrame(klines, columns=["timestamp", "open_price", "high_price", "low_price", "close_price", "volume", "turnover"])
    df['close'] = df['close_price'].astype(float)
    # 建立 MACD 策略
    strategy = SimpleEntryExitStrategy()
    # 回測
    backtester = Backtester(df, strategy)
    backtester.run()
    perf = backtester.performance()
    print("回測績效:")
    for k, v in perf.items():
        print(f"{k}: {v}")
    return perf

if __name__ == "__main__":
    run_macd_backtest("BTC-USDT", interval="1m", market_type="futures", limit=300)
