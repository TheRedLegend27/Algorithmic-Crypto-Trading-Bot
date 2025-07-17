#!/usr/bin/env python
"""
Command-line entry point for the crypto trading bot.

This script serves as the main entry point for running the cryptocurrency trading bot.
It imports and calls the main function from the bot package, which initializes all
components and starts the trading scheduler.

Usage:
    python run_bot.py [options]

For a full list of command-line options, run:
    python run_bot.py --help
"""
import sys
from typing import NoReturn
from bot.main import main

if __name__ == "__main__":
    """
    Entry point for the script.
    Calls the main function and uses its return value as the exit code.
    """
    sys.exit(main())