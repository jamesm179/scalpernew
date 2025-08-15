import sqlite3
import pandas as pd
import logging
import queue
import threading
import time
from contextlib import contextmanager
import asyncio

class DatabaseConnectionPool:
    def __init__(self, db_path, max_connections=50, timeout=15):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.pool = queue.Queue(maxsize=max_connections)
        self.active_connections = 0
        self.pool_lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        for _ in range(min(3, self.max_connections)):
            try:
                conn = self._create_optimized_connection()
                self.pool.put(conn, block=False)
                self.active_connections += 1
            except Exception as e:
                logging.error(f"Error initializing connection pool: {e}")

    def _create_optimized_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-30000")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def get_connection(self):
        try:
            return self.pool.get(block=True, timeout=self.timeout)
        except queue.Empty:
            raise Exception("Database connection timeout")

    def return_connection(self, conn):
        if conn:
            self.pool.put(conn)

    @contextmanager
    def get_connection_context(self):
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)


class DatabaseManager:
    def __init__(self, db_path, display_manager):
        self.pool = DatabaseConnectionPool(db_path)
        self.display = display_manager
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS candles (
                    pair TEXT,
                    interval TEXT,
                    open_time INTEGER,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    PRIMARY KEY (pair, interval, open_time)
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_pair_interval_time ON candles (pair, interval, open_time DESC)")
            conn.commit()

    def save_candle_data(self, df, pair, interval):
        if df.empty:
            return
        with self.pool.get_connection_context() as conn:
            try:
                # Use a transaction for bulk inserts
                df_tuples = [tuple(x) for x in df[['open_time', 'open', 'high', 'low', 'close', 'volume']].to_numpy()]
                sql = f"INSERT OR REPLACE INTO candles (pair, interval, open_time, open, high, low, close, volume) VALUES ('{pair}', '{interval}', ?, ?, ?, ?, ?, ?)"
                conn.executemany(sql, df_tuples)
                conn.commit()
            except Exception as e:
                logging.error(f"Error saving candle data for {pair} ({interval}): {e}")


    def get_candle_data(self, pair, limit, timeframe=None):
        with self.pool.get_connection_context() as conn:
            query = "SELECT * FROM candles WHERE pair = ? AND interval = ? ORDER BY open_time DESC LIMIT ?"
            df = pd.read_sql_query(query, conn, params=(pair, timeframe, limit))
            if not df.empty:
                # open_time is stored as integer milliseconds
                df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            return df.sort_values('open_time').reset_index(drop=True)

    def get_latest_candle_time(self, pair):
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(open_time) FROM candles WHERE pair = ?", (pair,))
            result = cursor.fetchone()[0]
            return pd.to_datetime(result, unit='ms') if result else None

    def clear_cache_for_pair(self, pair_symbol):
        with self.pool.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM candles WHERE pair = ?", (pair_symbol,))
            conn.commit()
            return cursor.rowcount
