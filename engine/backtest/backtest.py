import pandas as pd
from typing import Any, Dict
from engine.backtest.rms import RiskManager
import matplotlib.pyplot as plt

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
        self.equity_curve = []

    def run_dynamic(self, window_1m: int = 6000, base_qty: float = 1, leverage: float = 1) -> list:
        self.trade_records = []
        self.equity_curve = []
        df_1m = self.df_1m
        if len(df_1m) < 6000:
            raise ValueError("需要至少6000根1min數據")

        initial_1m = df_1m.iloc[:6000]
        df_1h = initial_1m.set_index('timestamp').resample('1h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna().reset_index()
        df_15m = initial_1m.set_index('timestamp').resample('15min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna().reset_index()
        if len(df_15m) > 100:
            df_15m = df_15m.iloc[-100:]
        signal_df_15m = df_15m
        current_signal = self.strategy.generate_signals(signal_df_15m, df_1h)

        current_15m_data = []
        current_1h_data = []

        current_idx = 6000
        current_position = 0
        risk_manager = None
        entry_price = None
        realized_pnl = 0.0

        # Add equity curve for initial 6000 bars (no position)
        for i in range(6000):
            self.equity_curve.append({
                'timestamp': df_1m.iloc[i]['timestamp'],
                'idx': i,
                'realized_pnl': 0.0,
                'unrealized_pnl': 0.0,
                'total_pnl': 0.0
            })

        while current_idx < len(df_1m):
            new_1m = df_1m.iloc[current_idx]
            current_15m_data.append(new_1m)
            current_1h_data.append(new_1m)

            if len(current_15m_data) == 15:
                new_15m = {
                    'timestamp': pd.to_datetime(current_15m_data[0]['timestamp']),
                    'open': current_15m_data[0]['open'],
                    'high': max(d['high'] for d in current_15m_data),
                    'low': min(d['low'] for d in current_15m_data),
                    'close': current_15m_data[-1]['close'],
                    'volume': sum(d['volume'] for d in current_15m_data)
                }
                df_15m = pd.concat([df_15m, pd.DataFrame([new_15m])], ignore_index=True)
                if len(df_15m) > 100:
                    df_15m = df_15m.iloc[1:].reset_index(drop=True)
                signal_df_15m = df_15m
                current_15m_data = []
                current_signal = self.strategy.generate_signals(signal_df_15m, df_1h)

            if len(current_1h_data) == 60:
                new_1h = {
                    'timestamp': pd.to_datetime(current_1h_data[0]['timestamp']),
                    'open': current_1h_data[0]['open'],
                    'high': max(d['high'] for d in current_1h_data),
                    'low': min(d['low'] for d in current_1h_data),
                    'close': current_1h_data[-1]['close'],
                    'volume': sum(d['volume'] for d in current_1h_data)
                }
                df_1h = pd.concat([df_1h, pd.DataFrame([new_1h])], ignore_index=True)
                if len(df_1h) > 100:
                    df_1h = df_1h.iloc[1:].reset_index(drop=True)
                current_1h_data = []
                current_signal = self.strategy.generate_signals(signal_df_15m, df_1h)

            if current_position == 0 and current_signal != 0:
                print("進場:", current_signal, "價格:", signal_df_15m['close'].iloc[-1], "時間:", signal_df_15m['timestamp'].iloc[-1])
                current_position = current_signal
                entry_price = signal_df_15m['close'].iloc[-1]
                entry_idx = current_idx
                risk_manager = RiskManager()
                risk_manager.reset()
                risk_manager.add_position(entry_price, base_qty)

            elif current_position != 0:
                current_price = new_1m['close']
                # check whether liquidation
                check_liquidation = False
                exit_price = current_price
                avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / sum(p['qty'] for p in risk_manager.positions)
                if current_position == 1:
                    if exit_price <= avg_entry * (1 - 1 / leverage):
                        check_liquidation = True
                else:
                    if exit_price >= avg_entry * (1 + 1 / leverage):
                        check_liquidation = True
                if check_liquidation:
                    print("強平出場:", current_position, "價格:", exit_price, "時間:", new_1m['timestamp'])
                    total_qty = sum(p['qty'] for p in risk_manager.positions)
                    # 強平損失 = 倉位價值 * leverage (100%虧損)
                    pnl = -total_qty * leverage
                    # pnl -= pnl* self.fee
                    self.trade_records.append({
                        'average_entry': avg_entry,
                        'exit_price': exit_price,
                        'total_qty': total_qty,
                        'pnl': pnl,
                        'position': current_position,
                        'exit_idx': current_idx,
                    })
                    realized_pnl += pnl
                    current_position = 0
                    risk_manager = None
                    entry_price = None
                elif risk_manager.should_add_position(entry_price, current_price, current_position):
                    qty = risk_manager.add_position(current_price, base_qty)
                    print("加倉:", current_position, "價格:", current_price, "時間:", new_1m['timestamp'], "加倉量:", qty, "reverse_pct:", (current_price - entry_price) / entry_price)
                    # entry_price = new_1m['close']
                    if qty is None:
                        print("已達最大加倉層數，無法再加倉")
                        exit_price = current_price
                        total_qty = sum(p['qty'] for p in risk_manager.positions)
                        avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / total_qty
                        pnl = (exit_price - avg_entry) / avg_entry * current_position * total_qty * leverage
                        # pnl -= pnl* self.fee
                        self.trade_records.append({
                            'average_entry': avg_entry,
                            'exit_price': exit_price,
                            'total_qty': total_qty,
                            'pnl': pnl,
                            'position': current_position,
                            'exit_idx': current_idx,
                        })
                        realized_pnl += pnl
                        current_position = 0
                        risk_manager = None
                        entry_price = None
                elif risk_manager and risk_manager.check_take_profit(current_price, current_position):
                    exit_price = current_price
                    print("出場:", current_position, "價格:", exit_price, "時間:", new_1m['timestamp'])
                    total_qty = sum(p['qty'] for p in risk_manager.positions)
                    # print("total_qty:", total_qty)
                    avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / total_qty
                    pnl = (exit_price - avg_entry) / avg_entry * current_position * total_qty * leverage
                    # pnl -= pnl* self.fee
                    self.trade_records.append({
                        'average_entry': avg_entry,
                        'exit_price': exit_price,
                        'total_qty': total_qty,
                        'pnl': pnl,
                        'position': current_position,
                        'exit_idx': current_idx,
                    })
                    realized_pnl += pnl
                    current_position = 0
                    risk_manager = None
                    entry_price = None

            # Record equity curve for this minute
            unrealized_pnl = 0.0
            if current_position != 0 and risk_manager is not None:
                current_price = new_1m['close']
                total_qty = sum(p['qty'] for p in risk_manager.positions)
                avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / total_qty
                unrealized_pnl = (current_price - avg_entry) / avg_entry * current_position * total_qty * leverage
            
            self.equity_curve.append({
                'timestamp': new_1m['timestamp'],
                'idx': current_idx,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': realized_pnl + unrealized_pnl
            })

            current_idx += 1

        # 循環結束後，如果還有倉位，強平
        if current_position != 0:
            exit_price = df_1m['close'].iloc[-1]
            total_qty = sum(p['qty'] for p in risk_manager.positions)
            avg_entry = sum(p['price'] * p['qty'] for p in risk_manager.positions) / total_qty
            pnl = (exit_price - avg_entry) / avg_entry * current_position * total_qty * leverage
            # pnl -= pnl* self.fee
            self.trade_records.append({
                'average_entry': avg_entry,
                'exit_price': exit_price,
                'total_qty': total_qty,
                'pnl': pnl,
                'position': current_position,
                'exit_idx': len(df_1m) - 1,
            })
            realized_pnl += pnl

        # save trade records into csv
        trade_df = pd.DataFrame(self.trade_records)
        trade_df.to_csv('output/trade_records.csv', index=False)
        return self.trade_records

    def performance(self, initial_amount: float = 500.0, **kwargs) -> Dict[str, Any]:
        if self.trade_records:
            if not self.trade_records:
                return {'總報酬': 0, '年化報酬': 0, '最大回撤': 0, 'Sharpe Ratio': float('nan'), '交易次數': 0, '勝率': float('nan'), '平均單次盈虧': float('nan'), '最大單次獲利': float('nan'), '最大單次虧損': float('nan')}

            pnls = [t['pnl'] for t in self.trade_records]
            trades = len(pnls)
            win_trades = sum(1 for p in pnls if p > 0)
            lose_trades = sum(1 for p in pnls if p < 0)
            win_rate = win_trades / trades if trades > 0 else float('nan')
            avg_pnl = sum(pnls) / trades if trades > 0 else float('nan')
            max_win = max(pnls) if pnls else float('nan')
            max_loss = min(pnls) if pnls else float('nan')

            if self.equity_curve:
                equity_df = pd.DataFrame(self.equity_curve)
                equity_value = initial_amount + equity_df['total_pnl']
                total_return = equity_value.iloc[-1] - initial_amount

                duration_years = (equity_df['timestamp'].iloc[-1] - equity_df['timestamp'].iloc[0]).total_seconds() / (365 * 24 * 3600)
                annualized_return = (equity_value.iloc[-1] / initial_amount) ** (1 / duration_years) - 1 if duration_years > 0 else float('nan')

                max_drawdown = ((equity_value.cummax() - equity_value) / equity_value.cummax()).max()

                returns = equity_value.pct_change().dropna()
                std = returns.std()
                periods_per_year = 365 * 24 * 60
                sharpe = returns.mean() / std * (periods_per_year ** 0.5) if std > 0 else float('nan')
            else:
                equity = [0]
                for pnl in pnls:
                    equity.append(equity[-1] + pnl)
                total_return = equity[-1]
                annualized_return = float('nan')
                equity_series = pd.Series(equity)
                max_drawdown = (equity_series.cummax() - equity_series).max()
                std = pd.Series(pnls).std()
                sharpe = pd.Series(pnls).mean() / std if std > 0 else float('nan')
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

    def plot_equity_curve(self, initial_amount: float = 1000, base_qty: float = 1, leverage: float = 1, symbol: str = "BTC-USDT", filename: str = "output/equity_curve.png"):
        if not self.equity_curve:
            print("沒有權益曲線數據，無法繪圖")
            return
        
        timestamps = [ec['timestamp'] for ec in self.equity_curve]
        total_pnls = [ec['total_pnl'] / initial_amount * 100 for ec in self.equity_curve]
        
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, total_pnls, label='Total PnL', linewidth=1)
        plt.title(f'Equity Curve - {symbol} (Leverage: {leverage}x, Base Qty: {base_qty})')
        plt.xlabel('Time')
        plt.ylabel('PnL (%)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        print(f"Equity curve 已保存為 {filename}")
