"""
OKX Order Management Module

This module provides functionality to place orders on OKX exchange.
It includes proper HMAC SHA256 signature generation for authenticated API requests.

Features:
- Spot and futures market order placement
- HMAC SHA256 signature generation with OKX format
- Support for various order types (LIMIT, MARKET, STOP_LOSS, etc.)
- Order cancellation and query functionality
- Position management for futures
- Input validation and error handling

Security Notice:
- Never hardcode API keys in your code
- Use environment variables or secure configuration files
- Keep your API secret key and passphrase confidential
"""

import os
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union, Literal
from enum import Enum
import logging
from dotenv import load_dotenv
from urllib.parse import urlencode

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Order side enumeration"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration for OKX"""
    LIMIT = "limit"
    MARKET = "market"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"


class FuturesOrderType(str, Enum):
    """Futures order type enumeration for OKX"""
    LIMIT = "limit"
    MARKET = "market"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"


class TimeInForce(str, Enum):
    """Time in force enumeration for OKX"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


class PositionSide(str, Enum):
    """Position side for futures (OKX hedge mode)"""
    LONG = "long"
    SHORT = "short"
    NET = "net"  # One-way mode


class OKXOrderError(Exception):
    """Custom exception for OKX order errors"""
    def __init__(self, message: str, code: str = None, response: Dict = None):
        self.message = message
        self.code = code
        self.response = response
        super().__init__(self.message)


class OKXOrderClient:
    """
    A client for placing orders on OKX spot and futures markets.

    This class handles API authentication using HMAC SHA256 signatures
    with OKX-specific format and provides methods for various order operations.
    """

    # OKX API endpoints
    BASE_URL = "https://www.okx.com"

    # API endpoints
    SPOT_ORDER_ENDPOINT = "/api/v5/trade/order"
    SPOT_CANCEL_ORDER_ENDPOINT = "/api/v5/trade/cancel-order"
    SPOT_AMEND_ORDER_ENDPOINT = "/api/v5/trade/amend-order"
    SPOT_ORDERS_PENDING_ENDPOINT = "/api/v5/trade/orders-pending"
    SPOT_ORDER_INFO_ENDPOINT = "/api/v5/trade/order"
    SPOT_ACCOUNT_ENDPOINT = "/api/v5/account/balance"

    FUTURES_ORDER_ENDPOINT = "/api/v5/trade/order"
    FUTURES_CANCEL_ORDER_ENDPOINT = "/api/v5/trade/cancel-order"
    FUTURES_AMEND_ORDER_ENDPOINT = "/api/v5/trade/amend-order"
    FUTURES_ORDERS_PENDING_ENDPOINT = "/api/v5/trade/orders-pending"
    FUTURES_ORDER_INFO_ENDPOINT = "/api/v5/trade/order"
    FUTURES_ACCOUNT_ENDPOINT = "/api/v5/account/balance"
    FUTURES_POSITION_ENDPOINT = "/api/v5/account/positions"
    FUTURES_LEVERAGE_ENDPOINT = "/api/v5/account/set-leverage"
    FUTURES_MARGIN_MODE_ENDPOINT = "/api/v5/account/set-margin-mode"
    FUTURES_INSTRUMENT_INFO_ENDPOINT = "/api/v5/account/instruments"
    FUTURES_POSITION_INFO_ENDPOINT = "/api/v5/account/positions"

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        passphrase: str = None,
        market_type: str = "futures",
        testnet: bool = False,
        recv_window: int = 5000
    ):
        """
        Initialize the OKXOrderClient.

        Args:
            api_key (str): OKX API key. If None, reads from OKX_API_KEY env var
            api_secret (str): OKX API secret. If None, reads from OKX_API_SECRET env var
            passphrase (str): OKX API passphrase. If None, reads from OKX_PASSPHRASE env var
            market_type (str): Market type, either "spot" or "futures"
            testnet (bool): Whether to use testnet (for testing without real money)
            recv_window (int): Request validity window in milliseconds
        """
        # Get API credentials from parameters or environment variables
        self.api_key = api_key or os.getenv("OKX_API_KEY")
        self.api_secret = api_secret or os.getenv("OKX_API_SECRET")
        self.passphrase = passphrase or os.getenv("OKX_PASSPHRASE")

        if not all([self.api_key, self.api_secret, self.passphrase]):
            raise ValueError(
                "API key, secret, and passphrase are required. "
                "Set OKX_API_KEY, OKX_API_SECRET, and OKX_PASSPHRASE environment variables "
                "or pass them as parameters."
            )

        if market_type not in ["spot", "futures"]:
            raise ValueError("market_type must be 'spot' or 'futures'")

        self.market_type = market_type
        self.testnet = testnet
        self.recv_window = recv_window

        # OKX uses the same base URL for both live and testnet
        # Testnet is handled via different API credentials
        self.base_url = self.BASE_URL

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-PASSPHRASE": self.passphrase
        })

        logger.info(f"Initialized OKXOrderClient for {market_type} market"
                   f"{' (testnet)' if testnet else ''}")

    def _get_timestamp(self) -> str:
        """
        Get current timestamp in OKX format (ISO 8601).

        Returns:
            str: Current timestamp in ISO 8601 format
        """
        # OKX expects ISO8601 UTC timestamp with milliseconds, e.g. 2025-12-28T14:30:12.345Z
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _generate_signature(self, timestamp: str, method: str, endpoint: str, body: str = "") -> str:
        """
        Generate HMAC SHA256 signature for OKX API request.

        OKX signature format: base64(hmac_sha256(secret, message))
        Message format: timestamp + method + endpoint + body

        Args:
            timestamp (str): Request timestamp
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            body (str): Request body (for POST requests)

        Returns:
            str: Base64 encoded HMAC SHA256 signature
        """
        message = timestamp + method.upper() + endpoint + body

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()

        return base64.b64encode(signature).decode('utf-8')

    def _make_signed_request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make a signed API request to OKX.

        Args:
            method (str): HTTP method (GET, POST, DELETE)
            endpoint (str): API endpoint
            params (Dict): URL parameters
            data (Dict): Request body data

        Returns:
            Dict: Response data from OKX API

        Raises:
            OKXOrderError: If API request fails
        """
        timestamp = self._get_timestamp()

        # Prepare request body
        body = ""
        if data:
            import json
            body = json.dumps(data, separators=(',', ':'))

        # Build request path (endpoint + optional query string) for signature
        query = ""
        if params:
            # OKX signature requires the exact query string included in the request path.
            # Use URL encoding and a stable order.
            query = urlencode(sorted(params.items()), doseq=True)

        request_path = endpoint + (f"?{query}" if query else "")

        # Generate signature (NOTE: must sign request_path, not just endpoint)
        signature = self._generate_signature(timestamp, method, request_path, body)

        # Update headers
        self.session.headers.update({
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp
        })

        url = f"{self.base_url}{request_path}"

        try:
            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, data=body)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, data=body)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            data = response.json()

            # Check OKX API response format
            if data.get('code') != '0':
                error_code = data.get('code', str(response.status_code))
                error_msg = data.get('msg', 'Unknown error')
                raise OKXOrderError(
                    f"OKX API Error {error_code}: {error_msg}",
                    code=error_code,
                    response=data
                )

            return data

        except requests.exceptions.RequestException as e:
            raise OKXOrderError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise OKXOrderError(f"Invalid JSON response: {str(e)}")

    def _validate_symbol(self, symbol: str) -> str:
        """Validate and format symbol for OKX."""
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Symbol must be a non-empty string")
        symbol = symbol.upper().strip()
        # OKX uses hyphen format (BTC-USDT)
        symbol = symbol.replace('_', '-')
        if symbol.count('-') != 1:
            raise ValueError("Symbol must be in format 'BASE-QUOTE' (e.g., 'BTC-USDT')")
        # Ensure both base and quote parts are non-empty
        base, quote = symbol.split('-')
        if not base or not quote:
            raise ValueError("Symbol must be in format 'BASE-QUOTE' (e.g., 'BTC-USDT')")
        return symbol

    def _get_inst_type(self) -> str:
        """Get instrument type based on market type."""
        return "SPOT" if self.market_type == "spot" else "SWAP"

    def _get_inst_id(self, symbol: str) -> str:
        """Get instrument ID for OKX."""
        symbol = self._validate_symbol(symbol)
        if self.market_type == "spot":
            return symbol
        else:
            # For futures, OKX uses format like BTC-USDT-SWAP
            return f"{symbol}-SWAP"

    # ==================== SPOT MARKET ORDERS ====================

    def place_spot_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        order_type: Union[str, OrderType],
        size: Union[str, float],
        price: Optional[Union[str, float]] = None,
        time_in_force: Optional[Union[str, TimeInForce]] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a spot market order.

        Args:
            symbol (str): Trading symbol (e.g., 'BTC-USDT')
            side (str): Order side ('buy' or 'sell')
            order_type (str): Order type ('limit', 'market', 'post_only', 'fok', 'ioc')
            size (str/float): Order size in base currency
            price (str/float): Order price (required for limit orders)
            time_in_force (str): Time in force ('GTC', 'IOC', 'FOK')
            client_order_id (str): Custom order ID

        Returns:
            Dict: Order response from OKX
        """
        if self.market_type != "spot":
            raise ValueError("This client is configured for futures market. "
                           "Use place_futures_order() instead.")

        symbol = self._validate_symbol(symbol)
        side = side.value if isinstance(side, OrderSide) else side.lower()
        order_type = order_type.value if isinstance(order_type, OrderType) else order_type.lower()

        # Build request data
        data = {
            "instId": symbol,
            "tdMode": "cash",  # Spot trading
            "side": side,
            "ordType": order_type,
            "sz": str(size)
        }

        if price is not None:
            data["px"] = str(price)

        if time_in_force is not None:
            tif = time_in_force.value if isinstance(time_in_force, TimeInForce) else time_in_force
            data["tif"] = tif

        if client_order_id is not None:
            data["clOrdId"] = client_order_id

        logger.info(f"Placing spot {side} {order_type} order for {symbol}")

        return self._make_signed_request("POST", self.SPOT_ORDER_ENDPOINT, data=data)

    def place_spot_market_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        size: Union[str, float]
    ) -> Dict[str, Any]:
        """
        Convenience method to place a spot market order.

        Args:
            symbol (str): Trading symbol
            side (str): Order side ('buy' or 'sell')
            size (str/float): Order size

        Returns:
            Dict: Order response
        """
        return self.place_spot_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            size=size
        )

    def place_spot_limit_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        size: Union[str, float],
        price: Union[str, float],
        time_in_force: Union[str, TimeInForce] = TimeInForce.GTC
    ) -> Dict[str, Any]:
        """
        Convenience method to place a spot limit order.

        Args:
            symbol (str): Trading symbol
            side (str): Order side ('buy' or 'sell')
            size (str/float): Order size
            price (str/float): Limit price
            time_in_force (str): Time in force

        Returns:
            Dict: Order response
        """
        return self.place_spot_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            size=size,
            price=price,
            time_in_force=time_in_force
        )

    # ==================== FUTURES MARKET ORDERS ====================

    def place_futures_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        order_type: Union[str, FuturesOrderType],
        size: Union[str, float],
        price: Optional[Union[str, float]] = None,
        time_in_force: Optional[Union[str, TimeInForce]] = None,
        position_side: Optional[Union[str, PositionSide]] = None,
        reduce_only: Optional[bool] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a futures market order.

        Args:
            symbol (str): Trading symbol (e.g., 'BTC-USDT')
            side (str): Order side ('buy' or 'sell')
            order_type (str): Order type ('limit', 'market', 'post_only', 'fok', 'ioc')
            size (str/float): Order size in contracts
            price (str/float): Order price (required for limit orders)
            time_in_force (str): Time in force ('GTC', 'IOC', 'FOK')
            position_side (str): Position side ('long', 'short', 'net')
            reduce_only (bool): Reduce only flag
            client_order_id (str): Custom order ID

        Returns:
            Dict: Order response from OKX
        """
        if self.market_type != "futures":
            raise ValueError("This client is configured for spot market. "
                           "Use place_spot_order() instead.")

        inst_id = self._get_inst_id(symbol)
        side = side.value if isinstance(side, OrderSide) else side.lower()
        order_type = order_type.value if isinstance(order_type, FuturesOrderType) else order_type.lower()

        # Build request data
        data = {
            "instId": inst_id,
            "tdMode": "isolated",  # Futures trading mode
            "side": side,
            "ordType": order_type,
            "sz": str(size)
        }

        if price is not None:
            data["px"] = str(price)

        if time_in_force is not None:
            tif = time_in_force.value if isinstance(time_in_force, TimeInForce) else time_in_force
            data["tif"] = tif

        if position_side is not None:
            ps = position_side.value if isinstance(position_side, PositionSide) else position_side.lower()
            data["posSide"] = ps

        if reduce_only is not None:
            data["reduceOnly"] = str(reduce_only).lower()

        if client_order_id is not None:
            data["clOrdId"] = client_order_id

        logger.info(f"Placing futures {side} {order_type} order for {inst_id}")

        return self._make_signed_request("POST", self.FUTURES_ORDER_ENDPOINT, data=data)

    def place_futures_market_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        size: Union[str, float],
        position_side: Union[str, PositionSide],
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience method to place a futures market order.

        Args:
            symbol (str): Trading symbol
            side (str): Order side ('buy' or 'sell')
            size (str/float): Order size in contracts
            position_side (str): Position side
            reduce_only (bool): Reduce only flag

        Returns:
            Dict: Order response
        """
        return self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.MARKET,
            size=size,
            position_side=position_side,
            reduce_only=reduce_only
        )

    def place_futures_limit_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        size: Union[str, float],
        price: Union[str, float],
        time_in_force: Union[str, TimeInForce] = TimeInForce.GTC,
        position_side: Union[str, PositionSide] = PositionSide.NET,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience method to place a futures limit order.

        Args:
            symbol (str): Trading symbol
            side (str): Order side ('buy' or 'sell')
            size (str/float): Order size in contracts
            price (str/float): Limit price
            time_in_force (str): Time in force
            position_side (str): Position side
            reduce_only (bool): Reduce only flag

        Returns:
            Dict: Order response
        """
        return self.place_futures_order(
            symbol=symbol,
            side=side,
            order_type=FuturesOrderType.LIMIT,
            size=size,
            price=price,
            time_in_force=time_in_force,
            position_side=position_side,
            reduce_only=reduce_only
        )

    # ==================== ORDER MANAGEMENT ====================

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel an active order.

        Args:
            symbol (str): Trading symbol
            order_id (str): Order ID
            client_order_id (str): Client order ID

        Returns:
            Dict: Cancellation response
        """
        if order_id is None and client_order_id is None:
            raise ValueError("Either order_id or client_order_id is required")

        inst_id = self._get_inst_id(symbol)

        data = {"instId": inst_id}

        if order_id is not None:
            data["ordId"] = order_id
        if client_order_id is not None:
            data["clOrdId"] = client_order_id

        endpoint = (self.SPOT_CANCEL_ORDER_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_CANCEL_ORDER_ENDPOINT)

        logger.info(f"Cancelling order for {inst_id}")

        return self._make_signed_request("POST", endpoint, data=data)

    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all open orders.

        Args:
            symbol (str, optional): Trading symbol (if None, cancels all symbols)

        Returns:
            Dict: Cancellation response
        """
        data = {}
        if symbol is not None:
            inst_id = self._get_inst_id(symbol)
            data["instId"] = inst_id

        # OKX doesn't have a direct "cancel all" endpoint, so we need to get pending orders first
        pending_orders = self.get_open_orders(symbol)

        if not pending_orders.get('data'):
            return {"cancelled": 0, "message": "No open orders to cancel"}

        cancelled_count = 0
        for order in pending_orders['data']:
            try:
                self.cancel_order(
                    symbol=order['instId'],
                    order_id=order['ordId']
                )
                cancelled_count += 1
                time.sleep(0.1)  # Small delay to avoid rate limits
            except Exception as e:
                logger.warning(f"Failed to cancel order {order['ordId']}: {e}")

        return {"cancelled": cancelled_count, "total": len(pending_orders['data'])}

    def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get order information.

        Args:
            symbol (str): Trading symbol
            order_id (str): Order ID
            client_order_id (str): Client order ID

        Returns:
            Dict: Order information
        """
        if order_id is None and client_order_id is None:
            raise ValueError("Either order_id or client_order_id is required")

        inst_id = self._get_inst_id(symbol)
        params = {"instId": inst_id}

        if order_id is not None:
            params["ordId"] = order_id
        if client_order_id is not None:
            params["clOrdId"] = client_order_id

        endpoint = (self.SPOT_ORDER_INFO_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_ORDER_INFO_ENDPOINT)

        return self._make_signed_request("GET", endpoint, params=params)

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all open orders.

        Args:
            symbol (str, optional): Trading symbol

        Returns:
            Dict: List of open orders
        """
        params = {}
        if symbol is not None:
            inst_id = self._get_inst_id(symbol)
            params["instId"] = inst_id

        endpoint = (self.SPOT_ORDERS_PENDING_ENDPOINT if self.market_type == "spot"
                   else self.FUTURES_ORDERS_PENDING_ENDPOINT)

        return self._make_signed_request("GET", endpoint, params=params)

    # ==================== ACCOUNT & POSITION ====================

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.

        Returns:
            Dict: Account information including balances
        """
        return self._make_signed_request("GET", self.SPOT_ACCOUNT_ENDPOINT)

    def get_futures_positions(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get futures positions.

        Args:
            symbol (str, optional): Trading symbol

        Returns:
            Dict: List of positions
        """
        if self.market_type != "futures":
            raise ValueError("This method is only available for futures market")

        params = {}
        if symbol is not None:
            inst_id = self._get_inst_id(symbol)
            params["instId"] = inst_id

        return self._make_signed_request("GET", self.FUTURES_POSITION_ENDPOINT, params=params)

    def set_futures_leverage(
        self,
        symbol: str,
        leverage: int,
        margin_mode: str = "cross"
    ) -> Dict[str, Any]:
        """
        Set leverage for a futures symbol.

        Args:
            symbol (str): Trading symbol
            leverage (int): Leverage (1-125)
            margin_mode (str): Margin mode ('cross' or 'isolated')

        Returns:
            Dict: Leverage update response
        """
        if self.market_type != "futures":
            raise ValueError("This method is only available for futures market")

        inst_id = self._get_inst_id(symbol)

        if not 1 <= leverage <= 125:
            raise ValueError("Leverage must be between 1 and 125")

        if margin_mode not in ["cross", "isolated"]:
            raise ValueError("margin_mode must be 'cross' or 'isolated'")

        data = {
            "instId": inst_id,
            "lever": str(leverage),
            "mgnMode": margin_mode
        }

        logger.info(f"Setting leverage for {inst_id} to {leverage}x ({margin_mode})")

        return self._make_signed_request("POST", self.FUTURES_LEVERAGE_ENDPOINT, data=data)

    def set_futures_margin_mode(
        self,
        symbol: str,
        margin_mode: Literal["cross", "isolated"]
    ) -> Dict[str, Any]:
        """
        Set margin mode for a futures symbol.

        Args:
            symbol (str): Trading symbol
            margin_mode (str): Margin mode ('cross' or 'isolated')

        Returns:
            Dict: Margin mode update response
        """
        if self.market_type != "futures":
            raise ValueError("This method is only available for futures market")

        inst_id = self._get_inst_id(symbol)

        if margin_mode not in ["cross", "isolated"]:
            raise ValueError("margin_mode must be 'cross' or 'isolated'")

        data = {
            "instId": inst_id,
            "mgnMode": margin_mode
        }

        logger.info(f"Setting margin mode for {inst_id} to {margin_mode}")

        return self._make_signed_request("POST", self.FUTURES_MARGIN_MODE_ENDPOINT, data=data)

    # def get_instruments(self, symbol: str, inst_type: str) -> Dict[str, Any]:
    #     """Retrieve instrument metadata (public endpoint).

    #     For SWAP instruments, OKX requires `instType=SWAP`.

    #     Args:
    #         symbol (str): Trading symbol, e.g. 'BTC-USDT'
    #     Returns:
    #         Dict: Instruments information
    #     """
    #     if self.market_type != "futures":
    #         raise ValueError("This method is only available for futures market")

    #     inst_id = self._get_inst_id(symbol)
    #     return self._make_signed_request(
    #         "GET",
    #         self.FUTURES_INSTRUMENT_INFO_ENDPOINT,
    #         params={"instType": inst_type, "instId": inst_id},
    #     )

    # def get_position(self) -> Dict[str, Any]:
    #     """Retrieve position information for a given instrument ID.

    #     Args:
    #         instid (str): Instrument ID, e.g. 'BTC-USDT-SWAP'

    #     Returns:
    #         Dict: Position information
    #     """
    #     if self.market_type != "futures":
    #         raise ValueError("This method is only available for futures market")

    #     return self._make_signed_request(
    #         "GET",
    #         self.FUTURES_POSITION_ENDPOINT
    #     )

