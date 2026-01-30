import os
import sys
from typing import Dict, Any, List

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.backtest.backtest import Backtester
from strategy.longstrategy import LongStrategy
from strategy.shortstrategy import ShortStrategy


def _prepare_df(csv_file) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    if 'timestamp' not in df.columns and 'ts' in df.columns:
        df = df.rename(columns={'ts': 'timestamp'})
    if 'timestamp' not in df.columns:
        raise ValueError("CSV 必須包含 timestamp 或 ts 欄位")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def _build_equity_curve(equity_curve: List[Dict[str, Any]], initial_amount: float = 500.0):
    if not equity_curve:
        return None
    
    timestamps = [ec['timestamp'] for ec in equity_curve]
    total_pnls = [ec['total_pnl'] / initial_amount * 100 for ec in equity_curve]
    realized_pnls = [ec['realized_pnl'] / initial_amount * 100 for ec in equity_curve]
    unrealized_pnls = [ec['unrealized_pnl'] / initial_amount * 100 for ec in equity_curve]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(timestamps, total_pnls, label='Total PnL', linewidth=1.5, alpha=0.9)
    ax.plot(timestamps, realized_pnls, label='Realized PnL', linewidth=1, alpha=0.6, linestyle='--')
    ax.plot(timestamps, unrealized_pnls, label='Unrealized PnL', linewidth=1, alpha=0.6, linestyle=':')
    ax.set_xlabel('Time')
    ax.set_ylabel('PnL (%)')
    ax.set_title('Equity Curve')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()
    return fig


def _run_backtest(df_1m: pd.DataFrame, strategy_name: str, base_qty: float, leverage: float):
    if strategy_name == "LongStrategy":
        strategy = LongStrategy(fast=12, slow=26, signal=9)
    else:
        strategy = ShortStrategy(fast=12, slow=26, signal=9)

    backtester = Backtester(df_1m, strategy)
    backtester.run_dynamic(base_qty=base_qty, leverage=leverage)
    perf = backtester.performance()
    return backtester, perf


def main():
    st.set_page_config(page_title="Backtest UI", layout="wide")
    st.title("回測介面")

    with st.sidebar:
        st.header("參數設定")
        csv_file = st.file_uploader("上傳 CSV", type=["csv"])
        strategy_name = st.selectbox("策略", ["LongStrategy", "ShortStrategy"])
        symbol = st.text_input("Symbol", value="BTC-USDT")
        initial_amount = st.number_input("Initial Amount", min_value=100.0, value=500.0, step=50.0) 
        # window_1m = st.number_input("Window (1m)", min_value=6000, value=6000, step=100)
        base_qty = st.number_input("Base Qty", min_value=0.1, value=1.0, step=0.1)
        leverage = st.number_input("Leverage", min_value=1.0, value=1.0, step=0.5)
        run_btn = st.button("執行回測", type="primary", use_container_width=True)

    if run_btn:
        if csv_file is None:
            st.error("請先上傳 CSV")
            return

        with st.spinner("回測中..."):
            df_1m = _prepare_df(csv_file)
            backtester, perf = _run_backtest(df_1m, strategy_name, float(base_qty), float(leverage))
            perf = backtester.performance(initial_amount=float(initial_amount))

        st.subheader("績效指標")
        perf_cols = st.columns(4)
        perf_items = list(perf.items())
        for i, (k, v) in enumerate(perf_items):
            col = perf_cols[i % 4]
            if isinstance(v, float):
                col.metric(k, f"{v:.4f}")
            else:
                col.metric(k, str(v))

        st.subheader("績效曲線")
        fig = _build_equity_curve(backtester.equity_curve, initial_amount=float(initial_amount))
        if fig is None:
            st.warning("沒有權益曲線數據，無法繪圖")
        else:
            st.pyplot(fig, use_container_width=True)

        st.subheader("交易紀錄")
        st.dataframe(pd.DataFrame(backtester.trade_records))
        
        st.subheader("分鐘級損益數據（前100筆）")
        st.dataframe(pd.DataFrame(backtester.equity_curve).head(100))


if __name__ == "__main__":
    main()
