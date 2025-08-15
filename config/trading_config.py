class TradingConfig:
    # --- Risk Management ---
    LEVERAGE = 10  # Default leverage
    MAX_RISK_USDT = 100.0  # Max amount in USDT to risk per trade
    RISK_PERCENT = 0.02  # Percentage of balance to risk per trade
    MIN_ORDER_SIZE = 10.0  # Minimum order size in USDT

    @staticmethod
    def calculate_tp_sl(desired_tp, desired_sl, leverage, strategy_name):
        """
        Calculate Take Profit and Stop Loss percentages based on leverage.
        This ensures that the percentages are adjusted for the leveraged position size.
        """
        if leverage <= 0:
            return None, None

        # The desired TP/SL is for the position including leverage.
        # The actual price movement needed is the desired % divided by leverage.
        # For example, a 10% TP with 10x leverage means a 1% price move.
        take_profit_percent = desired_tp / leverage / 100
        stop_loss_percent = desired_sl / leverage / 100

        return take_profit_percent, stop_loss_percent
