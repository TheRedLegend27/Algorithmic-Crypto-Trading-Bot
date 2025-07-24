#!/usr/bin/env python
"""
Command-line entry point for the Coinbase cryptocurrency trading bot.

This script serves as the main entry point for running the cryptocurrency trading bot
with Coinbase Advanced Trade API. It imports and calls the main function from the bot
package, which initializes all components and starts the trading scheduler.

Usage:
    python run_coinbase_bot.py [options]

For a full list of command-line options, run:
    python run_coinbase_bot.py --help
"""
import sys
from typing import NoReturn
from bot.main import main

if __name__ == "__main__":
    """
    Entry point for the script.
    Calls the main function with Coinbase platform and uses its return value as the exit code.
    """
    # Add --platform coinbase to the command line arguments
    sys.argv.append("--platform")
    sys.argv.append("coinbase")
    sys.exit(main())