# ==================== CONVENIENCE FUNCTIONS ====================

def create_spot_client(
    api_key: str = None,
    api_secret: str = None,
    passphrase: str = None,
    testnet: bool = False
) -> OKXOrderClient:
    """
    Create a spot market order client.

    Args:
        api_key (str): API key (or use OKX_API_KEY env var)
        api_secret (str): API secret (or use OKX_API_SECRET env var)
        passphrase (str): API passphrase (or use OKX_PASSPHRASE env var)
        testnet (bool): Use testnet

    Returns:
        OKXOrderClient: Configured for spot market
    """
    return OKXOrderClient(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        market_type="spot",
        testnet=testnet
    )


def create_futures_client(
    api_key: str = None,
    api_secret: str = None,
    passphrase: str = None,
    testnet: bool = False
) -> OKXOrderClient:
    """
    Create a futures market order client.

    Args:
        api_key (str): API key (or use OKX_API_KEY env var)
        api_secret (str): API secret (or use OKX_API_SECRET env var)
        passphrase (str): API passphrase (or use OKX_PASSPHRASE env var)
        testnet (bool): Use testnet

    Returns:
        OKXOrderClient: Configured for futures market
    """
    return OKXOrderClient(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        market_type="futures",
        testnet=testnet
    )


if __name__ == "__main__":
    client = create_futures_client()
    # Example: Place a futures market order
    response = client.get_account_info()
    print(response)
    # response = client.place_futures_market_order(
    #     symbol="BTC-USDT",
    #     side=OrderSide.SELL,
    #     size=0.01,
    #     position_side=PositionSide.LONG,
    #     reduce_only=False
    # )
    # print(response)
    # Example: Get futures positions
    # response = client.get_futures_positions("BTC-USDT")
    # print(response)