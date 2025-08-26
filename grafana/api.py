import os
import dotenv
dotenv.load_dotenv()  # Load environment variables from a .env file if present
from binance.client import Client

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

class BinanceSpotAccount:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)

    def get_total_asset(self):
        account_info = self.client.get_account()
        total_asset = sum(float(balance['free']) + float(balance['locked']) for balance in account_info['balances'])
        return total_asset
    
class BinanceFuturesAccount:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)

    def get_total_asset(self):
        account_info = self.client.futures_account()
        total_asset = float(account_info['totalWalletBalance'])
        return total_asset
if __name__ == "__main__":
    spot_account = BinanceSpotAccount(api_key, api_secret)
    futures_account = BinanceFuturesAccount(api_key, api_secret)

    print("Spot Account Total Asset:", spot_account.get_total_asset())
    print("Futures Account Total Asset:", futures_account.get_total_asset())
