from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static, Input, Select
from textual.containers import Container, Horizontal
from connector.okx_order import OKXOrderClient
from connector import binance_order

class MainMenu(Static):
    def compose(self) -> ComposeResult:
        yield Button("查詢帳戶資訊", id="account")
        yield Button("切換交易所", id="switch")
        yield Button("重新輸入 API key", id="rekey")
        yield Button("離開程式", id="exit")

class ExchangeSelect(Static):
    def compose(self) -> ComposeResult:
        yield Select(options=[("Binance", "binance"), ("OKX", "okx")], prompt="選擇交易所", id="exchange_select")
        yield Input(placeholder="API Key", id="api_key")
        yield Input(placeholder="API Secret", id="api_secret")
        yield Input(placeholder="OKX Passphrase (如選OKX)", id="passphrase")
        yield Button("確認", id="confirm")

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
==== OKX 帳戶資訊 ====
總資產: {data.get('totalEq', 'N/A')}
保證金資產: {data.get('isoEq', 'N/A')}
槓桿率: {data.get('mgnRatio', 'N/A')}
更新時間: {data.get('uTime', 'N/A')}
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

    def compose(self) -> ComposeResult:
        yield Header()
        # 一開始顯示交易所選擇與 API key 輸入
        yield Container(ExchangeSelect(), id="main")
        yield Footer()

    def on_button_pressed(self, event):
        btn_id = event.button.id
        if btn_id == "account":
            self.query_account()
        elif btn_id == "switch":
            self.switch_exchange()
        elif btn_id == "rekey":
            self.rekey()
        elif btn_id == "exit":
            self.exit()
        elif btn_id == "confirm":
            self.confirm_exchange()

    def query_account(self):
        if self.exchange == "okx" and self.okx_client:
            try:
                info = self.okx_client.get_account_info()
                self.mount(AccountInfo(info, "okx"), after="#main_menu")
            except Exception as e:
                self.mount(AccountInfo({"error": str(e)}, "okx"), after="#main_menu")
        elif self.exchange == "binance" and self.api_key and self.api_secret:
            try:
                info = binance_order.get_account_info(self.api_key, self.api_secret)
                self.mount(AccountInfo(info, "binance"), after="#main_menu")
            except Exception as e:
                self.mount(AccountInfo({"error": str(e)}, "binance"), after="#main_menu")

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
        self.query_one("#main").remove_children()
        self.query_one("#main").mount(MainMenu(id="main_menu"))

    def exit(self):
        self.exit()

if __name__ == "__main__":
    TradeApp().run()
