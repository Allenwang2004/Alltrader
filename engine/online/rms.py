class RiskManager:
	def __init__(self, stop_loss=0.02, take_profit=0.03):
		self.stop_loss = stop_loss
		self.take_profit = take_profit

	def check_risk(self, entry_price, current_price, position):
		"""
		根據持倉方向與價格，判斷是否觸發止盈/止損
		position: 1=多單, -1=空單, 0=無倉
		"""
		if position == 0:
			return False, None
		if position == 1:
			if (current_price - entry_price) / entry_price <= -self.stop_loss:
				return True, 'stop_loss'
			if (current_price - entry_price) / entry_price >= self.take_profit:
				return True, 'take_profit'
		if position == -1:
			if (entry_price - current_price) / entry_price <= -self.stop_loss:
				return True, 'stop_loss'
			if (entry_price - current_price) / entry_price >= self.take_profit:
				return True, 'take_profit'
		return False, None
