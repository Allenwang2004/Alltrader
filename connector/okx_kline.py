"""
OKX Kline Data Fetcher

This module provides functionality to fetch kline (candlestick) data from OKX exchange.
OKX supports spot and futures markets with comprehensive kline data.

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


class OKXKlineError(Exception):
    """Custom exception for OKX kline fetching errors"""
    pass


class OKXKlineFetcher:
    """
    A class to fetch kline data from OKX spot and futures markets.

    This class handles API requests to OKX to retrieve candlestick data
    for specified symbols within given time ranges.
    """

    # OKX API endpoints
    BASE_URL = "https://www.okx.com"

    # API endpoints
    SPOT_KLINES_ENDPOINT = "/api/v5/market/candles"
    FUTURES_KLINES_ENDPOINT = "/api/v5/market/candles"  # Same endpoint for futures

    # Valid intervals for kline data (OKX format)
    VALID_INTERVALS = [
        "1s", "1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "6H", "12H",
        "1D", "2D", "3D", "1W", "1M", "3M"
    ]

    # Maximum limit per request (OKX limit)
    MAX_LIMIT = 300

    def __init__(self, market_type: str = "spot", request_delay: float = 0.1):
        """
        Initialize the OKXKlineFetcher.

        Args:
            market_type (str): Market type, either "spot" or "futures"
            request_delay (float): Delay between requests in seconds to avoid rate limiting
        """
        if market_type not in ["spot", "futures"]:
            raise ValueError("market_type must be 'spot' or 'futures'")

        self.market_type = market_type
        self.request_delay = request_delay
        self.base_url = self.BASE_URL
        self.session = requests.Session()

    def _validate_symbol(self, symbol: str) -> str:
        """
        Validate and format symbol.

        Args:
            symbol (str): Trading symbol (e.g., 'BTC-USDT')

        Returns:
            str: Formatted symbol in OKX format (with hyphen)

        Raises:
            ValueError: If symbol is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Symbol must be a non-empty string")

        symbol = symbol.upper().strip()

        # OKX uses hyphen format (BTC-USDT), convert from underscore if needed
        symbol = symbol.replace('_', '-')

        # Ensure it has exactly one hyphen
        if symbol.count('-') != 1:
            raise ValueError("Symbol must be in format 'BASE-QUOTE' (e.g., 'BTC-USDT')")

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

    def _validate_timestamp(self, timestamp: Union[int, str, datetime]) -> str:
        """
        Convert and validate timestamp for OKX API.

        OKX expects timestamps in ISO 8601 format with milliseconds.

        Args:
            timestamp: Timestamp in various formats

        Returns:
            str: ISO 8601 timestamp string with milliseconds

        Raises:
            ValueError: If timestamp is invalid
        """
        if isinstance(timestamp, datetime):
            # Convert to UTC and format as ISO 8601 with milliseconds
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        elif isinstance(timestamp, str):
            try:
                # Try to parse various formats
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                raise ValueError(f"Invalid datetime string format: {timestamp}")
        elif isinstance(timestamp, (int, float)):
            # Assume it's in milliseconds, convert to seconds
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        else:
            raise ValueError("Timestamp must be datetime, string, or numeric")

    def _make_request(self, params: Dict[str, Any]) -> List[List]:
        """
        Make API request to OKX.

        Args:
            params (dict): Request parameters

        Returns:
            List[List]: Raw kline data from OKX API

        Raises:
            OKXKlineError: If API request fails
        """
        url = f"{self.base_url}{self.SPOT_KLINES_ENDPOINT}"

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Check OKX API response format
            if data.get('code') != '0':
                raise OKXKlineError(f"OKX API Error {data.get('code')}: {data.get('msg', 'Unknown error')}")

            kline_data = data.get('data', [])
            if not isinstance(kline_data, list):
                raise OKXKlineError(f"Unexpected response format: {data}")

            return kline_data

        except requests.exceptions.RequestException as e:
            raise OKXKlineError(f"API request failed: {str(e)}")
        except ValueError as e:
            raise OKXKlineError(f"Invalid JSON response: {str(e)}")

    def _format_kline_data(self, raw_data: List[List]) -> List[Dict[str, Any]]:
        """
        Format raw kline data into structured dictionaries.

        OKX kline format: [timestamp, open, high, low, close, volume, volumeCcy, volumeCcyQuote, confirm]

        Args:
            raw_data (List[List]): Raw kline data from OKX API

        Returns:
            List[Dict]: Formatted kline data
        """
        formatted_data = []

        for kline in raw_data:
            if len(kline) < 9:
                continue  # Skip incomplete data

            formatted_kline = {
                'timestamp': int(kline[0]),
                'open_price': float(kline[1]),
                'high_price': float(kline[2]),
                'low_price': float(kline[3]),
                'close_price': float(kline[4]),
                'volume': float(kline[5]),
                'volume_ccy': float(kline[6]),
                'volume_ccy_quote': float(kline[7]),
                'confirm': kline[8]  # Confirmation status
            }

            # Add human-readable timestamps
            formatted_kline['timestamp_str'] = datetime.fromtimestamp(
                formatted_kline['timestamp'] / 1000, tz=timezone.utc
            ).isoformat()

            formatted_data.append(formatted_kline)

        return formatted_data

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        before: Optional[Union[int, str, datetime]] = None,
        after: Optional[Union[int, str, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch kline data for a specific symbol and time range.

        Args:
            symbol (str): Trading symbol (e.g., 'BTC-USDT')
            interval (str): Kline interval (e.g., '1m', '1H', '1D')
            before: End time for data range (timestamp before this time)
            after: Start time for data range (timestamp after this time)
            limit (int, optional): Maximum number of klines to return

        Returns:
            List[Dict]: List of kline data dictionaries

        Raises:
            ValueError: If parameters are invalid
            OKXKlineError: If API request fails
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        interval = self._validate_interval(interval)

        # Prepare parameters
        params = {
            'instId': symbol,
            'bar': interval
        }

        if before is not None:
            params['before'] = self._validate_timestamp(before)

        if after is not None:
            params['after'] = self._validate_timestamp(after)

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
        would exceed OKX's maximum limit per request.

        Args:
            symbol (str): Trading symbol (e.g., 'BTC-USDT')
            interval (str): Kline interval (e.g., '1m', '1H', '1D')
            start_time: Start time for data range
            end_time: End time for data range
            max_records (int, optional): Maximum total records to fetch

        Returns:
            List[Dict]: Complete list of kline data

        Raises:
            ValueError: If parameters are invalid
            OKXKlineError: If API request fails
        """
        # Validate inputs
        symbol = self._validate_symbol(symbol)
        interval = self._validate_interval(interval)
        start_timestamp = self._validate_timestamp(start_time)
        end_timestamp = self._validate_timestamp(end_time)

        # Convert to datetime for comparison
        start_dt = datetime.fromisoformat(start_timestamp.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_timestamp.replace('Z', '+00:00'))

        if start_dt >= end_dt:
            raise ValueError("start_time must be before end_time")

        all_klines = []
        current_after = start_timestamp  # OKX uses 'after' for pagination
        total_fetched = 0

        logger.info(f"Starting paginated fetch for {symbol} from "
                   f"{start_dt} to {end_dt}")

        while current_after < end_timestamp:
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
                after=current_after,
                before=end_timestamp,
                limit=current_limit
            )

            if not batch_klines:
                logger.info("No more data available")
                break

            all_klines.extend(batch_klines)
            total_fetched += len(batch_klines)

            # Update pagination cursor (use the last timestamp as new after)
            last_timestamp = batch_klines[-1]['timestamp']
            current_after = self._validate_timestamp(
                datetime.fromtimestamp(last_timestamp / 1000, tz=timezone.utc)
            )

            logger.info(f"Fetched {len(batch_klines)} klines. Total: {total_fetched}")

            # Check if we got less than expected (end of available data)
            if len(batch_klines) < current_limit:
                logger.info("Reached end of available data")
                break

        logger.info(f"Completed paginated fetch. Total records: {len(all_klines)}")
        return all_klines


def create_spot_fetcher(request_delay: float = 0.1) -> OKXKlineFetcher:
    """
    Create an OKXKlineFetcher for spot market.

    Args:
        request_delay (float): Delay between requests

    Returns:
        OKXKlineFetcher: Configured for spot market
    """
    return OKXKlineFetcher(market_type="spot", request_delay=request_delay)


def create_futures_fetcher(request_delay: float = 0.1) -> OKXKlineFetcher:
    """
    Create an OKXKlineFetcher for futures market.

    Args:
        request_delay (float): Delay between requests

    Returns:
        OKXKlineFetcher: Configured for futures market
    """
    return OKXKlineFetcher(market_type="futures", request_delay=request_delay)


# Convenience functions for quick usage
def fetch_spot_klines(
    symbol: str,
    interval: str,
    before: Optional[Union[int, str, datetime]] = None,
    after: Optional[Union[int, str, datetime]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Quick function to fetch spot klines.

    Args:
        symbol (str): Trading symbol (e.g., 'BTC-USDT')
        interval (str): Kline interval (e.g., '1m', '1H', '1D')
        before: End time for data range
        after: Start time for data range
        limit (int, optional): Maximum number of klines

    Returns:
        List[Dict]: Kline data
    """
    fetcher = create_spot_fetcher()
    return fetcher.fetch_klines(symbol, interval, before, after, limit)


def fetch_futures_klines(
    symbol: str,
    interval: str,
    before: Optional[Union[int, str, datetime]] = None,
    after: Optional[Union[int, str, datetime]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Quick function to fetch futures klines.

    Args:
        symbol (str): Trading symbol (e.g., 'BTC-USDT')
        interval (str): Kline interval (e.g., '1m', '1H', '1D')
        before: End time for data range
        after: Start time for data range
        limit (int, optional): Maximum number of klines

    Returns:
        List[Dict]: Kline data
    """
    fetcher = create_futures_fetcher()
    return fetcher.fetch_klines(symbol, interval, before, after, limit)