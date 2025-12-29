from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static, Input, Select
import importlib
import os
import time
from utils.strategy_utils import get_strategy_classes
from textual.containers import Container, Horizontal
from connector.okx_order import OKXOrderClient
from connector import binance_order
import threading
from connector.okx_kline import OKXKlineFetcher
from datawarehouse.kline_db import insert_kline
from engine.trader import trading_main
import pandas as pd

class LogPanel(Static):
    def __init__(self, text: str = "", max_lines: int = 200, **kwargs):
        super().__init__(text, **kwargs)
        self.max_lines = max_lines
        self._lines: list[str] = []
        if text:
            self._lines.append(text)

    def write(self, text: str):
        # 支援多行輸入
        for line in str(text).splitlines():
            self._lines.append(line)

        # 限制最大行數，避免無限成長
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines :]

        # 重新 render（append 效果）
        self.update("\n".join(self._lines))

class MainMenu(Static):
    def compose(self) -> ComposeResult:
        yield Button("Account Info", id="account")
        yield Button("Select Strategy", id="strategy")
        yield Button("Record Symbol", id="record_symbol")
        yield Button("Exit", id="exit")

class RecordSymbolPanel(Static):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Symbol (like BTC-USDT)", id="symbol_input")
        yield Input(placeholder="Interval (like 1m, 5m, 1H)", id="interval_input")
        yield Button("Start Recording", id="start_recording")

class StrategySelect(Static):
    def compose(self) -> ComposeResult:
        # 動態取得策略清單
        strategies = get_strategy_classes()
        options = [(sname, cname) for cname, sname in strategies]
        yield Input(placeholder="Symbol (如 BTC-USDT)", id="symbol_input")
        yield Select(options=options, prompt="Select Strategy", id="strategy_select")
        yield Button("Confirm Strategy", id="confirm_strategy")

class ExchangeSelect(Static):
    def compose(self) -> ComposeResult:
        yield Select(options=[("Binance", "binance"), ("OKX", "okx")], prompt="Select Exchange", id="exchange_select")
        yield Input(placeholder="API Key", id="api_key")
        yield Input(placeholder="API Secret", id="api_secret")
        yield Input(placeholder="OKX Passphrase (OKX)", id="passphrase")
        yield Button("Confirm", id="confirm")

class AccountInfo(Static):
    def __init__(self, info, exchange, **kwargs):
        super().__init__(**kwargs)
        self.info = info
        self.exchange = exchange
    def render(self):
        if self.exchange == "okx":
            if not self.info or 'data' not in self.info or not self.info['data']:
                return "查無帳戶資料。"
            data = self.info['data'][0]
            return f"""
==== OKX Account Info ====
Total Assets: {data.get('totalEq', 'N/A')}
Margin Assets: {data.get('isoEq', 'N/A')}
Margin Ratio: {data.get('mgnRatio', 'N/A')}
Refreshed At: {data.get('uTime', 'N/A')}
====================
"""
        elif self.exchange == "binance":
            if not self.info:
                return "查無帳戶資料。"
            return "\n".join([f"{k}: {v}" for k, v in self.info.items()])
        return "不支援的交易所"

