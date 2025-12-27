import pandas as pd
from engine.backtest.backtest import Strategy

class SimpleEntryExitStrategy(Strategy):
    """
    只要連續兩根收盤價上升就做多，連續兩根下降就做空，否則空倉。
    確保有明確進場與出場訊號。
    """
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        up = (df['close'] > df['close'].shift(1)) & (df['close'].shift(1) > df['close'].shift(2))
        down = (df['close'] < df['close'].shift(1)) & (df['close'].shift(1) < df['close'].shift(2))
        signal = pd.Series(0, index=df.index)
        signal[up] = 1
        signal[down] = -1
        return signal
