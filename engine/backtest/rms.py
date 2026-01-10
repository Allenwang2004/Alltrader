class RiskManager:

    def __init__(self):
        # layer_index: (multiplier, reverse_pct)）
        self.layers = [
            (1, 0.01),   # #2
            (2, 0.02),   # #3
            (4, 0.02),   # #4
            (2, 0.02),   # #5
            (2, 0.02),   # #6
            (10, 0.05),  # #7
            (5, 0.03),   # #8
            (5, 0.03),   # #9
            (15, 0.07),  # #10
            (15, 0.04),  # #11
            (15, 0.04),  # #12
            (20, 0.10),  # #13
        ]

        #（TP %, trailing %）
        self.tp_rules = [
            (0.01, 0.004),  # #1
            (0.01, 0.003),  # #2
            (0.01, 0.003),  # #3
            (0.01, 0.003),  # #4
            (0.012, 0.004), # #5
            (0.012, 0.004), # #6
            (0.012, 0.004), # #7
            (0.014, 0.006), # #8
            (0.014, 0.006), # #9
            (0.014, 0.006), # #10
            (0.016, 0.008), # #11
            (0.016, 0.008), # #12
            (0.016, 0.008), # #13
        ]

        self.positions = []  # [{"price": , "qty": }]
        self.trailing_peak = None

    def reset(self):
        self.positions = []
        self.trailing_peak = None

    def add_position(self, price, base_qty):
        layer_idx = len(self.positions)
        if layer_idx >= len(self.layers):
            return None

        multiplier, _ = self.layers[layer_idx]
        qty = base_qty * multiplier
        self.positions.append({"price": price, "qty": qty})
        return qty

    def should_add_position(self, entry_price, current_price, position):
        if not self.positions:
            return True

        layer_idx = len(self.positions)
        if layer_idx >= len(self.layers):
            return False

        _, reverse_pct = self.layers[layer_idx]

        if position == 1:  # long
            return (entry_price - current_price) / entry_price >= reverse_pct
        else:  # short
            return (current_price - entry_price) / entry_price >= reverse_pct

    def _avg_price(self):
        total = sum(p["price"] * p["qty"] for p in self.positions)
        qty = sum(p["qty"] for p in self.positions)
        return total / qty

    def _first_last_avg(self):
        first = self.positions[0]
        last = self.positions[-1]
        return (first["price"] * first["qty"] + last["price"] * last["qty"]) / (first["qty"] + last["qty"])

    def check_take_profit(self, current_price, position):
        layer_idx = len(self.positions) - 1
        if layer_idx < 0:
            return False

        tp_pct, trail_pct = self.tp_rules[layer_idx]

        if layer_idx <= 6:
            base_price = self._avg_price()
        else:
            base_price = self._first_last_avg()

        if position == 1:  # long
            pnl_pct = (current_price - base_price) / base_price
        else:  # short
            pnl_pct = (base_price - current_price) / base_price

        if pnl_pct < tp_pct:
            return False

        if self.trailing_peak is None:
            self.trailing_peak = pnl_pct
            return False

        self.trailing_peak = max(self.trailing_peak, pnl_pct)

        if pnl_pct <= self.trailing_peak - trail_pct:
            return True

        return False