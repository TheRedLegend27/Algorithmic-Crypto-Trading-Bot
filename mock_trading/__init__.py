"""
Mock Trading Environment Package

A comprehensive paper trading simulator that mimics Alpaca's API behavior
while using real market data but simulating trades with fake money.
"""

__version__ = "1.0.0"
__author__ = "Trading Bot Team"

from .mock_config import MockTradingConfig
from .mock_trader import MockTrader

__all__ = [
    "MockTradingConfig",
    "MockTrader",
]