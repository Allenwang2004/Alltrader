import pandas as pd
from typing import Any, Dict
from engine.online.rms import RiskManager

class Strategy:
    def generate_signals(self, *dfs: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

class Backtester:
    def __init__(self, df_1m: pd.DataFrame, strategy: Strategy, fee: float = 0.0005):
        self.df_1m = df_1m.copy()
        self.strategy = strategy
        self.fee = fee
        self.results = None
        self.trade_records = []

    def run_dynamic(self, window_1m: int = 6000, step: int = 60, base_qty: float = 1) -> list:
        self.trade_records = []
        df_1m = self.df_1m
        start = 0
        while start + window_1m <= len(df_1m):
            sub_1m = df_1m.iloc[start:start + window_1m]
            df_1h = sub_1m.set_index('timestamp').resample('1h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna().reset_index()
            df_1h.to_csv("data/debug_1h.csv", index=False)
            df_15m = sub_1m.set_index('timestamp').resample('15min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna().reset_index()
            df_15m.to_csv("data/debug_15m.csv", index=False)
            signal_df_15m = df_15m.iloc[-100:] if len(df_15m) >= 100 else df_15m
            signals = self.strategy.generate_signals(signal_df_15m, df_1h)
            if signals in [1, -1]:
                position = signals
                entry_price = signal_df_15m['close'].iloc[-1]
                risk_manager = RiskManager()
                risk_manager.reset()
                risk_manager.add_position(entry_price, base_qty)
                current_idx = start + window_1m
                while current_idx < len(df_1m):
                    current_price = df_1m['close'].iloc[current_idx]
                    if risk_manager.should_add_position(entry_price, current_price, position):
                        qty = risk_manager.add_position(current_price, base_qty)
                        if qty is None:
                            break
                    if risk_manager.check_take_profit(current_price, position):
                        exit_price = current_price
                        total_qty = sum(p['qty'] for p in risk_manager.positions)
                        avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / total_qty
                        pnl = (exit_price - avg_entry) / avg_entry * position * total_qty
                        pnl -= self.fee * total_qty
                        self.trade_records.append({
                            'entry_idx': current_idx - (start + window_1m),
                            'exit_idx': current_idx,
                            'pnl': pnl,
                            'position': position
                        })
                        break
                    current_idx += 1
                else:
                    # 強平
                    exit_price = df_1m['close'].iloc[-1]
                    total_qty = sum(p['qty'] for p in risk_manager.positions)
                    avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / total_qty
                    pnl = (exit_price - avg_entry) / avg_entry * position * total_qty
                    pnl -= self.fee * total_qty
                    self.trade_records.append({
                        'entry_idx': current_idx - (start + window_1m),
                        'exit_idx': len(df_1m) - 1,
                        'pnl': pnl,
                        'position': position
                    })
            start += step
        return self.trade_records

    def performance(self) -> Dict[str, Any]:
        if self.trade_records:
            if not self.trade_records:
                return {'總報酬': 0, '年化報酬': 0, '最大回撤': 0, 'Sharpe Ratio': float('nan'), '交易次數': 0, '勝率': float('nan'), '平均單次盈虧': float('nan'), '最大單次獲利': float('nan'), '最大單次虧損': float('nan')}
            pnls = [t['pnl'] for t in self.trade_records]
            equity = [1]
            for pnl in pnls:
                equity.append(equity[-1] * (1 + pnl))
            total_return = equity[-1] - 1
            periods = len(self.df_1m) / 252
            annualized_return = (equity[-1]) ** (1 / periods) - 1 if periods > 0 else 0
            max_drawdown = ((pd.Series(equity).cummax() - pd.Series(equity)) / pd.Series(equity).cummax()).max()
            std = pd.Series(pnls).std()
            sharpe = pd.Series(pnls).mean() / std * (252 ** 0.5) if std > 0 else float('nan')
            trades = len(pnls)
            win_trades = sum(1 for p in pnls if p > 0)
            lose_trades = sum(1 for p in pnls if p < 0)
            win_rate = win_trades / trades if trades > 0 else float('nan')
            avg_pnl = sum(pnls) / trades if trades > 0 else float('nan')
            max_win = max(pnls) if pnls else float('nan')
            max_loss = min(pnls) if pnls else float('nan')
        else:
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

            trades = (self.results['position'].diff().abs() > 0).sum()

            trade_pnl = self.results.loc[self.results['position'].diff().abs() > 0, 'strategy_ret']

            win_trades = (trade_pnl > 0).sum()
            lose_trades = (trade_pnl < 0).sum()
            win_rate = win_trades / trades if trades > 0 else float('nan')

            avg_pnl = trade_pnl.mean() if trades > 0 else float('nan')

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
