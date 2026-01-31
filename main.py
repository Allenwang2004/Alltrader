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
from strategy.longstrategy import LongStrategy
from engine.trader import trading_main

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
        yield Button("Set Leverage", id="set_leverage")
        yield Button("Exit", id="exit")

class StrategySelect(Static):
    def compose(self) -> ComposeResult:
        # 動態取得策略清單
        strategies = get_strategy_classes()
        options = [(sname, cname) for cname, sname in strategies]
        yield Input(placeholder="Symbol (如 BTC-USDT)", id="symbol_input")
        yield Select(options=options, prompt="Select Strategy", id="strategy_select")
        yield Button("Confirm Strategy", id="confirm_strategy")

class LeverageSelect(Static):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Symbol (如 BTC-USDT)", id="lev_symbol")
        yield Input(placeholder="Leverage (OKX, e.g. 5)", id="leverage")
        yield Select(options=[("cross", "cross"), ("isolated", "isolated")], prompt="Margin Mode (OKX)", id="margin_mode")
        yield Select(options=[("auto", "auto"), ("long", "long"), ("short", "short"), ("net", "net")], prompt="Position Side (OKX)", id="pos_side")
        yield Button("Apply Leverage", id="confirm_leverage")

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
        self.leverage = None
        self.margin_mode = None
        self.pos_side = None
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
        elif btn_id == "set_leverage":
            self.show_leverage()
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
        elif btn_id == "confirm_leverage":
            self.confirm_leverage()

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
        found = False
        for cname, sname in get_strategy_classes():
            # Select.value contains the second tuple element (we set value=cname)
            if cname == selected_strategy:
                try:
                    module = importlib.import_module(f"strategy.{cname.lower()}")
                    self.strategy_class = getattr(module, cname)
                    self.strategy_name = sname
                    found = True
                except Exception as e:
                    log.write(f"Load error: {e}")
                break
        if not found:
            log.write(f"Cannot find strategy: {selected_strategy}")
            return
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

    def show_leverage(self):
        main = self.query_one("#left")
        main.remove_children()
        main.mount(LeverageSelect())

    def confirm_leverage(self):
        log = self.query_one(LogPanel)
        if self.exchange != "okx" or not self.okx_client:
            log.write("Only OKX supports leverage setting here.")
            return
        symbol_input = self.query_one("#lev_symbol", Input).value.strip()
        symbol = symbol_input or getattr(self, "symbol", None)
        if not symbol:
            log.write("請先輸入 symbol")
            return
        leverage_raw = self.query_one("#leverage", Input).value
        if not leverage_raw.strip().isdigit():
            log.write("Leverage 必須是整數")
            return
        self.leverage = int(leverage_raw)
        self.margin_mode = self.query_one("#margin_mode", Select).value
        self.pos_side = self.query_one("#pos_side", Select).value
        try:
            pos_side = None if self.pos_side in (None, "", "auto") else self.pos_side
            self.okx_client.set_futures_leverage_with_pos_side(
                symbol=symbol,
                leverage=self.leverage,
                margin_mode=self.margin_mode or "cross",
                position_side=pos_side
            )
            log.write(f"Leverage set: {self.leverage}x mode={self.margin_mode or 'cross'} posSide={pos_side or 'auto'}")
            main = self.query_one("#left")
            main.remove_children()
            main.mount(MainMenu(id="main_menu"))
        except Exception as e:
            log.write(f"Set leverage failed: {e}")

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
