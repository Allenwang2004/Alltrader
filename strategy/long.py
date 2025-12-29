import pandas as pd
from engine.backtest.backtest import Strategy

class LongStrategy(Strategy):
    def __init__(self, fast=12, slow=26, signal=9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.strategy_name = "MACD_1h_15m_EMA_long"

    def generate_signals(self, df_1h: pd.DataFrame, df_15m: pd.DataFrame) -> pd.Series:
        if 'close' not in df_1h or 'close' not in df_15m:
            raise ValueError("DataFrame 必須包含 'close' 及 'close' 欄位")

        ema_fast_1h = df_1h['close'].ewm(span=self.fast, adjust=False).mean()
        ema_slow_1h = df_1h['close'].ewm(span=self.slow, adjust=False).mean()
        macd_1h = ema_fast_1h - ema_slow_1h
        macd_cond = macd_1h > 0

        c15 = df_15m['close']
        pattern = (c15.shift(3) > c15.shift(2)) & (c15.shift(2) > c15.shift(1)) & (c15.shift(1) < c15)

        ema4_15m = c15.ewm(span=4, adjust=False).mean()
        ema16_15m = c15.ewm(span=16, adjust=False).mean()
        ema_cond = ema4_15m > ema16_15m

        entry = macd_cond & pattern & ema_cond
        signal = entry.astype(int)
        return signal
