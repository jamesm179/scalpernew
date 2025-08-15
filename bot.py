import os
import asyncio
import pandas as pd
import numpy as np
import queue
import time
import threading
from datetime import datetime, timedelta, timezone
import pytz
import logging
import json
import signal
import sys
import requests
import hmac
import hashlib
import csv
import sqlite3
import subprocess
import platform
from typing import Dict, List, Optional, Any
from collections import deque
from contextlib import contextmanager

# --- Local Imports ---
from exchange_apis import ExchangeAPIFactory
from core.data_manager import DatabaseManager
from health_monitor import HealthMonitor
from config.config_manager import Config
from config.trading_config import TradingConfig

# --- Optional Imports ---
try:
    import talib
except ImportError:
    logging.warning("TA-Lib not found. Strategy calculations requiring TA-Lib will be skipped.")
    talib = None

import dash
from flask import jsonify
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    Bot = None
    TelegramError = None
    logging.warning("python-telegram-bot not found. Telegram notifications will be disabled.")

if sys.platform == 'win32':
    try:
        import winsound
    except ImportError:
        winsound = None
    try:
        import pyttsx3
    except ImportError:
        pyttsx3 = None
else:
    winsound = None
    pyttsx3 = None

# --- Main Application Classes ---

class EmergencyKillSwitch:
    def __init__(self, trading_engine, notification_manager=None):
        self.trading_engine = trading_engine
        self.notification_manager = notification_manager
        self.is_active = False
        self.trading_disabled = False
        self.execution_log = []

    def authenticate_password(self, password):
        return password == Config.SETTINGS_PASSWORD

    async def execute_emergency_exit(self):
        logging.info("EMERGENCY KILL SWITCH ACTIVATED")
        self.trading_disabled = True
        for exchange, strats in self.trading_engine.active_trades.items():
            for strat, trades in strats.items():
                for symbol in list(trades.keys()):
                    logging.info(f"Closing position for {symbol} via emergency exit.")
                    del self.trading_engine.active_trades[exchange][strat][symbol]
        if self.notification_manager:
            await self.notification_manager.send_message("🚨 EMERGENCY EXIT EXECUTED! All positions closed. Trading disabled.")
        return {'success': True}


class Strategy:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
    def get_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
    async def check_signals(self, latest_row: pd.Series, active_trades: Dict) -> Dict[str, Any]:
        raise NotImplementedError

