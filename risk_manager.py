from utils import logger

class RiskManager:
    def __init__(self, trading_client, risk_per_trade: float):
        self.trading_client = trading_client
        self.risk_per_trade = risk_per_trade

    def get_trade_quantity(self, entry_price: float, stop_loss_price: float):
        """Calculates the trade quantity based on risk parameters."""
        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
            
            risk_amount = equity * self.risk_per_trade
            price_risk_per_unit = abs(entry_price - stop_loss_price)
            
            if price_risk_per_unit == 0:
                return 0
            
            quantity = risk_amount / price_risk_per_unit
            logger.info(f"Calculated trade quantity: {quantity:.6f} based on {self.risk_per_trade*100}% risk.")
            return quantity
        except Exception as e:
            logger.error(f"Error getting account info for quantity calculation: {e}")
            return 0