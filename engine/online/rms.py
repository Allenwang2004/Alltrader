class RiskManager:

    def __init__(self):
        # layer_index: (multiplier, reverse_pct)）
        self.layers = [
            (1, 0.00),   # #1
            (1, 0.001),   # #2
            (2, 0.002),   # #3
            (4, 0.002),   # #4
            (2, 0.002),   # #5
            (2, 0.002),   # #6
            (10, 0.005),  # #7
            (5, 0.003),   # #8
            (5, 0.003),   # #9
            (15, 0.007),  # #10
            (15, 0.004),  # #11
            (15, 0.004),  # #12
            (20, 0.010),  # #13
        ]

        #（TP %, trailing %）
        self.tp_rules = [
            (0.001, 0.0004),  # #1
            (0.001, 0.0003),  # #2
            (0.001, 0.0003),  # #3
            (0.001, 0.0003),  # #4
            (0.0012, 0.0004), # #5
            (0.0012, 0.0004), # #6
            (0.0012, 0.0004), # #7
            (0.0014, 0.0006), # #8
            (0.0014, 0.0006), # #9
            (0.0014, 0.0006), # #10
            (0.0016, 0.0008), # #11
            (0.0016, 0.0008), # #12
            (0.0016, 0.0008), # #13
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

        # _, reverse_pct = self.layers[layer_idx]

        reverse_pct = sum(self.layers[i][1] for i in range(0, layer_idx + 1))

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

        # 決定使用哪種均價
        if layer_idx <= 6:
            base_price = self._avg_price()
        else:
            base_price = self._first_last_avg()

        if position == 1:  # long
            pnl_pct = (current_price - base_price) / base_price
        else:  # short
            pnl_pct = (base_price - current_price) / base_price

        # 尚未達到 TP
        if pnl_pct < tp_pct:
            return False

        # 啟動移動止盈
        if self.trailing_peak is None:
            self.trailing_peak = pnl_pct
            print(f"[RMS] start trailing take profit at pnl_pct={pnl_pct:.5f}")
            return False

        self.trailing_peak = max(self.trailing_peak, pnl_pct)
        print(f"[RMS] trailing peak updated to pnl_pct={self.trailing_peak:.5f}")
        if pnl_pct <= self.trailing_peak - trail_pct:
            return True

        return False
