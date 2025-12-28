import pandas as pd
from engine.backtest.backtest import Strategy

class SimpleEntryExitStrategy(Strategy):
    def __init__(self):
        self.strategy_name = "SimpleEntryExit"
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        up = (df['close'] > df['close'].shift(1)) & (df['close'].shift(1) > df['close'].shift(2))
        down = (df['close'] < df['close'].shift(1)) & (df['close'].shift(1) < df['close'].shift(2))
        signal = pd.Series(0, index=df.index)
        signal[up] = 1
        signal[down] = -1
        return signal
