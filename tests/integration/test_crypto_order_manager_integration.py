"""
Integration tests for the CryptoOrderManager class.

These tests require valid Coinbase API credentials to be set in the environment.
They will be skipped if credentials are not available.
"""
import unittest
import os
import time
from decimal import Decimal
from unittest import skipIf

from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials
from bot.crypto_order_manager import CryptoOrderManager


# Check if Coinbase credentials are available
has_credentials = (
    os.environ.get("COINBASE_API_KEY") is not None and
    os.environ.get("COINBASE_API_SECRET") is not None and
    os.environ.get("COINBASE_PASSPHRASE") is not None
)

# Use sandbox for testing
USE_SANDBOX = True


@skipIf(not has_credentials, "Coinbase API credentials not available")
class TestCryptoOrderManagerIntegration(unittest.TestCase):
    """Integration tests for CryptoOrderManager."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the entire test case."""
        # Create Coinbase client with sandbox mode
        credentials = CoinbaseCredentials(
            api_key=os.environ.get("COINBASE_API_KEY"),
            api_secret=os.environ.get("COINBASE_API_SECRET"),
            passphrase=os.environ.get("COINBASE_PASSPHRASE"),
            sandbox=USE_SANDBOX
        )
        cls.client = CoinbaseClient(credentials)
        
        # Create order manager
        cls.order_manager = CryptoOrderManager(cls.client)
        
        # Test product (use BTC-USD for sandbox)
        cls.test_product = "BTC-USD"
        
        # Small order size for testing
        cls.test_size = 0.001  # 0.001 BTC
        
        # Store created orders for cleanup
        cls.test_orders = []
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        # Cancel any remaining test orders
        for order_id in cls.test_orders:
            try:
                cls.order_manager.cancel_order(order_id)
                print(f"Cancelled test order: {order_id}")
            except Exception as e:
                print(f"Error cancelling order {order_id}: {e}")
    
    def setUp(self):
        """Set up test fixtures before each test."""
        # Verify API connection
        self.assertTrue(self.client.test_authentication(), "API authentication failed")
    
    def test_01_get_products(self):
        """Test getting product information."""
        # Get BTC-USD product
        product = self.order_manager.get_product(self.test_product)
        
        # Verify product information
        self.assertIsNotNone(product)
        self.assertEqual(product.id, self.test_product)
        self.assertEqual(product.base_currency, "BTC")
        self.assertEqual(product.quote_currency, "USD")
        self.assertTrue(product.base_min_size > 0)
        self.assertTrue(product.base_max_size > 0)
        self.assertTrue(product.quote_increment > 0)
        self.assertTrue(product.base_increment > 0)
        self.assertEqual(product.status, "online")
    
    def test_02_validate_order_size(self):
        """Test order size validation with real product constraints."""
        product = self.order_manager.get_product(self.test_product)
        
        # Valid size
        is_valid, _ = self.order_manager.validate_order_size(self.test_product, self.test_size)
        self.assertTrue(is_valid)
        
        # Below minimum size
        too_small = product.base_min_size * 0.5
        is_valid, error = self.order_manager.validate_order_size(self.test_product, too_small)
        self.assertFalse(is_valid)
        self.assertIn("below minimum", error)
        
        # Above maximum size
        too_large = product.base_max_size * 2
        is_valid, error = self.order_manager.validate_order_size(self.test_product, too_large)
        self.assertFalse(is_valid)
        self.assertIn("above maximum", error)
    
    def test_03_validate_price(self):
        """Test price validation with real product constraints."""
        # Get current price
        ticker = self.client.get_product_ticker(self.test_product)
        current_price = float(ticker.get("price", 0.0))
        self.assertTrue(current_price > 0)
        
        # Valid price
        is_valid, _ = self.order_manager.validate_price(self.test_product, current_price)
        self.assertTrue(is_valid)
        
        # Invalid precision
        product = self.order_manager.get_product(self.test_product)
        precision = self.order_manager._get_precision_from_increment(product.quote_increment)
        invalid_price = current_price + (0.1 ** (precision + 1))
        is_valid, error = self.order_manager.validate_price(self.test_product, invalid_price)
        self.assertFalse(is_valid)
        self.assertIn("precision", error)
    
    def test_04_round_size_and_price(self):
        """Test size and price rounding with real product constraints."""
        product = self.order_manager.get_product(self.test_product)
        
        # Test size rounding
        size_precision = self.order_manager._get_precision_from_increment(product.base_increment)
        test_size = self.test_size + (0.1 ** (size_precision + 1))
        rounded_size = self.order_manager.round_size(self.test_product, test_size)
        self.assertNotEqual(test_size, rounded_size)
        
        # Test price rounding
        ticker = self.client.get_product_ticker(self.test_product)
        current_price = float(ticker.get("price", 0.0))
        price_precision = self.order_manager._get_precision_from_increment(product.quote_increment)
        test_price = current_price + (0.1 ** (price_precision + 1))
        rounded_price = self.order_manager.round_price(self.test_product, test_price)
        self.assertNotEqual(test_price, rounded_price)
    
    def test_05_place_limit_order(self):
        """Test placing and cancelling a limit order."""
        # Get current price
        ticker = self.client.get_product_ticker(self.test_product)
        current_price = float(ticker.get("price", 0.0))
        
        # Place a limit buy order 10% below current price (unlikely to execute)
        limit_price = current_price * 0.9
        result = self.order_manager.place_limit_order(
            self.test_product, "buy", self.test_size, limit_price
        )
        
        # Verify order result
        self.assertIsNotNone(result)
        self.assertEqual(result.product_id, self.test_product)
        self.assertEqual(result.side, "buy")
        self.assertEqual(result.size, self.test_size)
        
        # Store order ID for cleanup
        self.__class__.test_orders.append(result.order_id)
        
        # Check order status
        status = self.order_manager.get_order_status(result.order_id)
        self.assertEqual(status["id"], result.order_id)
        
        # Cancel the order
        success = self.order_manager.cancel_order(result.order_id)
        self.assertTrue(success)
        
        # Verify order is cancelled
        time.sleep(1)  # Wait for cancellation to process
        status = self.order_manager.get_order_status(result.order_id)
        self.assertIn(status.get("status"), ["cancelled", "canceled"])
    
    def test_06_get_open_orders(self):
        """Test getting open orders."""
        # Place a limit order
        ticker = self.client.get_product_ticker(self.test_product)
        current_price = float(ticker.get("price", 0.0))
        limit_price = current_price * 0.9
        
        result = self.order_manager.place_limit_order(
            self.test_product, "buy", self.test_size, limit_price
        )
        self.assertIsNotNone(result)
        self.__class__.test_orders.append(result.order_id)
        
        # Wait for order to be processed
        time.sleep(1)
        
        # Get all open orders
        open_orders = self.order_manager.get_open_orders()
        self.assertTrue(len(open_orders) > 0)
        
        # Get open orders for specific product
        product_orders = self.order_manager.get_open_orders(self.test_product)
        self.assertTrue(len(product_orders) > 0)
        
        # Verify our test order is in the list
        order_ids = [order["id"] for order in open_orders]
        self.assertIn(result.order_id, order_ids)
        
        # Clean up
        self.order_manager.cancel_order(result.order_id)
    
    def test_07_calculate_fees(self):
        """Test fee calculation with real fee rates."""
        # Calculate fees for a market order
        order_value = 1000.0  # $1000 order
        market_fees = self.order_manager.calculate_fees("market", 1.0, 1000.0)
        self.assertTrue(market_fees > 0)
        
        # Calculate fees for a limit order
        limit_fees = self.order_manager.calculate_fees("limit", 1.0, 1000.0)
        self.assertTrue(limit_fees > 0)


if __name__ == '__main__':
    unittest.main()