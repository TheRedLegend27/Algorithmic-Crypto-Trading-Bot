# Python Crypto Scalping Bot for Alpaca

This is a high-performance crypto scalping bot that uses the `alpaca-py` SDK to trade cryptocurrencies on Alpaca. It is designed for low-latency market data processing, rapid order execution, and robust risk management.

## Features

-   **Real-time Data Streaming**: Connects to Alpaca's WebSocket for live trade data.
-   **Scalping Strategy**: Implements a simple VWAP and RSI-based scalping strategy.
-   **Order Management**: Supports Market, Limit, and Stop-Limit orders.
-   **Risk Management**: Includes per-trade risk, daily loss limits, and dynamic position sizing.
-   **Paper Trading**: Supports Alpaca's paper trading environment for safe testing.
-   **Modular Design**: Code is organized into logical modules for easy extension.

## Getting Started

### Prerequisites

-   Python 3.9+
-   An Alpaca account (either paper or live).

### 1. Clone the Repository

```bash
git clone <repository_url>
cd crypto_scalping_bot