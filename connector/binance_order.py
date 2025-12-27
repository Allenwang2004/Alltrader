"""
Binance Order Management Module

This module provides functionality to place orders on Binance spot and futures markets.
It includes proper HMAC SHA256 signature generation for authenticated API requests.

Features:
- Spot and futures market order placement
- HMAC SHA256 signature generation
- Support for various order types (LIMIT, MARKET, STOP_LOSS, etc.)
- Order cancellation and query functionality
- Position management for futures
- Input validation and error handling

Security Notice:
- Never hardcode API keys in your code
- Use environment variables or secure configuration files
- Keep your API secret key confidential
"""

import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union, Literal
from enum import Enum
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Order side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class FuturesOrderType(str, Enum):
    """Futures order type enumeration"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class TimeInForce(str, Enum):
    """Time in force enumeration"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTX = "GTX"  # Good Till Crossing (Post Only)


class PositionSide(str, Enum):
    """Position side for futures (hedge mode)"""
    BOTH = "BOTH"  # One-way mode
    LONG = "LONG"  # Hedge mode long
    SHORT = "SHORT"  # Hedge mode short


class BinanceOrderError(Exception):
    """Custom exception for Binance order errors"""
    def __init__(self, message: str, code: int = None, response: Dict = None):
        self.message = message
        self.code = code
        self.response = response
        super().__init__(self.message)


