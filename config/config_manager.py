import dash_bootstrap_components as dbc

class Config:
    # --- General Settings ---
    DB_PATH = 'trading_bot.db'
    PAPER_TRADING = True
    AUTO_OPEN_BROWSER = True
    SETTINGS_PASSWORD = "admin123"  # Change this!

    # --- Exchange Settings ---
    ACTIVE_EXCHANGES = ["coindcx"]
    SELECTED_EXCHANGE = "coindcx"
    SUPPORTED_EXCHANGES = ["coindcx", "bitget", "binance"]
    EXCHANGE_CREDENTIALS = {} # Loaded from credentials.json

    # --- Trading Pairs ---
    DEFAULT_TRADING_PAIRS = [
        "B-BTC_USDT", "B-ETH_USDT", "B-XRP_USDT", "B-LTC_USDT", "B-ADA_USDT",
        "B-DOGE_USDT", "B-SOL_USDT", "B-MATIC_USDT", "B-BNB_USDT", "B-LINK_USDT"
    ]
    MANUAL_TRADING_PAIRS = []

    # --- Strategies ---
    ACTIVE_STRATEGIES = ['main_strategy', 'trf_strategy']
    DISPLAY_STRATEGY = 'main_strategy'

    STRATEGIES = {
        'main_strategy': {
            'ema50_period': 50, 'ema200_period': 200, 'cci1_length': 100,
            'cci2_length': 40, 'cci_long_level': 100, 'cci_short_level': -100,
            'use_long_signals': True, 'use_short_signals': True,
            'use_cci1': True, 'use_cci2': True,
            'desired_take_profit': 7.0, 'desired_stop_loss': 5.0
        },
        'rsi_cci_strategy': {
            'rsi25_period': 25, 'rsi100_period': 100, 'cci40_period': 40,
            'cci100_period': 100, 'rsi_cross_level': 60, 'cci40_cross_level': 200,
            'cci100_cross_level': -45, 'ema14_period': 14, 'trail_percent': 12.0,
            'use_long_signals': True, 'use_short_signals': False
        },
        'trf_strategy': {
            'per1': 27, 'mult1': 2, 'per2': 55, 'mult2': 3,
            'use_long_signals': True, 'use_short_signals': True,
            'desired_take_profit': 10.0, 'desired_stop_loss': 5.0,
            'cci_length': 100, 'ema_length': 200, 'cci_long_level': 100,
            'cci_short_level': -100, 'use_trending_signals': True, 'use_reversal_signals': True
        }
    }

    # --- UI & Dashboard ---
    REFRESH_INTERVAL = 15  # seconds
    CURRENT_TIMEFRAME = '5m'
    SUPPORTED_TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    TIMEFRAME_LABELS = {
        '1m': '1 Minute', '5m': '5 Minutes', '15m': '15 Minutes', '30m': '30 Minutes',
        '1h': '1 Hour', '4h': '4 Hours', '1d': '1 Day'
    }
    THEMES = {
        'dark': {'name': 'Black', 'stylesheet': dbc.themes.DARKLY},
        'light': {'name': 'White', 'stylesheet': dbc.themes.BOOTSTRAP},
        'blue': {'name': 'Blue', 'stylesheet': dbc.themes.CYBORG}
    }
    CURRENT_THEME = 'dark'
    DASH_HOST = '127.0.0.1'
    DASH_PORT = 8050

    # --- Data & Performance ---
    CANDLE_HISTORY_LIMIT = 500
    MIN_CANDLES_FOR_TRADING = 200
    FORCE_DATA_REFRESH_ON_TIMEFRAME_CHANGE = True

    # --- Notifications ---
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    ENABLE_SOUND_NOTIFICATIONS = True

    # --- TP/SL & Trailing Stop ---
    TP_SL_OVERRIDE_ENABLED = False
    OVERRIDE_TAKE_PROFIT = 10.0
    OVERRIDE_STOP_LOSS = 5.0
    TRAILING_STOP_ENABLED = True
    TRAILING_METHOD = 'percentage'
    TRAILING_ACTIVATION_PROFIT = 20.0
    INITIAL_TRAIL_DISTANCE = 10.0
    TRAIL_TIGHTENING_STEP = 1.5
    PROFIT_INCREMENT_THRESHOLD = 10.0

    # --- Data Freshness & Circuit Breaker ---
    DATA_FRESHNESS_CHECK_ENABLED = True
    MAX_DATA_AGE_SECONDS = 300
    STALE_DATA_CIRCUIT_BREAKER_THRESHOLD = 5
    REQUIRE_FRESH_DATA_ON_STARTUP = True
    STARTUP_DATA_VALIDATION_TIMEOUT = 180
    MIN_DATA_FRESHNESS_FOR_TRADING = 600

    # --- Connectivity Monitoring ---
    CONNECTIVITY_MONITORING_ENABLED = True
    CONNECTIVITY_TEST_INTERVAL = 60
    CONNECTIVITY_PING_TIMEOUT = 2000
    CONNECTIVITY_HTTP_TIMEOUT = 5
    CONNECTIVITY_FAILURE_THRESHOLD = 3
    CONNECTIVITY_NOTIFICATIONS_ENABLED = True