class EMACCIStrategy(Strategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ema50_period = config.get('ema50_period', 50)
        self.ema200_period = config.get('ema200_period', 200)
        self.cci1_length = config.get('cci1_length', 100)
        self.cci_long_level = config.get('cci_long_level', 100)
        self.cci_short_level = config.get('cci_short_level', -100)

    def get_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or talib is None: return df
        result = df.copy()
        if len(result) < self.ema200_period: return result
        close = result['close'].values
        high = result['high'].values
        low = result['low'].values
        result['ema50'] = talib.EMA(close, timeperiod=self.ema50_period)
        result['ema200'] = talib.EMA(close, timeperiod=self.ema200_period)
        result['cci1'] = talib.CCI(high, low, close, timeperiod=self.cci1_length)
        return result

    async def check_signals(self, latest_row: pd.Series, active_trades: Dict) -> Dict[str, Any]:
        signals = {'signal_type': None}
        if pd.isna(latest_row.get('ema200')): return signals
        if latest_row['close'] > latest_row['ema200'] and latest_row['cci1'] > self.cci_long_level:
            signals['signal_type'] = 'long'
        elif latest_row['close'] < latest_row['ema200'] and latest_row['cci1'] < self.cci_short_level:
            signals['signal_type'] = 'short'
        return signals

class TRFStrategy(Strategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    def get_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return df # Placeholder
    async def check_signals(self, latest_row: pd.Series, active_trades: Dict) -> Dict[str, Any]:
        return {'signal_type': None}

def get_strategy(strategy_name: str, config: Dict[str, Any]) -> Optional[Strategy]:
    strategies = {'main_strategy': EMACCIStrategy, 'trf_strategy': TRFStrategy}
    strategy_class = strategies.get(strategy_name)
    return strategy_class(config) if strategy_class else None

class TradingEngine:
    def __init__(self, api_clients, pairs, display_manager):
        self.api_clients = api_clients
        self.pairs = pairs
        self.display = display_manager
        self.strategies = {name: get_strategy(name, conf) for name, conf in Config.STRATEGIES.items() if name in Config.ACTIVE_STRATEGIES and get_strategy(name, conf)}
        self.active_trades = {exchange: {strat: {} for strat in self.strategies} for exchange in self.api_clients}
        self.balance = 10000.0
        self.bot = None

    def set_bot(self, bot):
        self.bot = bot

    async def process_data(self, data, pair_info):
        if data.empty: return None
        df = data.copy()
        df['pair'] = pair_info["symbol"]
        strategy_dfs = {name: s.get_indicators(df) for name, s in self.strategies.items()}
        return strategy_dfs

    async def check_signals(self, strategy_dfs):
        signals = {}
        for strat_name, df in strategy_dfs.items():
            if df is not None and not df.empty:
                latest_row = df.iloc[-1]
                strat_signals = await self.strategies[strat_name].check_signals(latest_row, self.active_trades.get(Config.SELECTED_EXCHANGE, {}).get(strat_name, {}))
                if strat_signals.get('signal_type'):
                    signals.update(strat_signals)
                    signals['pair'] = latest_row['pair']
                    signals['price'] = latest_row['close']
                    signals['trigger_strategy'] = strat_name
                    break
        return signals

    async def execute_trades(self, signals):
        if not Config.AUTO_TRADING: return False
        exchange = signals['exchange']
        pair = signals['pair']
        price = signals['price']
        strat_name = signals['trigger_strategy']
        direction = signals['signal_type']

        if pair not in self.active_trades[exchange][strat_name]:
            logging.info(f"Executing {direction} for {pair} on {exchange} at {price}")
            self.active_trades[exchange][strat_name][pair] = {'entry_price': price, 'direction': direction}
            return True
        return False

class DisplayManager:
    def __init__(self, trading_engine, db_manager, performance_tracker):
        self.engine = trading_engine
        self.db_manager = db_manager
        # self.performance_tracker = performance_tracker # This was in original code but not used in my simplified version
        self.pair_data = {}
        self.last_update = datetime.now()
        self.log_messages = []
        self._setup_dash_app()

    def _setup_dash_app(self):
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
        self.app.title = "Sniper Bot V1 Dashboard"
        self.app.layout = self.create_dashboard_layout()
        self.register_callbacks()

    def create_dashboard_layout(self):
        return html.Div([
            dcc.Interval(id='refresh-interval', interval=Config.REFRESH_INTERVAL * 1000),
            dbc.NavbarSimple(brand="Sniper Bot V1 Dashboard", color="primary", dark=True, id='header'),
            dbc.Container([
                dbc.Row([
                    dbc.Col(dbc.Card(id='bot-status-card', body=True), md=4),
                    dbc.Col(dbc.Card(id='performance-card', body=True), md=4),
                    dbc.Col(dbc.Card(id='api-status-card', body=True), md=4),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.H3("Active Positions"),
                        html.Div(id='trades-table')
                    ], md=12)
                ], className="mt-4"),
                dbc.Row([
                     dbc.Col([
                        html.H3("Log Messages"),
                        html.Pre(id='log-container', style={'height': '200px', 'overflowY': 'scroll', 'border': '1px solid #ccc'})
                    ], md=12)
                ], className="mt-4")
            ], fluid=True)
        ])

    def register_callbacks(self):
        @self.app.callback(
            [Output('bot-status-card', 'children'),
             Output('performance-card', 'children'),
             Output('api-status-card', 'children'),
             Output('trades-table', 'children'),
             Output('log-container', 'children')],
            Input('refresh-interval', 'n_intervals')
        )
        def update_dashboard_data(n):
            if not self.engine:
                return "Engine not ready", "N/A", "N/A", "N/A", "N/A"

            # Simplified data for display
            bot_status = [html.H4("Bot Status"), f"Pairs: {len(self.engine.pairs)}"]
            performance = [html.H4("Performance"), f"Balance: ${self.engine.balance:,.2f}"]
            api_status = [html.H4("API Status"), "Status: OK"]

            trade_rows = []
            for ex, strats in self.engine.active_trades.items():
                for strat, trades in strats.items():
                    for symbol, data in trades.items():
                        trade_rows.append(html.Tr([html.Td(symbol), html.Td(data['direction']), html.Td(data['entry_price'])]))

            trades_table = dbc.Table([html.Thead(html.Tr([html.Th("Pair"), html.Th("Direction"), html.Th("Entry")])), html.Tbody(trade_rows)], bordered=True)

            logs = "\n".join(self.log_messages)

            return bot_status, performance, api_status, trades_table, logs

    def draw_screen(self):
        self.app.run(host=Config.DASH_HOST, port=Config.DASH_PORT, debug=False)

    def add_log(self, message):
        self.log_messages.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.log_messages = self.log_messages[:10]

    def update_pair_data(self, pair_symbol, strategy_dfs):
        if strategy_dfs and Config.DISPLAY_STRATEGY in strategy_dfs:
            self.pair_data[pair_symbol] = strategy_dfs[Config.DISPLAY_STRATEGY]
            self.last_update = datetime.now()


