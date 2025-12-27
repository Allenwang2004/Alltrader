import pandas as pd
from typing import Any, Dict

class Strategy:
    """
    策略基底類別，所有自訂策略需繼承並實作 generate_signals 方法。
    """
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        根據 dataframe 產生交易信號。
        必須回傳一個與 df 同長度的 pd.Series，內容為 1(做多)、-1(做空)、0(空倉)。
        """
        raise NotImplementedError

class Backtester:
    def __init__(self, df: pd.DataFrame, strategy: Strategy, fee: float = 0.0005):
        self.df = df.copy()
        self.strategy = strategy
        self.fee = fee
        self.results = None

    def run(self) -> pd.DataFrame:
        signals = self.strategy.generate_signals(self.df)
        self.df['signal'] = signals
        self.df['position'] = self.df['signal'].shift().fillna(0)
        self.df['ret'] = self.df['close'].pct_change(fill_method=None).fillna(0)
        self.df['strategy_ret'] = self.df['position'] * self.df['ret']
        self.df['strategy_ret'] -= abs(self.df['position'].diff().fillna(0)) * self.fee
        self.df['equity_curve'] = (1 + self.df['strategy_ret']).cumprod()
        self.results = self.df
        return self.df

    def performance(self) -> Dict[str, Any]:
        if self.results is None:
            raise ValueError('請先執行 run()')
        total_return = self.results['equity_curve'].iloc[-1] - 1
        annualized_return = (self.results['equity_curve'].iloc[-1]) ** (252/len(self.results)) - 1
        max_drawdown = ((self.results['equity_curve'].cummax() - self.results['equity_curve']) / self.results['equity_curve'].cummax()).max()
        std = self.results['strategy_ret'].std()
        if std == 0 or pd.isna(std):
            sharpe = float('nan')
        else:
            sharpe = self.results['strategy_ret'].mean() / std * (252 ** 0.5)

        # 交易次數（訊號變化次數）
        trades = (self.results['position'].diff().abs() > 0).sum()
        # 每次交易的損益
        trade_pnl = self.results.loc[self.results['position'].diff().abs() > 0, 'strategy_ret']
        # 勝率
        win_trades = (trade_pnl > 0).sum()
        lose_trades = (trade_pnl < 0).sum()
        win_rate = win_trades / trades if trades > 0 else float('nan')
        # 平均單次盈虧
        avg_pnl = trade_pnl.mean() if trades > 0 else float('nan')
        # 最大單次獲利/虧損
        max_win = trade_pnl.max() if trades > 0 else float('nan')
        max_loss = trade_pnl.min() if trades > 0 else float('nan')

        return {
            '總報酬': total_return,
            '年化報酬': annualized_return,
            '最大回撤': max_drawdown,
            'Sharpe Ratio': sharpe,
            '交易次數': trades,
            '勝率': win_rate,
            '平均單次盈虧': avg_pnl,
            '最大單次獲利': max_win,
            '最大單次虧損': max_loss
        }
