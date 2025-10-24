"""
Example script demonstrating how to use the Binance Kline Fetcher.

This script shows various ways to fetch kline data from Binance spot and futures markets.
"""

from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path so we can import from connector
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connector.binance_kline import (
    BinanceKlineFetcher,
    create_spot_fetcher,
    create_futures_fetcher,
    fetch_spot_klines,
    fetch_futures_klines,
    BinanceKlineError
)
from connector.binance_open_interest import (
    BinanceOpenInterestFetcher,
    fetch_current_open_interest,
    fetch_historical_open_interest,
    fetch_all_open_interest,
    BinanceOpenInterestError
)


def example_basic_usage():
    """Demonstrate basic usage of the kline fetcher."""
    print("=== Basic Usage Example ===")
    
    try:
        # Fetch recent 100 1-hour klines for BTCUSDT spot
        klines = fetch_spot_klines(
            symbol="BTCUSDT",
            interval="1h",
            limit=5  # Just 5 for demo
        )
        
        print(f"Fetched {len(klines)} klines for BTCUSDT (spot)")
        
        # Print the first kline
        if klines:
            first_kline = klines[0]
            print(f"First kline:")
            print(f"  Open time: {first_kline['open_time_str']}")
            print(f"  OHLC: {first_kline['open_price']}, {first_kline['high_price']}, "
                  f"{first_kline['low_price']}, {first_kline['close_price']}")
            print(f"  Volume: {first_kline['volume']}")
            
    except BinanceKlineError as e:
        print(f"Error fetching klines: {e}")


def example_time_range_usage():
    """Demonstrate fetching klines for a specific time range."""
    print("\n=== Time Range Example ===")
    
    try:
        # Define time range (last 24 hours)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        print(f"Fetching klines from {start_time} to {end_time}")
        
        # Fetch 15-minute klines for the last 24 hours
        klines = fetch_spot_klines(
            symbol="ETHUSDT",
            interval="15m",
            start_time=start_time,
            end_time=end_time
        )
        
        print(f"Fetched {len(klines)} 15-minute klines for ETHUSDT")
        
        if len(klines) >= 2:
            print(f"Time range: {klines[0]['open_time_str']} to {klines[-1]['close_time_str']}")
            
    except BinanceKlineError as e:
        print(f"Error fetching klines: {e}")


def example_futures_usage():
    """Demonstrate fetching futures klines."""
    print("\n=== Futures Market Example ===")
    
    try:
        # Fetch recent futures klines
        klines = fetch_futures_klines(
            symbol="BTCUSDT",
            interval="1h",
            limit=3
        )
        
        print(f"Fetched {len(klines)} futures klines for BTCUSDT")
        
        for i, kline in enumerate(klines):
            print(f"Kline {i+1}: Price range {kline['low_price']:.2f} - {kline['high_price']:.2f}")
            
    except BinanceKlineError as e:
        print(f"Error fetching futures klines: {e}")


def example_class_usage():
    """Demonstrate using the BinanceKlineFetcher class directly."""
    print("\n=== Class-based Usage Example ===")
    
    try:
        # Create a fetcher with custom settings
        fetcher = BinanceKlineFetcher(
            market_type="spot",
            request_delay=0.2  # Slower requests to be extra safe
        )
        
        # Fetch klines
        klines = fetcher.fetch_klines(
            symbol="ADAUSDT",
            interval="1d",
            limit=7  # Last 7 days
        )
        
        print(f"Fetched {len(klines)} daily klines for ADAUSDT")
        
        # Calculate some simple statistics
        if klines:
            prices = [float(kline['close_price']) for kline in klines]
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            print(f"Price statistics over {len(klines)} days:")
            print(f"  Average: ${avg_price:.4f}")
            print(f"  Min: ${min_price:.4f}")
            print(f"  Max: ${max_price:.4f}")
            
    except BinanceKlineError as e:
        print(f"Error with class-based usage: {e}")


def example_paginated_usage():
    """Demonstrate paginated fetching for large datasets."""
    print("\n=== Paginated Fetching Example ===")
    
    try:
        # Create a fetcher
        fetcher = create_spot_fetcher()
        
        # Define a longer time range (7 days of 5-minute data)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        print(f"Fetching 7 days of 5-minute data (this might take a while...)")
        print("This is just a demo - limiting to 100 records for speed")
        
        # Use paginated fetch with a limit to avoid long waits
        klines = fetcher.fetch_klines_paginated(
            symbol="BTCUSDT",
            interval="5m",
            start_time=start_time,
            end_time=end_time,
            max_records=100  # Limit for demo purposes
        )
        
        print(f"Fetched {len(klines)} klines using pagination")
        
        if klines:
            print(f"Data range: {klines[0]['open_time_str']} to {klines[-1]['close_time_str']}")
            
    except BinanceKlineError as e:
        print(f"Error with paginated fetch: {e}")