class BinanceOrderClient:
    """
    A client for placing orders on Binance spot and futures markets.
    
    This class handles API authentication using HMAC SHA256 signatures
    and provides methods for various order operations.
    """
    
    # Binance API endpoints
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"
    
    # Testnet endpoints (for testing without real money)
    SPOT_TESTNET_URL = "https://testnet.binance.vision"
    FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"
    
    # API endpoints
    SPOT_ORDER_ENDPOINT = "/api/v3/order"
    SPOT_ACCOUNT_ENDPOINT = "/api/v3/account"
    SPOT_OPEN_ORDERS_ENDPOINT = "/api/v3/openOrders"
    
    FUTURES_ORDER_ENDPOINT = "/fapi/v1/order"
    FUTURES_ACCOUNT_ENDPOINT = "/fapi/v2/account"
    FUTURES_POSITION_ENDPOINT = "/fapi/v2/positionRisk"
    FUTURES_OPEN_ORDERS_ENDPOINT = "/fapi/v1/openOrders"
    FUTURES_LEVERAGE_ENDPOINT = "/fapi/v1/leverage"
    FUTURES_MARGIN_TYPE_ENDPOINT = "/fapi/v1/marginType"
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        market_type: str = "futures",
        testnet: bool = False,
        recv_window: int = 5000
    ):
        """
        Initialize the BinanceOrderClient.
        
        Args:
            api_key (str): Binance API key. If None, reads from BINANCE_API_KEY env var
            api_secret (str): Binance API secret. If None, reads from BINANCE_API_SECRET env var
            market_type (str): Market type, either "spot" or "futures"
            testnet (bool): Whether to use testnet (for testing without real money)
            recv_window (int): Request validity window in milliseconds
        """
        # Get API credentials from parameters or environment variables
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "API key and secret are required. "
                "Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables "
                "or pass them as parameters."
            )
        
        if market_type not in ["spot", "futures"]:
            raise ValueError("market_type must be 'spot' or 'futures'")
            
        self.market_type = market_type
        self.testnet = testnet
        self.recv_window = recv_window
        
        # Set base URL based on market type and testnet setting
        if market_type == "spot":
            self.base_url = self.SPOT_TESTNET_URL if testnet else self.SPOT_BASE_URL
        else:
            self.base_url = self.FUTURES_TESTNET_URL if testnet else self.FUTURES_BASE_URL
            
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key
        })
        
        logger.info(f"Initialized BinanceOrderClient for {market_type} market"
                   f"{' (testnet)' if testnet else ''}")
    
    def _get_timestamp(self) -> int:
        """
        Get current timestamp in milliseconds.
        
        Returns:
            int: Current timestamp in milliseconds
        """
        return int(time.time() * 1000)
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for API request.
        
        This is the core authentication mechanism for Binance API.
        The signature is created by signing the query string with the API secret.
        
        Args:
            params (Dict): Request parameters
            
        Returns:
            str: HMAC SHA256 signature in hexadecimal format
        """
        # Create query string from parameters
        query_string = urlencode(params)
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _make_signed_request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make a signed API request to Binance.
        
        Args:
            method (str): HTTP method (GET, POST, DELETE)
            endpoint (str): API endpoint
            params (Dict): Request parameters
            
        Returns:
            Dict: Response data from Binance API
            
        Raises:
            BinanceOrderError: If API request fails
        """
        params = params or {}
        
        # Add timestamp and recvWindow
        params['timestamp'] = self._get_timestamp()
        params['recvWindow'] = self.recv_window
        
        # Generate signature
        params['signature'] = self._generate_signature(params)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = self.session.post(url, params=params, timeout=30)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            data = response.json()
            
            # Check for API errors
            if response.status_code != 200:
                error_code = data.get('code', response.status_code)
                error_msg = data.get('msg', 'Unknown error')
                raise BinanceOrderError(
                    f"API Error {error_code}: {error_msg}",
                    code=error_code,
                    response=data
                )
            
            return data
            
        except requests.exceptions.RequestException as e:
            raise BinanceOrderError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise BinanceOrderError(f"Invalid JSON response: {str(e)}")
    
    def _validate_symbol(self, symbol: str) -> str:
        """Validate and format symbol."""
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Symbol must be a non-empty string")
        return symbol.upper().strip()
    
    # ==================== SPOT MARKET ORDERS ====================
    
    def place_spot_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        order_type: Union[str, OrderType],
        quantity: Optional[float] = None,
        quote_order_qty: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[Union[str, TimeInForce]] = None,
        stop_price: Optional[float] = None,
        new_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a spot market order.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            side (str): Order side ('BUY' or 'SELL')
            order_type (str): Order type ('LIMIT', 'MARKET', etc.)
            quantity (float): Order quantity in base asset
            quote_order_qty (float): Order quantity in quote asset (for MARKET orders)
            price (float): Order price (required for LIMIT orders)
            time_in_force (str): Time in force ('GTC', 'IOC', 'FOK')
            stop_price (float): Stop price for stop orders
            new_client_order_id (str): Custom order ID
            
        Returns:
            Dict: Order response from Binance
        """
        if self.market_type != "spot":
            raise ValueError("This client is configured for futures market. "
                           "Use place_futures_order() instead.")
        
        # Validate and convert enums
        symbol = self._validate_symbol(symbol)
        side = side.value if isinstance(side, OrderSide) else side.upper()
        order_type = order_type.value if isinstance(order_type, OrderType) else order_type.upper()
        
        # Build parameters
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type
        }
        
        if quantity is not None:
            params['quantity'] = str(quantity)
            
        if quote_order_qty is not None:
            params['quoteOrderQty'] = str(quote_order_qty)
            
        if price is not None:
            params['price'] = str(price)
            
        if time_in_force is not None:
            tif = time_in_force.value if isinstance(time_in_force, TimeInForce) else time_in_force
            params['timeInForce'] = tif
            
        if stop_price is not None:
            params['stopPrice'] = str(stop_price)
            
        if new_client_order_id is not None:
            params['newClientOrderId'] = new_client_order_id
        
        logger.info(f"Placing spot {side} {order_type} order for {symbol}")
        
        return self._make_signed_request("POST", self.SPOT_ORDER_ENDPOINT, params)
    
    def place_spot_market_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: float
    ) -> Dict[str, Any]:
        """
        Convenience method to place a spot market order.
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side ('BUY' or 'SELL')
            quantity (float): Order quantity
            
        Returns:
            Dict: Order response
        """
        return self.place_spot_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity
        )
    
    def place_spot_limit_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: float,
        price: float,
        time_in_force: Union[str, TimeInForce] = TimeInForce.GTC
    ) -> Dict[str, Any]:
        """
        Convenience method to place a spot limit order.
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side ('BUY' or 'SELL')
            quantity (float): Order quantity
            price (float): Limit price
            time_in_force (str): Time in force
            
        Returns:
            Dict: Order response
        """
        return self.place_spot_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force
        )
    
    # ==================== FUTURES MARKET ORDERS ====================
    
    def place_futures_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        order_type: Union[str, FuturesOrderType],
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[Union[str, TimeInForce]] = None,
        position_side: Optional[Union[str, PositionSide]] = None,
        reduce_only: Optional[bool] = None,
        stop_price: Optional[float] = None,
        close_position: Optional[bool] = None,
        activation_price: Optional[float] = None,
        callback_rate: Optional[float] = None,
        working_type: Optional[str] = None,
        new_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a futures market order.
        
        Args:
            symbol (str): Trading symbol (e.g., 'BTCUSDT')
            side (str): Order side ('BUY' or 'SELL')
            order_type (str): Order type ('LIMIT', 'MARKET', 'STOP', etc.)
            quantity (float): Order quantity
            price (float): Order price (required for LIMIT orders)
            time_in_force (str): Time in force ('GTC', 'IOC', 'FOK', 'GTX')
            position_side (str): Position side for hedge mode ('BOTH', 'LONG', 'SHORT')
            reduce_only (bool): Reduce only flag
            stop_price (float): Stop price for stop orders
            close_position (bool): Close all positions
            activation_price (float): Activation price for trailing stop
            callback_rate (float): Callback rate for trailing stop
            working_type (str): Stop price working type ('MARK_PRICE' or 'CONTRACT_PRICE')
            new_client_order_id (str): Custom order ID
            
        Returns:
            Dict: Order response from Binance
        """
        if self.market_type != "futures":
            raise ValueError("This client is configured for spot market. "
                           "Use place_spot_order() instead.")
        
        # Validate and convert enums
        symbol = self._validate_symbol(symbol)
        side = side.value if isinstance(side, OrderSide) else side.upper()
        order_type = order_type.value if isinstance(order_type, FuturesOrderType) else order_type.upper()
        
        # Build parameters
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type
        }
        
        if quantity is not None:
            params['quantity'] = str(quantity)
            
        if price is not None:
            params['price'] = str(price)
            
        if time_in_force is not None:
            tif = time_in_force.value if isinstance(time_in_force, TimeInForce) else time_in_force
            params['timeInForce'] = tif
            
        if position_side is not None:
            ps = position_side.value if isinstance(position_side, PositionSide) else position_side
            params['positionSide'] = ps
            
        if reduce_only is not None:
            params['reduceOnly'] = str(reduce_only).lower()
            
        if stop_price is not None:
            params['stopPrice'] = str(stop_price)
            
        if close_position is not None:
            params['closePosition'] = str(close_position).lower()
            
        if activation_price is not None:
            params['activationPrice'] = str(activation_price)
            
        if callback_rate is not None:
            params['callbackRate'] = str(callback_rate)
            
        if working_type is not None:
            params['workingType'] = working_type
            
        if new_client_order_id is not None:
            params['newClientOrderId'] = new_client_order_id
        
        logger.info(f"Placing futures {side} {order_type} order for {symbol}")
        
        return self._make_signed_request("POST", self.FUTURES_ORDER_ENDPOINT, params)
    
    def place_futures_market_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: float,
        position_side: Union[str, PositionSide] = PositionSide.BOTH,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience method to place a futures market order.
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side ('BUY' or 'SELL')
            quantity (float): Order quantity
            position_side (str): Position side for hedge mode
            reduce_only (bool): Reduce only flag
            
        Returns:
            Dict: Order response
        """
        return self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.MARKET,
            quantity=quantity,
            position_side=position_side,
            reduce_only=reduce_only
        )
    
    def place_futures_limit_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: float,
        price: float,
        time_in_force: Union[str, TimeInForce] = TimeInForce.GTC,
        position_side: Union[str, PositionSide] = PositionSide.BOTH,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience method to place a futures limit order.
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side ('BUY' or 'SELL')
            quantity (float): Order quantity
            price (float): Limit price
            time_in_force (str): Time in force
            position_side (str): Position side for hedge mode
            reduce_only (bool): Reduce only flag
            
        Returns:
            Dict: Order response
        """
        return self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.LIMIT,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            position_side=position_side,
            reduce_only=reduce_only
        )
    
    def place_futures_stop_market_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: float,
        stop_price: float,
        position_side: Union[str, PositionSide] = PositionSide.BOTH,
        reduce_only: bool = True,
        working_type: str = "MARK_PRICE"
    ) -> Dict[str, Any]:
        """
        Place a futures stop market order (stop loss).
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side ('BUY' or 'SELL')
            quantity (float): Order quantity
            stop_price (float): Stop trigger price
            position_side (str): Position side for hedge mode
            reduce_only (bool): Reduce only flag (default True for stop loss)
            working_type (str): Price type for stop trigger
            
        Returns:
            Dict: Order response
        """
        return self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.STOP_MARKET,
            quantity=quantity,
            stop_price=stop_price,
            position_side=position_side,
            reduce_only=reduce_only,
            working_type=working_type
        )
    
    def place_futures_take_profit_market_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: float,
        stop_price: float,
        position_side: Union[str, PositionSide] = PositionSide.BOTH,
        reduce_only: bool = True,
        working_type: str = "MARK_PRICE"
    ) -> Dict[str, Any]:
        """
        Place a futures take profit market order.
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side ('BUY' or 'SELL')
            quantity (float): Order quantity
            stop_price (float): Take profit trigger price
            position_side (str): Position side for hedge mode
            reduce_only (bool): Reduce only flag
            working_type (str): Price type for trigger
            
        Returns:
            Dict: Order response
        """
        return self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.TAKE_PROFIT_MARKET,
            quantity=quantity,
            stop_price=stop_price,
            position_side=position_side,
            reduce_only=reduce_only,
            working_type=working_type
        )
    
    # ==================== ORDER MANAGEMENT ====================
    
    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel an active order.
        
        Args:
            symbol (str): Trading symbol
            order_id (int): Order ID
            orig_client_order_id (str): Original client order ID
            
        Returns:
            Dict: Cancellation response
        """
        symbol = self._validate_symbol(symbol)
        
        if order_id is None and orig_client_order_id is None:
            raise ValueError("Either order_id or orig_client_order_id is required")
        
        params = {'symbol': symbol}
        
        if order_id is not None:
            params['orderId'] = order_id
        if orig_client_order_id is not None:
            params['origClientOrderId'] = orig_client_order_id
        
        endpoint = (self.SPOT_ORDER_ENDPOINT if self.market_type == "spot" 
                   else self.FUTURES_ORDER_ENDPOINT)
        
        logger.info(f"Cancelling order for {symbol}")
        
        return self._make_signed_request("DELETE", endpoint, params)
    
    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol (str): Trading symbol
            
        Returns:
            Dict: Cancellation response
        """
        symbol = self._validate_symbol(symbol)
        params = {'symbol': symbol}
        
        endpoint = (self.SPOT_OPEN_ORDERS_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_OPEN_ORDERS_ENDPOINT)
        
        logger.info(f"Cancelling all open orders for {symbol}")
        
        return self._make_signed_request("DELETE", endpoint, params)
    
    def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get order information.
        
        Args:
            symbol (str): Trading symbol
            order_id (int): Order ID
            orig_client_order_id (str): Original client order ID
            
        Returns:
            Dict: Order information
        """
        symbol = self._validate_symbol(symbol)
        
        if order_id is None and orig_client_order_id is None:
            raise ValueError("Either order_id or orig_client_order_id is required")
        
        params = {'symbol': symbol}
        
        if order_id is not None:
            params['orderId'] = order_id
        if orig_client_order_id is not None:
            params['origClientOrderId'] = orig_client_order_id
        
        endpoint = (self.SPOT_ORDER_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_ORDER_ENDPOINT)
        
        return self._make_signed_request("GET", endpoint, params)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Args:
            symbol (str, optional): Trading symbol (if None, returns all symbols)
            
        Returns:
            List[Dict]: List of open orders
        """
        params = {}
        if symbol is not None:
            params['symbol'] = self._validate_symbol(symbol)
        
        endpoint = (self.SPOT_OPEN_ORDERS_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_OPEN_ORDERS_ENDPOINT)
        
        return self._make_signed_request("GET", endpoint, params)
    
    # ==================== ACCOUNT & POSITION ====================
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict: Account information including balances
        """
        endpoint = (self.SPOT_ACCOUNT_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_ACCOUNT_ENDPOINT)
        
        return self._make_signed_request("GET", endpoint, {})
    
    def get_futures_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get futures positions.
        
        Args:
            symbol (str, optional): Trading symbol
            
        Returns:
            List[Dict]: List of positions
        """
        if self.market_type != "futures":
            raise ValueError("This method is only available for futures market")
        
        params = {}
        if symbol is not None:
            params['symbol'] = self._validate_symbol(symbol)
        
        return self._make_signed_request("GET", self.FUTURES_POSITION_ENDPOINT, params)
    
    def set_futures_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a futures symbol.
        
        Args:
            symbol (str): Trading symbol
            leverage (int): Leverage (1-125)
            
        Returns:
            Dict: Leverage update response
        """
        if self.market_type != "futures":
            raise ValueError("This method is only available for futures market")
        
        symbol = self._validate_symbol(symbol)
        
        if not 1 <= leverage <= 125:
            raise ValueError("Leverage must be between 1 and 125")
        
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        
        logger.info(f"Setting leverage for {symbol} to {leverage}x")
        
        return self._make_signed_request("POST", self.FUTURES_LEVERAGE_ENDPOINT, params)
    
    def set_futures_margin_type(
        self,
        symbol: str,
        margin_type: Literal["ISOLATED", "CROSSED"]
    ) -> Dict[str, Any]:
        """
        Set margin type for a futures symbol.
        
        Args:
            symbol (str): Trading symbol
            margin_type (str): Margin type ('ISOLATED' or 'CROSSED')
            
        Returns:
            Dict: Margin type update response
        """
        if self.market_type != "futures":
            raise ValueError("This method is only available for futures market")
        
        symbol = self._validate_symbol(symbol)
        
        if margin_type not in ["ISOLATED", "CROSSED"]:
            raise ValueError("margin_type must be 'ISOLATED' or 'CROSSED'")
        
        params = {
            'symbol': symbol,
            'marginType': margin_type
        }
        
        logger.info(f"Setting margin type for {symbol} to {margin_type}")
        
        return self._make_signed_request("POST", self.FUTURES_MARGIN_TYPE_ENDPOINT, params)


# ==================== CONVENIENCE FUNCTIONS ====================

def create_spot_client(
    api_key: str = None,
    api_secret: str = None,
    testnet: bool = False
) -> BinanceOrderClient:
    """
    Create a spot market order client.
    
    Args:
        api_key (str): API key (or use BINANCE_API_KEY env var)
        api_secret (str): API secret (or use BINANCE_API_SECRET env var)
        testnet (bool): Use testnet
        
    Returns:
        BinanceOrderClient: Configured for spot market
    """
    return BinanceOrderClient(
        api_key=api_key,
        api_secret=api_secret,
        market_type="spot",
        testnet=testnet
    )


def create_futures_client(
    api_key: str = None,
    api_secret: str = None,
    testnet: bool = False
) -> BinanceOrderClient:
    """
    Create a futures market order client.
    
    Args:
        api_key (str): API key (or use BINANCE_API_KEY env var)
        api_secret (str): API secret (or use BINANCE_API_SECRET env var)
        testnet (bool): Use testnet
        
    Returns:
        BinanceOrderClient: Configured for futures market
    """
    return BinanceOrderClient(
        api_key=api_key,
        api_secret=api_secret,
        market_type="futures",
        testnet=testnet
    )