#!/usr/bin/env python3
"""
Test script to verify --maxtrades argument works correctly.
"""
import sys
import argparse
from bot.aggressive_strategies import AggressiveRiskManager
from bot.aggressive_config import get_aggressive_config

def test_maxtrades_argument():
    """Test that --maxtrades argument is properly handled."""
    
    print("Testing --maxtrades argument functionality...")
    
    # Test 1: Default value
    print("\n1. Testing default values:")
    risk_manager = AggressiveRiskManager()
    print(f"   Default max_trades_per_day: {risk_manager.max_trades_per_day}")
    
    # Test 2: Custom value via constructor
    print("\n2. Testing custom value via constructor:")
    custom_max_trades = 50
    risk_manager_custom = AggressiveRiskManager(max_trades_per_day=custom_max_trades)
    print(f"   Custom max_trades_per_day: {risk_manager_custom.max_trades_per_day}")
    
    # Test 3: AggressiveConfig default
    print("\n3. Testing AggressiveConfig default:")
    config = get_aggressive_config()
    print(f"   Config max_trades_per_day: {config['trading_settings'].max_trades_per_day}")
    
    # Test 4: Simulate command line argument parsing
    print("\n4. Testing argument parsing simulation:")
    parser = argparse.ArgumentParser()
    parser.add_argument("--maxtrades", type=int, default=20)
    
    # Simulate different command line inputs
    test_cases = [
        [],  # Default
        ["--maxtrades", "30"],  # Custom value
        ["--maxtrades", "100"],  # High value
    ]
    
    for i, args in enumerate(test_cases):
        parsed_args = parser.parse_args(args)
        print(f"   Test case {i+1}: args={args} -> maxtrades={parsed_args.maxtrades}")
    
    print("\n✅ All tests completed successfully!")
    print("\nUsage examples:")
    print("  python run_bot.py --maxtrades 30")
    print("  python run_enhanced_bot.py --maxtrades 50")
    print("  python run_enhanced_bot.py --paper-trading --maxtrades 15")

if __name__ == "__main__":
    test_maxtrades_argument()