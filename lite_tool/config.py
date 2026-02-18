from pathlib import Path


PRODUCT_NAME = "巴菲特战法 Lite 体验版"
DISCLAIMER = "仅供研究与教育用途，不构成投资建议，不承诺收益。"
XHS_NOTES_URL = "https://xhslink.com/m/80EYiAQzo6G"
SIGNAL_DISPLAY_MAP = {"关注": "优先看", "观察": "可观察", "回避": "先回避"}
METRIC_HELP_TEXT = {
    "return_60d": "近60个交易日涨跌幅，主要看近期趋势是否偏强。",
    "annual_volatility": "把日常波动换算到一年，越高代表价格更颠簸。",
    "max_drawdown": "历史上从高点到低点的最大跌幅，越大代表抗压要求更高。",
}
FACTOR_HELP_TEXT = {
    "valuation_score": "估值分：当前位置相对历史高低位，偏低通常更友好。",
    "quality_score": "质量分：历史回撤表现，回撤越温和分数越高。",
    "momentum_score": "动量分：近期走势强弱，趋势更稳分数更高。",
    "volatility_score": "波动分：价格稳定性，波动越小分数越高。",
}
MAX_DAILY_RUNS = 3
MAX_UNIVERSE_SIZE = 30
MIN_SUCCESS_TO_CHARGE = 3
RUNTIME_BUDGET_SECONDS = 35
FETCH_RETRIES = 2
RETRY_BASE_WAIT_SECONDS = 0.8
AUTO_FILL_TARGET = 3
AUTO_FILL_POOL_SIZE = 50
MIN_HISTORY_BARS = 120
HISTORY_LOOKBACK_DAYS = 260
STATE_DIR = Path.home() / ".factor_lab_lite"
STATE_FILE = STATE_DIR / "run_limit.json"
CACHE_DIR = STATE_DIR / "cache"