class TradeApp(App):
    CSS_PATH = None
    BINDINGS = [ ("q", "quit", "離開") ]

    def __init__(self):
        super().__init__()
        self.exchange = None
        self.api_key = None
        self.api_secret = None
        self.passphrase = None
        self.okx_client = None
        self.binance_client = None
        self.account_info = None
        self.strategy_class = None
        self.strategy_name = None
        self.trading_thread = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Container(ExchangeSelect(), id="left"),
            Container(LogPanel("Log output..."), id="right"),
            id="main_layout"
        )
        yield Footer()

    def on_button_pressed(self, event):
        btn_id = event.button.id
        if btn_id == "account":
            self.query_account()
        elif btn_id == "strategy":
            self.select_strategy()
        elif btn_id == "record_symbol":
            self.record_symbol_panel()
        elif btn_id == "switch":
            self.switch_exchange()
        elif btn_id == "rekey":
            self.rekey()
        elif btn_id == "exit":
            self.exit()
        elif btn_id == "confirm":
            self.confirm_exchange()
        elif btn_id == "confirm_strategy":
            self.confirm_strategy()
        elif btn_id == "start_recording":
            self.start_recording_symbol()

    def record_symbol_panel(self):
        left = self.query_one("#left")
        left.remove_children()
        left.mount(RecordSymbolPanel())

    def start_recording_symbol(self):
        symbol = self.query_one("#symbol_input", Input).value.strip()
        interval = self.query_one("#interval_input", Input).value.strip()
        log = self.query_one(LogPanel)
        if not symbol or not interval:
            log.write("請輸入 symbol 與 interval")
            return
        fetcher = OKXKlineFetcher(market_type="futures")
        klines = fetcher.fetch_klines(symbol=symbol, interval=interval, limit=300)
        df = pd.DataFrame(klines, columns=["timestamp", "open_price", "high_price", "low_price", "close_price", "volume"])
        df.rename(columns={
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "volume": "volume",
        }, inplace=True)
        for _, row in df.iterrows():
            insert_kline(symbol, interval, row.to_dict())
        log.write(f"inserted {len(df)} historical klines for {symbol} {interval}")
        def record_loop():
            import time
            last_ts = df.index[-1]
            while True:
                try:
                    klines = fetcher.fetch_klines(symbol=symbol, interval=interval, limit=1)
                    df = pd.DataFrame(klines, columns=["timestamp", "open_price", "high_price", "low_price", "close_price", "volume"])
                    df.rename(columns={
                        "open_price": "open",
                        "high_price": "high",
                        "low_price": "low",
                        "close_price": "close",
                        "volume": "volume",
                    }, inplace=True)
                    ts = df['timestamp'].iloc[-1]
                    if ts != last_ts:
                        insert_kline(symbol, interval, df.iloc[-1].to_dict())
                        last_ts = ts
                        log.write(f"已存入 {symbol} {interval} 新K線: {ts}")
                    else:
                        log.write("尚無新K線")
                except Exception as e:
                    log.write(f"紀錄失敗: {e}")
                # 休息到下個 interval
                if interval.endswith('m'):
                    sleep_sec = int(interval[:-1]) * 60
                elif interval.endswith('H'):
                    sleep_sec = int(interval[:-1]) * 3600
                else:
                    sleep_sec = 60
                time.sleep(sleep_sec)
        threading.Thread(target=record_loop, daemon=True).start()
        log.write(f"開始紀錄 {symbol} {interval} K線到 sqlite ...")
        left = self.query_one("#left")
        left.remove_children()
        left.mount(MainMenu(id="main_menu"))

    def select_strategy(self):
        main = self.query_one("#left")
        main.remove_children()
        main.mount(StrategySelect())

    def confirm_strategy(self):
        select = self.query_one("#strategy_select", Select)
        symbol_input = self.query_one("#symbol_input", Input)
        selected_strategy = select.value
        symbol = symbol_input.value.strip()
        log = self.query_one(LogPanel)
        if not symbol:
            log.write("請先輸入 symbol")
            return
        self.symbol = symbol
        for cname, sname in get_strategy_classes():
            if sname == selected_strategy:
                module = importlib.import_module(f"strategy.{cname.lower()}")
                self.strategy_class = getattr(module, cname)
                self.strategy_name = sname
                break
        main = self.query_one("#left")
        main.remove_children()
        main.mount(MainMenu(id="main_menu"))
        log = self.query_one(LogPanel)
        if getattr(self, 'trading_thread', None) and self.trading_thread.is_alive():
            log.write("trading is running, ignore start request")
            return
        intervals = ["1h", "15m"]
        window = 100
        def _run():
            try:
                trading_main(self.strategy_class, self.api_key, self.api_secret, self.passphrase, self.symbol, intervals, window)
            except Exception as e:
                log.write(f"trading main error: {e}")
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self.trading_thread = t
        log.write(f"Started: strategy={self.strategy_name} symbol={self.symbol} intervals={intervals}")

    def query_account(self):
        log = self.query_one(LogPanel)
        if self.exchange == "okx" and self.okx_client:
            try:
                info = self.okx_client.get_account_info()
                log.write(AccountInfo(info, "okx").render())
            except Exception as e:
                log.write(f"Error: {e}")
        elif self.exchange == "binance" and self.api_key and self.api_secret:
            try:
                info = binance_order.get_account_info(self.api_key, self.api_secret)
                log.write(AccountInfo(info, "binance").render())
            except Exception as e:
                log.write(f"Error: {e}")

    def switch_exchange(self):
        self.mount(ExchangeSelect(), after="#main_menu")

    def rekey(self):
        self.switch_exchange()

    def confirm_exchange(self):
        select = self.query_one("#exchange_select", Select)
        api_key = self.query_one("#api_key", Input).value
        api_secret = self.query_one("#api_secret", Input).value
        passphrase = self.query_one("#passphrase", Input).value
        self.exchange = select.value
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        if self.exchange == "okx":
            self.okx_client = OKXOrderClient(api_key, api_secret, passphrase)
        left = self.query_one("#left")
        left.remove_children()
        left.mount(MainMenu(id="main_menu"))

    def exit(self):
        self.exit()

if __name__ == "__main__":
    TradeApp().run()

TradeApp.CSS = """
#left {
    width: 30%;
    border: heavy $accent;
}
#right {
    width: 70%;
    border: heavy $secondary;
}
"""