def example_error_handling():
    """Demonstrate error handling."""
    print("\n=== Error Handling Example ===")
    
    # Test with invalid symbol
    try:
        klines = fetch_spot_klines(
            symbol="INVALIDSYMBOL",
            interval="1h",
            limit=1
        )
        print("This shouldn't print - invalid symbol should cause an error")
        
    except BinanceKlineError as e:
        print(f"Expected error with invalid symbol: {e}")
    
    # Test with invalid interval
    try:
        klines = fetch_spot_klines(
            symbol="BTCUSDT",
            interval="invalid_interval",
            limit=1
        )
        print("This shouldn't print - invalid interval should cause an error")
        
    except ValueError as e:
        print(f"Expected error with invalid interval: {e}")


def example_current_open_interest():
    """Demonstrate fetching current open interest data."""
    print("\n=== Current Open Interest Example ===")
    
    try:
        # Fetch current open interest for BTCUSDT futures
        oi_data = fetch_current_open_interest("BTCUSDT")
        
        print(f"Current open interest for {oi_data['symbol']}:")
        print(f"  Open Interest: {oi_data['open_interest']:,.0f}")
        print(f"  Timestamp: {oi_data['time_str']}")
        
    except BinanceOpenInterestError as e:
        print(f"Error fetching open interest: {e}")


def example_historical_open_interest():
    """Demonstrate fetching historical open interest data."""
    print("\n=== Historical Open Interest Example ===")
    
    try:
        # Define time range (last 7 days)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        print(f"Fetching historical open interest from {start_time.date()} to {end_time.date()}")
        
        # Fetch daily historical open interest
        hist_data = fetch_historical_open_interest(
            symbol="BTCUSDT",
            period="1d",
            start_time=start_time,
            end_time=end_time,
            limit=7  # Last 7 days
        )
        
        print(f"Fetched {len(hist_data)} daily open interest records for BTCUSDT")
        
        if hist_data:
            print("\nRecent open interest trend:")
            for record in hist_data[-3:]:  # Show last 3 records
                oi_value = record['sum_open_interest']
                timestamp = record['timestamp_str'][:10]  # Just the date part
                print(f"  {timestamp}: {oi_value:,.0f}")
                
    except BinanceOpenInterestError as e:
        print(f"Error fetching historical open interest: {e}")


def example_all_open_interest():
    """Demonstrate fetching open interest for all symbols."""
    print("\n=== All Symbols Open Interest Example ===")
    
    try:
        # Fetch current open interest for all futures symbols
        print("Fetching open interest for all symbols (this might take a moment)...")
        all_oi = fetch_all_open_interest()
        
        print(f"Fetched open interest data for {len(all_oi)} symbols")
        
        # Find top 5 symbols by open interest
        sorted_oi = sorted(all_oi, key=lambda x: x['open_interest'], reverse=True)
        
        print("\nTop 5 symbols by open interest:")
        for i, record in enumerate(sorted_oi[:5]):
            print(f"  {i+1}. {record['symbol']}: {record['open_interest']:,.0f}")
            
    except BinanceOpenInterestError as e:
        print(f"Error fetching all open interest data: {e}")


def example_open_interest_class_usage():
    """Demonstrate using the BinanceOpenInterestFetcher class directly."""
    print("\n=== Open Interest Class Usage Example ===")
    
    try:
        # Create fetcher with custom settings
        oi_fetcher = BinanceOpenInterestFetcher(request_delay=0.2)
        
        # Fetch current open interest
        current_oi = oi_fetcher.fetch_current_open_interest("ETHUSDT")
        print(f"Current ETHUSDT open interest: {current_oi['open_interest']:,.0f}")
        
        # Fetch recent hourly historical data
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        hourly_oi = oi_fetcher.fetch_historical_open_interest(
            symbol="ETHUSDT",
            period="1h",
            start_time=start_time,
            end_time=end_time,
            limit=24  # Last 24 hours
        )
        
        if hourly_oi:
            latest_oi = hourly_oi[-1]['sum_open_interest']
            earliest_oi = hourly_oi[0]['sum_open_interest']
            change = latest_oi - earliest_oi
            change_pct = (change / earliest_oi) * 100 if earliest_oi > 0 else 0
            
            print(f"24-hour open interest change: {change:+,.0f} ({change_pct:+.2f}%)")
            
    except BinanceOpenInterestError as e:
        print(f"Error with open interest class usage: {e}")


if __name__ == "__main__":
    print("Binance Data Fetcher Examples")
    print("=" * 40)
    
    # Run kline examples
    print("KLINE DATA EXAMPLES")
    print("-" * 20)
    example_basic_usage()
    example_time_range_usage()
    example_futures_usage()
    example_class_usage()
    example_paginated_usage()
    
    # Run open interest examples
    print("\n\nOPEN INTEREST EXAMPLES")
    print("-" * 22)
    example_current_open_interest()
    example_historical_open_interest()
    example_all_open_interest()
    example_open_interest_class_usage()
    
    # Run error handling examples
    print("\n\nERROR HANDLING EXAMPLES")
    print("-" * 23)
    example_error_handling()
    
    print("\n" + "=" * 40)
    print("Examples completed!")
    print("\nNote: These examples make real API calls to Binance.")
    print("Please be mindful of rate limits when running frequently.")