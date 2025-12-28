import logging
import os
from datetime import datetime

LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'trade.log')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
	filename=LOG_FILE,
	level=logging.INFO,
	format='%(asctime)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S'
)

def log_trade(action, symbol, price, qty, position, reason=None):
	msg = f"action={action}, symbol={symbol}, price={price}, qty={qty}, position={position}"
	if reason:
		msg += f", reason={reason}"
	logging.info(msg)
