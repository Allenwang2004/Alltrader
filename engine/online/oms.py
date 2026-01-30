import time
from connector.okx_order import OrderSide, PositionSide

def wait_order_filled(order_client, symbol, order_id, poll_interval=1, timeout=30, cancel_on_timeout=True):
	start = time.time()
	while time.time() - start < timeout:
		try:
			info = order_client.get_order(symbol, order_id=order_id)
			status = info.get('data', [{}])[0].get('state')

			# OKX state examples: live/partially_filled/filled/canceled
			if status in ('filled', 'success', '2'):  # 2=成交
				return True
			if status in ('canceled', 'cancelled', 'failed', 'rejected'):
				return False
		except Exception as e:
			print(f"[OMS] get_order failed: {e}")

		time.sleep(poll_interval)

	if cancel_on_timeout:
		try:
			order_client.cancel_order(symbol, order_id=order_id)
			print(f"[OMS] order timeout, cancelled: {order_id}")
		except Exception as e:
			print(f"[OMS] cancel order failed: {e}")
	return False


def _normalize_position_side(position_side):
	if isinstance(position_side, PositionSide):
		return position_side
	if isinstance(position_side, str):
		side = position_side.lower()
		if side == 'long':
			return PositionSide.LONG
		if side == 'short':
			return PositionSide.SHORT
	raise ValueError(f"Invalid position_side: {position_side}")

class OrderManager:
	def __init__(self, client, max_retries=3, retry_delay=2):
		self.client = client
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
		position_side = _normalize_position_side(position_side)
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
