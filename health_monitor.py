import time
import logging

class HealthMonitor:
    def __init__(self):
        self.api_failures = {}
        self.db_failures = 0
        self.last_successful_cycle = time.time()
        self.pair_blacklist = set()
        self.bot = None

    def set_bot(self, bot):
        self.bot = bot

    def record_api_failure(self, pair):
        self.api_failures[pair] = self.api_failures.get(pair, 0) + 1
        if self.api_failures[pair] > 5:
            self.blacklist_pair(pair)

    def record_db_failure(self):
        self.db_failures += 1

    def record_successful_cycle(self):
        self.last_successful_cycle = time.time()

    def blacklist_pair(self, pair):
        if pair not in self.pair_blacklist:
            self.pair_blacklist.add(pair)
            logging.warning(f"Blacklisting pair {pair} due to repeated API failures.")
            if self.bot and hasattr(self.bot, 'display'):
                self.bot.display.add_log(f"Pair {pair} blacklisted.")

    def is_pair_blacklisted(self, pair):
        return pair in self.pair_blacklist

    def check_blacklist(self):
        # Periodically try to re-enable blacklisted pairs
        # For simplicity, this is not implemented here but could be a cron job or timed event
        pass

    def check_process_health(self, refresh_interval):
        time_since_success = time.time() - self.last_successful_cycle
        if time_since_success > refresh_interval * 5:
            logging.warning("Bot has not had a successful cycle in 5 intervals. Possible issue.")
            if self.bot and hasattr(self.bot, 'display'):
                self.bot.display.add_log("Warning: Bot may be stuck or experiencing issues.")

    def get_health_status(self):
        return {
            "api_failures": self.api_failures,
            "db_failures": self.db_failures,
            "last_successful_cycle": time.ctime(self.last_successful_cycle),
            "blacklisted_pairs": list(self.pair_blacklist)
        }