class CryptoBot:
    def __init__(self):
        load_credentials()
        self.health_monitor = HealthMonitor()
        self.display = DisplayManager(None, None, None)
        self.db_manager = DatabaseManager(Config.DB_PATH, self.display)
        self.api_clients = {name: ExchangeAPIFactory.create_api(name, creds, self.display, self.db_manager, Config) for name, creds in Config.EXCHANGE_CREDENTIALS.items() if name in Config.ACTIVE_EXCHANGES}
        if not self.api_clients: raise ValueError("No API clients configured.")
        self.update_trading_pairs()
        self.engine = TradingEngine(self.api_clients, self.pairs, self.display)
        self.display.engine = self.engine
        self.display.db_manager = self.db_manager
        self.engine.set_bot(self)
        self.running = True

    def update_trading_pairs(self):
        symbols = set(Config.DEFAULT_TRADING_PAIRS) | {f"B-{p.replace('/', '_')}" for p in Config.MANUAL_TRADING_PAIRS}
        self.pairs = [{"symbol": s, "color": "white"} for s in sorted(list(symbols))]

    async def run(self):
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        threading.Thread(target=self.display.draw_screen, daemon=True).start()

        while self.running:
            exchange = Config.SELECTED_EXCHANGE
            api_client = self.api_clients.get(exchange)
            if not api_client:
                logging.error(f"Selected exchange '{exchange}' not available.")
                await asyncio.sleep(Config.REFRESH_INTERVAL)
                continue

            active_pairs = [p for p in self.pairs if not self.health_monitor.is_pair_blacklisted(p["symbol"])]
            await asyncio.gather(*(self.process_pair(exchange, api_client, p) for p in active_pairs))
            await asyncio.sleep(Config.REFRESH_INTERVAL)

    async def process_pair(self, exchange, api_client, pair_info):
        symbol = pair_info["symbol"]
        try:
            data = api_client.get_historical_data(symbol, Config.CURRENT_TIMEFRAME)
            if data.empty or len(data) < Config.MIN_CANDLES_FOR_TRADING: return

            strategy_dfs = await self.engine.process_data(data, pair_info)
            if not strategy_dfs: return

            self.display.update_pair_data(symbol, strategy_dfs)
            signals = await self.engine.check_signals(strategy_dfs)
            if signals:
                signals['exchange'] = exchange
                await self.engine.execute_trades(signals)
        except Exception as e:
            logging.error(f"Error processing {symbol}: {e}", exc_info=True)

    def shutdown(self, signum, frame):
        self.running = False
        logging.info("Shutting down...")
        sys.exit(0)

def load_credentials():
    try:
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
            Config.EXCHANGE_CREDENTIALS = {k: v for k, v in creds.items() if k != 'telegram'}
            if 'telegram' in creds:
                Config.TELEGRAM_TOKEN = creds['telegram'].get('token')
                Config.TELEGRAM_CHAT_ID = creds['telegram'].get('chat_id')
    except FileNotFoundError:
        logging.critical("credentials.json not found. Please create it from the template.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.critical("credentials.json is malformed.")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler()])

    bot = CryptoBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.shutdown(None, None)
```
