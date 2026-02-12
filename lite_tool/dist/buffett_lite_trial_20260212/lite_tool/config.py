from pathlib import Path


PRODUCT_NAME = "巴菲特战法 Lite 体验版"
DISCLAIMER = "仅供研究与教育用途，不构成投资建议，不承诺收益。"
MAX_DAILY_RUNS = 3
MAX_UNIVERSE_SIZE = 30
MIN_HISTORY_BARS = 120
HISTORY_LOOKBACK_DAYS = 260
STATE_DIR = Path.home() / ".factor_lab_lite"
STATE_FILE = STATE_DIR / "run_limit.json"
CACHE_DIR = STATE_DIR / "cache"
