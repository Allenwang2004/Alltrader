import websocket
import threading
import json
import time
from typing import Callable, Dict, List, Optional

class OKXWsTicker:
    def __init__(self, symbol: str, channel: str = "tickers", inst_type: str = "SWAP"):
        self.symbol = symbol.replace('_', '-').upper()
        self.channel = channel
        self.inst_type = inst_type
        self.ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.last_price = None
        self._ws = None
        self._thread = None
        self._stop = threading.Event()

    def _on_message(self, ws, message):
        data = json.loads(message)
        # print(f"[OKX WS] Message: {data}")
        if 'data' in data and len(data['data']) > 0:
            self.last_price = float(data['data'][0].get('last', 0))

    def _on_error(self, ws, error):
        print(f"[OKX WS] Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"[OKX WS] Closed: {close_status_code} {close_msg}")

    def _on_open(self, ws):
        sub = {
            "op": "subscribe",
            "args": [
                {
                    "channel": self.channel,
                    "instId": f"{self.symbol}-{self.inst_type}"
                }
            ]
        }
        ws.send(json.dumps(sub))
        print(f"[OKX WS] 訂閱: {sub}")

    def start(self):
        def run():
            self._ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self._ws.run_forever()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._ws:
            self._ws.close()
        if self._thread:
            self._thread.join()

    def get_last_price(self):
        return self.last_price
    
class OKXWsKline:
    def __init__(self, symbol: str, channel: str = "candle1m", inst_type: str = "SWAP"):
        self.symbol = symbol.replace('_', '-').upper()
        self.channel = channel
        self.inst_type = inst_type
        self.ws_url = "wss://ws.okx.com:8443/ws/v5/business"
        self.last_price = None
        self.confirm = '0'
        self._ws = None
        self._thread = None
        self._stop = threading.Event()

    def _on_message(self, ws, message):
        data = json.loads(message)
        if 'data' in data and len(data['data']) > 0:
            self.last_price = float(data['data'][0][4])
            self.confirm = data['data'][0][8]

    def _on_error(self, ws, error):
        print(f"[OKX WS] Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"[OKX WS] Closed: {close_status_code} {close_msg}")

    def _on_open(self, ws):
        sub = {
            "op": "subscribe",
            "args": [
                {
                    "channel": self.channel,
                    "instId": f"{self.symbol}-{self.inst_type}"
                }
            ]
        }
        ws.send(json.dumps(sub))
        print(f"[OKX WS] 訂閱: {sub}")

    def start(self):
        def run():
            self._ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self._ws.run_forever()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._ws:
            self._ws.close()
        if self._thread:
            self._thread.join()

    def get_last_price(self):
        return self.last_price
    
    def is_confirmed(self):
        if self.confirm == '1':
            return True
        else:
            return False


if __name__ == "__main__":
    # ws_ticker = OKXWsTicker("BTC-USDT")
    # ws_ticker.start()
    # try:
    #     while True:
    #         print(f"即時價格: {ws_ticker.get_last_price()}")
    #         time.sleep(2)
    # except KeyboardInterrupt:
    #     ws_ticker.stop()
    
    ws_kline = OKXWsKline("BTC-USDT")
    ws_kline.start()
    try:
        while True:
            if ws_kline.is_confirmed():
                print(f"即時K線收盤價: {ws_kline.get_last_price()}")
            else:
                print("K線尚未確認")
            time.sleep(2)
    except KeyboardInterrupt:
        ws_kline.stop()                    
