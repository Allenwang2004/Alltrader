"""
Binance Kline Data Fetcher

This module provides functionality to fetch kline (candlestick) data from Binance
for both spot and futures markets within specified time ranges.

Features:
- Support for spot and futures markets
- Time range filtering with start_time and end_time
- Automatic pagination for large data requests
- Input validation for symbols and time ranges
- Rate limiting considerations
- Comprehensive error handling
"""

import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BinanceKlineError(Exception):
    """Custom exception for Binance kline fetching errors"""
    pass


class BinanceKlineFetcher:
    """
    A class to fetch kline data from Binance spot and futures markets.
    
    This class handles API requests to Binance to retrieve candlestick data
    for specified symbols within given time ranges.
    """
    
    # Binance API endpoints
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"
    
    # API endpoints
    SPOT_KLINES_ENDPOINT = "/api/v3/klines"
    FUTURES_KLINES_ENDPOINT = "/fapi/v1/klines"
    
    # Valid intervals for kline data
    VALID_INTERVALS = [
        "1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M"
    ]
    
    # Maximum limit per request (Binance limit)
    MAX_LIMIT = 1500
    
    def __init__(self, market_type: str = "spot", request_delay: float = 0.1):
        """
        Initialize the BinanceKlineFetcher.
        
        Args:
            market_type (str): Market type, either "spot" or "futures"
            request_delay (float): Delay between requests in seconds to avoid rate limiting
        """
        if market_type not in ["spot", "futures"]:
            raise ValueError("market_type must be 'spot' or 'futures'")
            
        self.market_type = market_type
        self.request_delay = request_delay
        
        if market_type == "spot":
            self.base_url = self.SPOT_BASE_URL
            self.klines_endpoint = self.SPOT_KLINES_ENDPOINT
        else:
            self.base_url = self.FUTURES_BASE_URL
            self.klines_endpoint = self.FUTURES_KLINES_ENDPOINT
            
        self.session = requests.Session()
        
    def _validate_symbol(self, symbol: str) -> str:
        """
        Validate and format symbol.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            str: Formatted symbol in uppercase
            
        Raises:
            ValueError: If symbol is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Symbol must be a non-empty string")
            
        symbol = symbol.upper().strip()
        
        if len(symbol) < 3:
            raise ValueError("Symbol must be at least 3 characters long")
            
        return symbol
    
    def _validate_interval(self, interval: str) -> str:
        """
        Validate interval parameter.
        
        Args:
            interval (str): Kline interval
            
        Returns:
            str: Validated interval
            
        Raises:
            ValueError: If interval is invalid
        """
        if interval not in self.VALID_INTERVALS:
            raise ValueError(f"Invalid interval. Must be one of: {self.VALID_INTERVALS}")
        return interval
    
    def _validate_timestamp(self, timestamp: Union[int, str, datetime]) -> int:
        """
        Convert and validate timestamp.
        
        Args:
            timestamp: Timestamp in various formats
            
        Returns:
            int: Unix timestamp in milliseconds
            
        Raises:
            ValueError: If timestamp is invalid
        """
        if isinstance(timestamp, datetime):
            return int(timestamp.timestamp() * 1000)
        elif isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return int(dt.timestamp() * 1000)
            except ValueError:
                raise ValueError(f"Invalid datetime string format: {timestamp}")
        elif isinstance(timestamp, (int, float)):
            # Assume it's already in milliseconds if > 10^10, otherwise convert from seconds
            if timestamp > 10**10:
                return int(timestamp)
            else:
                return int(timestamp * 1000)
        else:
            raise ValueError("Timestamp must be datetime, string, or numeric")
    
    def _make_request(self, params: Dict[str, Any]) -> List[List]:
        """
        Make API request to Binance.
        
        Args:
            params (dict): Request parameters
            
        Returns:
            List[List]: Raw kline data from Binance API
            
        Raises:
            BinanceKlineError: If API request fails
        """
        url = f"{self.base_url}{self.klines_endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not isinstance(data, list):
                raise BinanceKlineError(f"Unexpected response format: {data}")
                
            return data
            
        except requests.exceptions.RequestException as e:
            raise BinanceKlineError(f"API request failed: {str(e)}")
        except ValueError as e:
            raise BinanceKlineError(f"Invalid JSON response: {str(e)}")
    
    def _format_kline_data(self, raw_data: List[List]) -> List[Dict[str, Any]]:
        """
        Format raw kline data into structured dictionaries.
        
        Args:
            raw_data (List[List]): Raw kline data from Binance API
            
        Returns:
            List[Dict]: Formatted kline data
        """
        formatted_data = []
        
        for kline in raw_data:
            formatted_kline = {
                'open_time': int(kline[0]),
                'open_price': float(kline[1]),
                'high_price': float(kline[2]),
                'low_price': float(kline[3]),
                'close_price': float(kline[4]),
                'volume': float(kline[5]),
                'close_time': int(kline[6]),
                'quote_asset_volume': float(kline[7]),
                'number_of_trades': int(kline[8]),
                'taker_buy_base_asset_volume': float(kline[9]),
                'taker_buy_quote_asset_volume': float(kline[10]),
                'ignore': kline[11]
            }
            
            # Add human-readable timestamps
            formatted_kline['open_time_str'] = datetime.fromtimestamp(
                formatted_kline['open_time'] / 1000, tz=timezone.utc
            ).isoformat()
            formatted_kline['close_time_str'] = datetime.fromtimestamp(
                formatted_kline['close_time'] / 1000, tz=timezone.utc
            ).isoformat()
            
            formatted_data.append(formatted_kline)
            
        return formatted_data
    
    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[Union[int, str, datetime]] = None,
        end_time: Optional[Union[int, str, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch kline data for a specific symbol and time range.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            interval (str): Kline interval (e.g., '1h', '1d')
            start_time: Start time for data range
            end_time: End time for data range
            limit (int, optional): Maximum number of klines to return
            
        Returns:
            List[Dict]: List of kline data dictionaries
            
        Raises:
            ValueError: If parameters are invalid
            BinanceKlineError: If API request fails
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        interval = self._validate_interval(interval)
        
        # Prepare parameters
        params = {
            'symbol': symbol,
            'interval': interval
        }
        
        if start_time is not None:
            params['startTime'] = self._validate_timestamp(start_time)
            
        if end_time is not None:
            params['endTime'] = self._validate_timestamp(end_time)
            
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError("limit must be a positive integer")
            params['limit'] = min(limit, self.MAX_LIMIT)
        else:
            params['limit'] = self.MAX_LIMIT
            
        logger.info(f"Fetching {self.market_type} klines for {symbol} "
                   f"with interval {interval}")
        
        # Make request
        raw_data = self._make_request(params)
        
        # Add delay to avoid rate limiting
        time.sleep(self.request_delay)
        
        # Format and return data
        return self._format_kline_data(raw_data)
    
    def fetch_klines_paginated(
        self,
        symbol: str,
        interval: str,
        start_time: Union[int, str, datetime],
        end_time: Union[int, str, datetime],
        max_records: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch klines with automatic pagination for large time ranges.
        
        This method automatically handles pagination when the requested time range
        would exceed Binance's maximum limit per request.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            interval (str): Kline interval (e.g., '1h', '1d')
            start_time: Start time for data range
            end_time: End time for data range
            max_records (int, optional): Maximum total records to fetch
            
        Returns:
            List[Dict]: Complete list of kline data
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        interval = self._validate_interval(interval)
        start_timestamp = self._validate_timestamp(start_time)
        end_timestamp = self._validate_timestamp(end_time)
        
        if start_timestamp >= end_timestamp:
            raise ValueError("start_time must be before end_time")
        
        all_klines = []
        current_start = start_timestamp
        total_fetched = 0
        
        logger.info(f"Starting paginated fetch for {symbol} from "
                   f"{datetime.fromtimestamp(start_timestamp/1000)} to "
                   f"{datetime.fromtimestamp(end_timestamp/1000)}")
        
        while current_start < end_timestamp:
            # Determine limit for this request
            remaining_records = None
            if max_records is not None:
                remaining_records = max_records - total_fetched
                if remaining_records <= 0:
                    break
                    
            current_limit = min(self.MAX_LIMIT, remaining_records or self.MAX_LIMIT)
            
            # Fetch batch
            batch_klines = self.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_timestamp,
                limit=current_limit
            )
            
            if not batch_klines:
                logger.info("No more data available")
                break
                
            all_klines.extend(batch_klines)
            total_fetched += len(batch_klines)
            
            # Update start time for next batch
            last_close_time = batch_klines[-1]['close_time']
            current_start = last_close_time + 1  # Start from next millisecond
            
            logger.info(f"Fetched {len(batch_klines)} klines. "
                       f"Total: {total_fetched}")
            
            # Check if we got less than expected (end of available data)
            if len(batch_klines) < current_limit:
                logger.info("Reached end of available data")
                break
        
        logger.info(f"Completed paginated fetch. Total records: {len(all_klines)}")
        return all_klines


def create_spot_fetcher(request_delay: float = 0.1) -> BinanceKlineFetcher:
    """
    Create a BinanceKlineFetcher for spot market.
    
    Args:
        request_delay (float): Delay between requests
        
    Returns:
        BinanceKlineFetcher: Configured for spot market
    """
    return BinanceKlineFetcher(market_type="spot", request_delay=request_delay)


def create_futures_fetcher(request_delay: float = 0.1) -> BinanceKlineFetcher:
    """
    Create a BinanceKlineFetcher for futures market.
    
    Args:
        request_delay (float): Delay between requests
        
    Returns:
        BinanceKlineFetcher: Configured for futures market
    """
    return BinanceKlineFetcher(market_type="futures", request_delay=request_delay)


# Convenience functions for quick usage
def fetch_spot_klines(
    symbol: str,
    interval: str,
    start_time: Optional[Union[int, str, datetime]] = None,
    end_time: Optional[Union[int, str, datetime]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Quick function to fetch spot klines.
    
    Args:
        symbol (str): Trading symbol
        interval (str): Kline interval
        start_time: Start time for data range
        end_time: End time for data range
        limit (int, optional): Maximum number of klines
        
    Returns:
        List[Dict]: Kline data
    """
    fetcher = create_spot_fetcher()
    return fetcher.fetch_klines(symbol, interval, start_time, end_time, limit)


def fetch_futures_klines(
    symbol: str,
    interval: str,
    start_time: Optional[Union[int, str, datetime]] = None,
    end_time: Optional[Union[int, str, datetime]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Quick function to fetch futures klines.
    
    Args:
        symbol (str): Trading symbol
        interval (str): Kline interval
        start_time: Start time for data range
        end_time: End time for data range
        limit (int, optional): Maximum number of klines
        
    Returns:
        List[Dict]: Kline data
    """
    fetcher = create_futures_fetcher()
    return fetcher.fetch_klines(symbol, interval, start_time, end_time, limit)