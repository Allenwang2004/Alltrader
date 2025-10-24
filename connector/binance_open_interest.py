"""
Binance Open Interest Data Fetcher

This module provides functionality to fetch open interest data from Binance futures markets.
Open interest represents the total number of outstanding derivative contracts that have 
not been settled.

Features:
- Current open interest data for futures contracts
- Historical open interest data with time range filtering
- Support for different time intervals
- Input validation and error handling
- Rate limiting considerations
"""

import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BinanceOpenInterestError(Exception):
    """Custom exception for Binance open interest fetching errors"""
    pass


class BinanceOpenInterestFetcher:
    """
    A class to fetch open interest data from Binance futures markets.
    
    Open interest data is only available for futures markets, not spot markets.
    """
    
    # Binance Futures API endpoints
    FUTURES_BASE_URL = "https://fapi.binance.com"
    
    # API endpoints
    OPEN_INTEREST_ENDPOINT = "/fapi/v1/openInterest"
    OPEN_INTEREST_HIST_ENDPOINT = "/futures/data/openInterestHist"
    
    # Valid intervals for historical open interest data
    VALID_INTERVALS = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
    
    # Maximum limit per request
    MAX_LIMIT = 500
    
    def __init__(self, request_delay: float = 0.1):
        """
        Initialize the BinanceOpenInterestFetcher.
        
        Args:
            request_delay (float): Delay between requests in seconds to avoid rate limiting
        """
        self.request_delay = request_delay
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
        Validate interval parameter for historical data.
        
        Args:
            interval (str): Time interval
            
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
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Union[Dict, List]:
        """
        Make API request to Binance.
        
        Args:
            endpoint (str): API endpoint
            params (dict): Request parameters
            
        Returns:
            Union[Dict, List]: Response data from Binance API
            
        Raises:
            BinanceOpenInterestError: If API request fails
        """
        url = f"{self.FUTURES_BASE_URL}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            raise BinanceOpenInterestError(f"API request failed: {str(e)}")
        except ValueError as e:
            raise BinanceOpenInterestError(f"Invalid JSON response: {str(e)}")
    
    def fetch_current_open_interest(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current open interest for a specific symbol.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            Dict: Current open interest data
            
        Raises:
            ValueError: If symbol is invalid
            BinanceOpenInterestError: If API request fails
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        
        # Prepare parameters
        params = {'symbol': symbol}
        
        logger.info(f"Fetching current open interest for {symbol}")
        
        # Make request
        data = self._make_request(self.OPEN_INTEREST_ENDPOINT, params)
        
        # Add delay to avoid rate limiting
        time.sleep(self.request_delay)
        
        # Format response
        formatted_data = {
            'symbol': data.get('symbol'),
            'open_interest': float(data.get('openInterest', 0)),
            'time': int(data.get('time', 0)),
            'time_str': datetime.fromtimestamp(
                int(data.get('time', 0)) / 1000, tz=timezone.utc
            ).isoformat() if data.get('time') else None
        }
        
        return formatted_data
    
    def fetch_historical_open_interest(
        self,
        symbol: str,
        period: str,
        start_time: Optional[Union[int, str, datetime]] = None,
        end_time: Optional[Union[int, str, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical open interest data for a specific symbol.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            period (str): Time interval (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            start_time: Start time for data range
            end_time: End time for data range
            limit (int, optional): Maximum number of records to return
            
        Returns:
            List[Dict]: Historical open interest data
            
        Raises:
            ValueError: If parameters are invalid
            BinanceOpenInterestError: If API request fails
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        period = self._validate_interval(period)
        
        # Prepare parameters
        params = {
            'symbol': symbol,
            'period': period
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
            
        logger.info(f"Fetching historical open interest for {symbol} with period {period}")
        
        # Make request
        data = self._make_request(self.OPEN_INTEREST_HIST_ENDPOINT, params)
        
        # Add delay to avoid rate limiting
        time.sleep(self.request_delay)
        
        # Format and return data
        return self._format_historical_data(data)
    
    def _format_historical_data(self, raw_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Format raw historical open interest data.
        
        Args:
            raw_data (List[Dict]): Raw data from Binance API
            
        Returns:
            List[Dict]: Formatted historical data
        """
        formatted_data = []
        
        for item in raw_data:
            formatted_item = {
                'symbol': item.get('symbol'),
                'sum_open_interest': float(item.get('sumOpenInterest', 0)),
                'sum_open_interest_value': float(item.get('sumOpenInterestValue', 0)),
                'timestamp': int(item.get('timestamp', 0)),
                'timestamp_str': datetime.fromtimestamp(
                    int(item.get('timestamp', 0)) / 1000, tz=timezone.utc
                ).isoformat() if item.get('timestamp') else None
            }
            formatted_data.append(formatted_item)
            
        return formatted_data
    
    def fetch_all_open_interest(self) -> List[Dict[str, Any]]:
        """
        Fetch current open interest for all active futures symbols.
        
        Returns:
            List[Dict]: Open interest data for all symbols
            
        Raises:
            BinanceOpenInterestError: If API request fails
        """
        logger.info("Fetching open interest for all symbols")
        
        # Make request without symbol parameter to get all symbols
        data = self._make_request(self.OPEN_INTEREST_ENDPOINT, {})
        
        # Add delay to avoid rate limiting
        time.sleep(self.request_delay)
        
        # If data is a list (all symbols), format each item
        if isinstance(data, list):
            formatted_data = []
            for item in data:
                formatted_item = {
                    'symbol': item.get('symbol'),
                    'open_interest': float(item.get('openInterest', 0)),
                    'time': int(item.get('time', 0)),
                    'time_str': datetime.fromtimestamp(
                        int(item.get('time', 0)) / 1000, tz=timezone.utc
                    ).isoformat() if item.get('time') else None
                }
                formatted_data.append(formatted_item)
            return formatted_data
        else:
            # If single symbol response, wrap in list
            formatted_item = {
                'symbol': data.get('symbol'),
                'open_interest': float(data.get('openInterest', 0)),
                'time': int(data.get('time', 0)),
                'time_str': datetime.fromtimestamp(
                    int(data.get('time', 0)) / 1000, tz=timezone.utc
                ).isoformat() if data.get('time') else None
            }
            return [formatted_item]
    
    def fetch_historical_paginated(
        self,
        symbol: str,
        period: str,
        start_time: Union[int, str, datetime],
        end_time: Union[int, str, datetime],
        max_records: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical open interest data with automatic pagination.
        
        Args:
            symbol (str): Trading symbol
            period (str): Time interval
            start_time: Start time for data range
            end_time: End time for data range
            max_records (int, optional): Maximum total records to fetch
            
        Returns:
            List[Dict]: Complete historical open interest data
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        period = self._validate_interval(period)
        start_timestamp = self._validate_timestamp(start_time)
        end_timestamp = self._validate_timestamp(end_time)
        
        if start_timestamp >= end_timestamp:
            raise ValueError("start_time must be before end_time")
        
        all_data = []
        current_start = start_timestamp
        total_fetched = 0
        
        logger.info(f"Starting paginated fetch for {symbol} open interest data")
        
        while current_start < end_timestamp:
            # Determine limit for this request
            remaining_records = None
            if max_records is not None:
                remaining_records = max_records - total_fetched
                if remaining_records <= 0:
                    break
                    
            current_limit = min(self.MAX_LIMIT, remaining_records or self.MAX_LIMIT)
            
            # Fetch batch
            batch_data = self.fetch_historical_open_interest(
                symbol=symbol,
                period=period,
                start_time=current_start,
                end_time=end_timestamp,
                limit=current_limit
            )
            
            if not batch_data:
                logger.info("No more data available")
                break
                
            all_data.extend(batch_data)
            total_fetched += len(batch_data)
            
            # Update start time for next batch
            last_timestamp = batch_data[-1]['timestamp']
            current_start = last_timestamp + 1  # Start from next millisecond
            
            logger.info(f"Fetched {len(batch_data)} records. Total: {total_fetched}")
            
            # Check if we got less than expected (end of available data)
            if len(batch_data) < current_limit:
                logger.info("Reached end of available data")
                break
        
        logger.info(f"Completed paginated fetch. Total records: {len(all_data)}")
        return all_data


# Convenience functions for quick usage
def fetch_current_open_interest(symbol: str) -> Dict[str, Any]:
    """
    Quick function to fetch current open interest for a symbol.
    
    Args:
        symbol (str): Trading symbol
        
    Returns:
        Dict: Current open interest data
    """
    fetcher = BinanceOpenInterestFetcher()
    return fetcher.fetch_current_open_interest(symbol)


def fetch_historical_open_interest(
    symbol: str,
    period: str,
    start_time: Optional[Union[int, str, datetime]] = None,
    end_time: Optional[Union[int, str, datetime]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Quick function to fetch historical open interest data.
    
    Args:
        symbol (str): Trading symbol
        period (str): Time interval
        start_time: Start time for data range
        end_time: End time for data range
        limit (int, optional): Maximum number of records
        
    Returns:
        List[Dict]: Historical open interest data
    """
    fetcher = BinanceOpenInterestFetcher()
    return fetcher.fetch_historical_open_interest(symbol, period, start_time, end_time, limit)


def fetch_all_open_interest() -> List[Dict[str, Any]]:
    """
    Quick function to fetch current open interest for all symbols.
    
    Returns:
        List[Dict]: Open interest data for all symbols
    """
    fetcher = BinanceOpenInterestFetcher()
    return fetcher.fetch_all_open_interest()