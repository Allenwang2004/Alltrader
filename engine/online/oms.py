import time
from connector.okx_order import OrderSide, PositionSide

class OrderManager:
	def __init__(self, client, max_retries=3, retry_delay=2):
		self.client = client  # OKXOrderClient
		self.max_retries = max_retries
		self.retry_delay = retry_delay

	def open_long(self, symbol, qty):
		for attempt in range(self.max_retries):
			try:
				resp = self.client.place_futures_market_order(
					symbol=symbol,
					side=OrderSide.BUY,
					size=qty,
					position_side=PositionSide.LONG,
					reduce_only=False
				)
				print(f"下多單成功: {resp}")
				return resp
			except Exception as e:
				print(f"下多單失敗: {e}, 重試 {attempt+1}/{self.max_retries}")
				time.sleep(self.retry_delay)
		raise Exception("多單下單失敗，已重試多次")

	def open_short(self, symbol, qty):
		for attempt in range(self.max_retries):
			try:
				resp = self.client.place_futures_market_order(
					symbol=symbol,
					side=OrderSide.SELL,
					size=qty,
					position_side=PositionSide.SHORT,
					reduce_only=False
				)
				print(f"下空單成功: {resp}")
				return resp
			except Exception as e:
				print(f"下空單失敗: {e}, 重試 {attempt+1}/{self.max_retries}")
				time.sleep(self.retry_delay)
		raise Exception("空單下單失敗，已重試多次")

	def close_position(self, symbol, qty, position_side):
		for attempt in range(self.max_retries):
			try:
				resp = self.client.place_futures_market_order(
					symbol=symbol,
					side=OrderSide.SELL if position_side==PositionSide.LONG else OrderSide.BUY,
					size=qty,
					position_side=position_side,
					reduce_only=True
				)
				print(f"平倉成功: {resp}")
				return resp
			except Exception as e:
				print(f"平倉失敗: {e}, 重試 {attempt+1}/{self.max_retries}")
				time.sleep(self.retry_delay)
		raise Exception("平倉失敗，已重試多次")

	def get_position(self, symbol):
		try:
			pos_info = self.client.get_futures_positions(symbol)
			print(f"持倉資訊: {pos_info}")
			return pos_info
		except Exception as e:
			print(f"查詢持倉失敗: {e}")
			return None
