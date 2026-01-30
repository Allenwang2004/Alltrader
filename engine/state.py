from collections import deque

class RollingWindow:
    def __init__(self, maxlen: int):
        self.data = deque(maxlen=maxlen)

    def append(self, bar: dict):
        self.data.append(bar)

    def get_all(self):
        return list(self.data)


class TimeframeState:
    def __init__(self):
        self.m15 = RollingWindow(100)
        self.h1 = RollingWindow(100)