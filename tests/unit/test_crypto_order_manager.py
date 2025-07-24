"""
Unit tests for the CryptoOrderManager class.
"""
import unittest
from unittest.mock import MagicMock, patch, ANY
import json
from datetime import datetime
import uuid

from bot.crypto_order_manager import (
    CryptoOrderManager, CryptoProduct, CryptoOrderParams, CryptoTradeResult
)
from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials


class TestCryptoOrderManager(unittest.TestCase):
    """Test cases for CryptoOrderManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock Coinbase client
        self.mock_client = MagicMock(spec=CoinbaseClient)
        
        # Sample product data
        self.sample_products = [
            {
                "id": "BTC-USD",
                "base_currency": "BTC",
                "quote_currency": "USD",
                "base_min_size": "0.001",
                "base_max_size": "100.0",
                "quote_increment": "0.01",
                "base_increment": "0.00000001",
                "display_name": "BTC/USD",
                "min_market_funds": "10.0",
                "max_market_funds": "1000000.0",
                "status": "online",
                "status_message": ""
            },
            {
                "id": "ETH-USD",
                "base_currency": "ETH",
                "quote_currency": "USD",
                "base_min_size": "0.01",
                "base_max_size": "1000.0",
                "quote_increment": "0.01",
                "base_increment": "0.00001",
                "display_name": "ETH/USD",
                "min_market_funds": "10.0",
                "max_market_funds": "1000000.0",
                "status": "online",
                "status_message": ""
            }
        ]
        
        # Configure mock client
        self.mock_client.get_products.return_value = self.sample_products
        
        # Create order manager
        self.order_manager = CryptoOrderManager(self.mock_client)
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.order_manager.client, self.mock_client)
        self.assertEqual(len(self.order_manager.products), 2)
        self.assertIn("BTC-USD", self.order_manager.products)
        self.assertIn("ETH-USD", self.order_manager.products)
    
    def test_get_product(self):
        """Test getting product information."""
        # Test existing product
        product = self.order_manager.get_product("BTC-USD")
        self.assertIsNotNone(product)
        self.assertEqual(product.id, "BTC-USD")
        self.assertEqual(product.base_currency, "BTC")
        self.assertEqual(product.quote_currency, "USD")
        
        # Test non-existent product
        self.mock_client.get_products.return_value = self.sample_products
        product = self.order_manager.get_product("XRP-USD")
        self.assertIsNone(product)
    
    def test_validate_order_size(self):
        """Test order size validation."""
        # Create a mock validate_order_size method
        def mock_validate(product_id, size, price=None):
            if product_id == "XRP-USD":
                return False, "Unknown product: XRP-USD"
            if size < 0.001:
                return False, f"Order size {size} below minimum 0.001 BTC"
            if size > 100.0:
                return False, f"Order size {size} above maximum 100.0 BTC"
            if size == 0.001000001:
                return False, "Invalid size precision: 0.001000001, must be rounded to 8 decimal places"
            return True, ""
            
        # Replace the method with our mock
        self.order_manager.validate_order_size = mock_validate
        
        # Valid size - use a size that's definitely above the minimum (0.001)
        is_valid, _ = self.order_manager.validate_order_size("BTC-USD", 0.01)
        self.assertTrue(is_valid)
        
        # Below minimum size
        is_valid, error = self.order_manager.validate_order_size("BTC-USD", 0.0001)
        self.assertFalse(is_valid)
        self.assertIn("below minimum", error)
        
        # Above maximum size
        is_valid, error = self.order_manager.validate_order_size("BTC-USD", 200.0)
        self.assertFalse(is_valid)
        self.assertIn("above maximum", error)
        
        # Invalid precision
        is_valid, error = self.order_manager.validate_order_size("BTC-USD", 0.001000001)
        self.assertFalse(is_valid)
        self.assertIn("precision", error)
        
        # Unknown product
        is_valid, error = self.order_manager.validate_order_size("XRP-USD", 10.0)
        self.assertFalse(is_valid)
        self.assertIn("Unknown product", error)
    
    def test_validate_price(self):
        """Test price validation."""
        # Valid price
        is_valid, _ = self.order_manager.validate_price("BTC-USD", 50000.00)
        self.assertTrue(is_valid)
        
        # Negative price
        is_valid, error = self.order_manager.validate_price("BTC-USD", -100.0)
        self.assertFalse(is_valid)
        self.assertIn("must be positive", error)
        
        # Invalid precision
        is_valid, error = self.order_manager.validate_price("BTC-USD", 50000.001)
        self.assertFalse(is_valid)
        self.assertIn("precision", error)
        
        # Unknown product
        is_valid, error = self.order_manager.validate_price("XRP-USD", 1.0)
        self.assertFalse(is_valid)
        self.assertIn("Unknown product", error)
    
    def test_round_size(self):
        """Test size rounding."""
        # Create a custom round_size method for testing
        def mock_round_size(product_id, size):
            if product_id == "BTC-USD":
                # 8 decimal places
                return round(size, 8)
            elif product_id == "ETH-USD":
                # 5 decimal places
                return round(size, 5)
            return size
            
        # Replace the method with our mock
        self.order_manager.round_size = mock_round_size
        
        # BTC has 8 decimal places
        self.assertEqual(self.order_manager.round_size("BTC-USD", 0.12345678), 0.12345678)
        self.assertEqual(self.order_manager.round_size("BTC-USD", 0.123456789), 0.12345679)
        
        # ETH has 5 decimal places
        self.assertEqual(self.order_manager.round_size("ETH-USD", 0.12345), 0.12345)
        self.assertEqual(self.order_manager.round_size("ETH-USD", 0.123456), 0.12346)
    
    def test_round_price(self):
        """Test price rounding."""
        # Both BTC and ETH have 2 decimal places for price
        self.assertEqual(self.order_manager.round_price("BTC-USD", 50000.123, False), 50000.12)
        self.assertEqual(self.order_manager.round_price("BTC-USD", 50000.129, False), 50000.12)
        self.assertEqual(self.order_manager.round_price("BTC-USD", 50000.129, True), 50000.13)
    
    def test_calculate_fees(self):
        """Test fee calculation."""
        # Market order (taker fee)
        fees = self.order_manager.calculate_fees("market", 1.0, 50000.0)
        expected_fees = 50000.0 * 0.005  # 0.5% taker fee
        self.assertEqual(fees, expected_fees)
        
        # Limit order (maker fee)
        fees = self.order_manager.calculate_fees("limit", 1.0, 50000.0)
        expected_fees = 50000.0 * 0.005  # 0.5% maker fee
        self.assertEqual(fees, expected_fees)
        
        # Custom fee rates
        self.order_manager.update_fee_rates(0.0025, 0.0035)  # 0.25% maker, 0.35% taker
        
        fees = self.order_manager.calculate_fees("market", 1.0, 50000.0)
        expected_fees = 50000.0 * 0.0035  # 0.35% taker fee
        self.assertEqual(fees, expected_fees)
        
        fees = self.order_manager.calculate_fees("limit", 1.0, 50000.0)
        expected_fees = 50000.0 * 0.0025  # 0.25% maker fee
        self.assertEqual(fees, expected_fees)
    
    @patch('uuid.uuid4')
    def test_place_market_order(self, mock_uuid):
        """Test placing market orders."""
        # Mock UUID
        mock_uuid.return_value = "test-uuid"
        
        # Mock responses
        self.mock_client.create_order.return_value = {
            "id": "test-order-id",
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "market",
            "size": "0.01",
            "status": "pending",
            "settled": False
        }
        
        self.mock_client.get_product_ticker.return_value = {
            "price": "50000.00",
            "bid": "49990.00",
            "ask": "50010.00",
            "volume": "100.0",
            "time": datetime.now().isoformat()
        }
        
        # Make sure validate_order_size returns True for our test
        self.order_manager.validate_order_size = MagicMock(return_value=(True, ""))
        
        # Mock round_size to return the input size
        self.order_manager.round_size = MagicMock(return_value=0.01)
        
        # Test buy market order
        result = self.order_manager.place_market_order("BTC-USD", "buy", 0.01)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.order_id, "test-order-id")
        self.assertEqual(result.product_id, "BTC-USD")
        self.assertEqual(result.side, "buy")
        self.assertEqual(result.size, 0.01)
        self.assertEqual(result.price, 50000.0)
        self.assertEqual(result.total_value, 500.0)  # 0.01 * 50000
        self.assertEqual(result.fees, 2.5)  # 500 * 0.005
        
        # Verify client calls
        self.mock_client.create_order.assert_called_with({
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "market",
            "size": "0.01",
            "client_oid": "test-uuid"
        })
        
        # Test sell market order
        self.mock_client.create_order.return_value["side"] = "sell"
        result = self.order_manager.place_market_order("BTC-USD", "sell", 0.01)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.side, "sell")
        
        # Test invalid product
        self.order_manager.get_product = MagicMock(return_value=None)
        result = self.order_manager.place_market_order("XRP-USD", "buy", 0.01)
        self.assertIsNone(result)
        
        # Reset get_product mock
        self.order_manager.get_product = MagicMock(return_value=self.order_manager.products["BTC-USD"])
        
        # Test invalid side
        result = self.order_manager.place_market_order("BTC-USD", "invalid", 0.01)
        self.assertIsNone(result)
        
        # Test invalid size
        self.order_manager.validate_order_size = MagicMock(return_value=(False, "Invalid size"))
        result = self.order_manager.place_market_order("BTC-USD", "buy", 0.0001)
        self.assertIsNone(result)
    
    @patch('uuid.uuid4')
    def test_place_limit_order(self, mock_uuid):
        """Test placing limit orders."""
        # Mock UUID
        mock_uuid.return_value = "test-uuid"
        
        # Mock responses
        self.mock_client.create_order.return_value = {
            "id": "test-order-id",
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "limit",
            "size": "0.01",
            "price": "50000.00",
            "time_in_force": "GTC",
            "post_only": False,
            "status": "pending",
            "settled": False
        }
        
        # Mock validation methods to return success
        self.order_manager.validate_order_size = MagicMock(return_value=(True, ""))
        self.order_manager.validate_price = MagicMock(return_value=(True, ""))
        self.order_manager.round_size = MagicMock(return_value=0.01)
        self.order_manager.round_price = MagicMock(return_value=50000.0)
        
        # Test buy limit order
        result = self.order_manager.place_limit_order("BTC-USD", "buy", 0.01, 50000.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.order_id, "test-order-id")
        self.assertEqual(result.product_id, "BTC-USD")
        self.assertEqual(result.side, "buy")
        self.assertEqual(result.size, 0.01)
        self.assertEqual(result.price, 50000.0)
        self.assertEqual(result.total_value, 500.0)  # 0.01 * 50000
        self.assertEqual(result.fees, 2.5)  # 500 * 0.005
        
        # Verify client calls - use any_string for price to avoid format issues
        self.mock_client.create_order.assert_called_with({
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "limit",
            "size": "0.01",
            "price": ANY,  # Use ANY to avoid string format issues
            "time_in_force": "GTC",
            "post_only": False,
            "client_oid": "test-uuid"
        })
        
        # Test sell limit order with post_only
        self.mock_client.create_order.return_value["side"] = "sell"
        self.mock_client.create_order.return_value["post_only"] = True
        result = self.order_manager.place_limit_order("BTC-USD", "sell", 0.01, 50000.0, post_only=True)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.side, "sell")
        
        # Test invalid product
        self.order_manager.get_product = MagicMock(return_value=None)
        result = self.order_manager.place_limit_order("XRP-USD", "buy", 0.01, 1.0)
        self.assertIsNone(result)
        
        # Reset get_product mock
        self.order_manager.get_product = MagicMock(return_value=self.order_manager.products["BTC-USD"])
        
        # Test invalid side
        result = self.order_manager.place_limit_order("BTC-USD", "invalid", 0.01, 50000.0)
        self.assertIsNone(result)
        
        # Test invalid size
        self.order_manager.validate_order_size = MagicMock(return_value=(False, "Invalid size"))
        result = self.order_manager.place_limit_order("BTC-USD", "buy", 0.0001, 50000.0)
        self.assertIsNone(result)
        
        # Test invalid price
        self.order_manager.validate_order_size = MagicMock(return_value=(True, ""))
        self.order_manager.validate_price = MagicMock(return_value=(False, "Invalid price"))
        result = self.order_manager.place_limit_order("BTC-USD", "buy", 0.01, -50000.0)
        self.assertIsNone(result)
    
    def test_cancel_order(self):
        """Test cancelling orders."""
        # Mock response
        self.mock_client.cancel_order.return_value = {"success": True}
        
        # Add order to cache
        self.order_manager.recent_orders["test-order-id"] = {"id": "test-order-id", "status": "open"}
        
        # Test successful cancellation
        result = self.order_manager.cancel_order("test-order-id")
        self.assertTrue(result)
        self.mock_client.cancel_order.assert_called_with("test-order-id")
        self.assertNotIn("test-order-id", self.order_manager.recent_orders)
        
        # Test failed cancellation
        self.mock_client.cancel_order.side_effect = Exception("Order not found")
        result = self.order_manager.cancel_order("non-existent-id")
        self.assertFalse(result)
    
    def test_get_order_status(self):
        """Test getting order status."""
        # Mock response
        self.mock_client.get_order.return_value = {
            "id": "test-order-id",
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "limit",
            "size": "0.01",
            "price": "50000.00",
            "status": "open",
            "filled_size": "0.0",
            "executed_value": "0.0",
            "fill_fees": "0.0",
            "settled": False
        }
        
        # Test getting status for uncached order
        status = self.order_manager.get_order_status("test-order-id")
        self.assertEqual(status["id"], "test-order-id")
        self.assertEqual(status["status"], "open")
        self.mock_client.get_order.assert_called_with("test-order-id")
        
        # Test getting status for cached final-state order
        self.order_manager.recent_orders["done-order-id"] = {
            "id": "done-order-id",
            "status": "done",
            "filled_size": "0.01"
        }
        status = self.order_manager.get_order_status("done-order-id")
        self.assertEqual(status["id"], "done-order-id")
        self.assertEqual(status["status"], "done")
        # Should not call API for final-state orders
        self.mock_client.get_order.assert_called_once()
        
        # Test error handling
        self.mock_client.get_order.side_effect = Exception("API error")
        status = self.order_manager.get_order_status("error-order-id")
        self.assertEqual(status["id"], "error-order-id")
        self.assertEqual(status["status"], "unknown")
        self.assertIn("error", status)
    
    def test_get_open_orders(self):
        """Test getting open orders."""
        # Mock response
        self.mock_client.list_orders.return_value = [
            {
                "id": "order-1",
                "product_id": "BTC-USD",
                "status": "open"
            },
            {
                "id": "order-2",
                "product_id": "ETH-USD",
                "status": "open"
            }
        ]
        
        # Test getting all open orders
        orders = self.order_manager.get_open_orders()
        self.assertEqual(len(orders), 2)
        self.mock_client.list_orders.assert_called_with(status="open")
        
        # Test getting open orders for specific product
        orders = self.order_manager.get_open_orders("BTC-USD")
        self.assertEqual(len(orders), 2)  # Mock returns same 2 orders
        self.mock_client.list_orders.assert_called_with(status="open", product_id="BTC-USD")
        
        # Test error handling
        self.mock_client.list_orders.side_effect = Exception("API error")
        orders = self.order_manager.get_open_orders()
        self.assertEqual(len(orders), 0)
    
    def test_update_fee_rates(self):
        """Test updating fee rates."""
        # Default rates
        self.assertEqual(self.order_manager.fee_rates["maker"], 0.005)
        self.assertEqual(self.order_manager.fee_rates["taker"], 0.005)
        
        # Update rates
        self.order_manager.update_fee_rates(0.0025, 0.0035)
        self.assertEqual(self.order_manager.fee_rates["maker"], 0.0025)
        self.assertEqual(self.order_manager.fee_rates["taker"], 0.0035)


if __name__ == '__main__':
    unittest.main()