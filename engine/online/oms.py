class OrderManager:
	def __init__(self, client):
		self.client = client  # 例如 OKXOrderClient

	def open_long(self, symbol, qty):
		# 實際下單邏輯
		print(f"下多單: {symbol}, 數量: {qty}")
		# return self.client.open_long(symbol, qty)

	def open_short(self, symbol, qty):
		print(f"下空單: {symbol}, 數量: {qty}")
		# return self.client.open_short(symbol, qty)

	def close_position(self, symbol):
		print(f"平倉: {symbol}")
		# return self.client.close_position(symbol)

	def get_position(self, symbol):
		# 查詢持倉
		print(f"查詢持倉: {symbol}")
		# return self.client.get_position(symbol)
		return 0
