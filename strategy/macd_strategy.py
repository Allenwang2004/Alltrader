import pandas as pd
from engine.backtest.backtest import Strategy

class MACDStrategy(Strategy):
    def __init__(self, fast=12, slow=26, signal=9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        ema_fast = df['close'].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()
        df['macd'] = macd
        df['signal_line'] = signal_line
        signal = (macd > signal_line).astype(int) - (macd < signal_line).astype(int)
        return signal
