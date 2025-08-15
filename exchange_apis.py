import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timezone

class BaseExchangeAPI:
    def __init__(self, credentials, display, db_manager, config):
        self.credentials = credentials
        self.display = display
        self.db = db_manager
        self.config = config
        self.public_url = ""
        self.private_url = ""

    def get_historical_data(self, pair, interval, limit=500, force_fresh=False):
        raise NotImplementedError

    def get_wallet_data(self):
        raise NotImplementedError

    def validate_data_freshness(self, data, pair_symbol, max_age_seconds=None):
        if not self.config.DATA_FRESHNESS_CHECK_ENABLED:
            return {'is_fresh': True, 'message': 'Validation disabled'}

        if max_age_seconds is None:
            max_age_seconds = self.config.MAX_DATA_AGE_SECONDS

        if data.empty:
            return {'is_fresh': False, 'message': 'No data available'}

        try:
            latest_timestamp = pd.to_datetime(data['open_time'].iloc[-1])
            if latest_timestamp.tz is None:
                latest_timestamp = latest_timestamp.tz_localize('UTC')

            current_time = datetime.now(timezone.utc)
            data_age_seconds = (current_time - latest_timestamp).total_seconds()

            is_fresh = data_age_seconds <= max_age_seconds
            message = f"Data is {data_age_seconds:.0f}s old."
            if not is_fresh:
                message += f" (Stale, limit is {max_age_seconds}s)"

            return {
                'is_fresh': is_fresh,
                'data_age_seconds': int(data_age_seconds),
                'last_timestamp': latest_timestamp,
                'message': message
            }
        except Exception as e:
            logging.error(f"Error validating data freshness for {pair_symbol}: {e}")
            return {'is_fresh': False, 'message': f'Validation error: {e}'}

    def clear_cache_for_pair(self, pair_symbol):
        return self.db.clear_cache_for_pair(pair_symbol)


class MockExchangeAPI(BaseExchangeAPI):
    def get_historical_data(self, pair, interval, limit=500, force_fresh=False):
        if not force_fresh:
            data = self.db.get_candle_data(pair, limit, interval)
            if not data.empty:
                # Check if data is recent enough
                freshness = self.validate_data_freshness(data, pair)
                if freshness['is_fresh']:
                    return data

        # Generate mock data
        interval_seconds = self._interval_to_seconds(interval)
        if interval_seconds is None: return pd.DataFrame()

        now_ms = int(time.time() * 1000)
        end_time = now_ms - (now_ms % (interval_seconds * 1000)) # Align to interval
        start_time = end_time - (limit * interval_seconds * 1000)

        timestamps = np.arange(start_time, end_time, interval_seconds * 1000)
        price = 100 + np.random.randn(len(timestamps)).cumsum() * 0.1

        data = []
        for i in range(len(timestamps)):
            open_p = price[i-1] if i > 0 else price[i]
            close_p = price[i]
            high_p = max(open_p, close_p) + np.random.uniform(0, 0.5)
            low_p = min(open_p, close_p) - np.random.uniform(0, 0.5)
            volume = np.random.uniform(100, 1000)
            # Ensure open_time is integer milliseconds
            data.append([int(timestamps[i]), open_p, high_p, low_p, close_p, volume])

        df = pd.DataFrame(data, columns=['open_time', 'open', 'high', 'low', 'close', 'volume'])

        self.db.save_candle_data(df, pair, interval)
        return self.db.get_candle_data(pair, limit, interval)

    def _interval_to_seconds(self, interval):
        if interval.endswith('m'): return int(interval[:-1]) * 60
        if interval.endswith('h'): return int(interval[:-1]) * 3600
        if interval.endswith('d'): return int(interval[:-1]) * 86400
        return None

    def get_wallet_data(self):
        return [{'currency_short_name': 'USDT', 'balance': '10000.0'}]


class ExchangeAPIFactory:
    @staticmethod
    def create_api(exchange_name, credentials, display, db_manager, config):
        # In a real application, you would have separate classes for each exchange.
        # For now, we use the mock API for all.
        logging.info(f"Creating MOCK API client for {exchange_name}")
        return MockExchangeAPI(credentials, display, db_manager, config)
