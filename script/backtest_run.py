import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
from connector.okx_kline import OKXKlineFetcher
from strategy.longstrategy import LongStrategy
from strategy.shortstrategy import ShortStrategy
from engine.backtest.backtest import Backtester
from engine.backtest.rms import RiskManager

def run_macd_backtest(csv_path: str = "data/BTC_USDT_1m_okx_swap.csv", window_1m: int = 6000, initial_amount: float = 500, base_qty: float = 1, leverage: float = 1, symbol="BTC-USDT"):
    df_1m = pd.read_csv(csv_path)
    df_1m['ts'] = pd.to_datetime(df_1m['ts'])
    df_1m = df_1m.rename(columns={'ts': 'timestamp'})
    
    strategy = LongStrategy(fast=12, slow=26, signal=9)
    backtester = Backtester(df_1m, strategy)
    backtester.run_dynamic(window_1m=window_1m, base_qty=base_qty, leverage=leverage)
    perf = backtester.performance(initial_amount=initial_amount)
    backtester.plot_equity_curve(initial_amount=initial_amount, base_qty=base_qty, leverage=leverage, symbol=symbol)
    print("回測績效:")
    for k, v in perf.items():
        print(f"{k}: {v}")
    return perf

if __name__ == "__main__":
    run_macd_backtest()