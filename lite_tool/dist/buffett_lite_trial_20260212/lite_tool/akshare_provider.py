from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import time
from typing import Any, Callable, List

import pandas as pd

from .config import HISTORY_LOOKBACK_DAYS, MIN_HISTORY_BARS
from .config import CACHE_DIR


class DataProviderError(RuntimeError):
    pass


def _import_akshare():
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:
        raise DataProviderError(
            "未安装 akshare，请先执行: pip install -r requirements.txt"
        ) from exc
    return ak


def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "")
    if not s.isdigit() or len(s) != 6:
        raise ValueError(f"无效股票代码: {symbol}")
    return s


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str


def _call_with_retry(
    call: Callable[[], Any], retries: int = 3, wait_seconds: float = 1.2
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return call()
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < retries:
                time.sleep(wait_seconds * attempt)
    if last_error is None:
        raise DataProviderError("未知数据错误。")
    raise DataProviderError(str(last_error)) from last_error


def _ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _pick_first_existing(df: pd.DataFrame, columns: List[str]) -> str:
    for col in columns:
        if col in df.columns:
            return col
    raise DataProviderError(f"数据字段异常，未找到候选字段: {columns}")


class AKShareProvider:
    def get_auto_candidates(self, limit: int) -> List[Candidate]:
        ak = _import_akshare()
        cache_dir = _ensure_cache_dir()
        today_key = date.today().strftime("%Y%m%d")
        cache_path = cache_dir / f"auto_candidates_{today_key}_{limit}.csv"
        if cache_path.exists():
            cached = pd.read_csv(cache_path, dtype=str)
            if not cached.empty:
                return [
                    Candidate(code=row["code"], name=row["name"])
                    for _, row in cached.iterrows()
                ]

        errors = []
        df = None
        if hasattr(ak, "stock_zh_a_spot_em"):
            try:
                df = _call_with_retry(lambda: ak.stock_zh_a_spot_em())
            except Exception as exc:  # pragma: no cover
                errors.append(f"stock_zh_a_spot_em: {exc}")
        if (df is None or df.empty) and hasattr(ak, "stock_zh_a_spot"):
            try:
                df = _call_with_retry(lambda: ak.stock_zh_a_spot())
            except Exception as exc:  # pragma: no cover
                errors.append(f"stock_zh_a_spot: {exc}")
        if df is None or df.empty:
            detail = " | ".join(errors) if errors else "未知错误"
            raise DataProviderError(f"AKShare 未返回A股行情数据。{detail}")

        spot = df.copy()
        code_col = _pick_first_existing(spot, ["代码", "symbol", "代码"])
        name_col = _pick_first_existing(spot, ["名称", "name"])
        turnover_col = None
        for candidate_col in ["成交额", "amount", "成交量", "volume"]:
            if candidate_col in spot.columns:
                turnover_col = candidate_col
                break

        spot[code_col] = spot[code_col].astype(str).str.extract(r"(\d{6})", expand=False)
        spot = spot.dropna(subset=[code_col])
        if turnover_col:
            spot[turnover_col] = (
                pd.to_numeric(spot[turnover_col], errors="coerce").fillna(0.0)
            )
            spot = spot.sort_values(turnover_col, ascending=False)

        top = spot.head(limit)
        candidates = [
            Candidate(code=row[code_col], name=str(row[name_col]))
            for _, row in top.iterrows()
        ]
        pd.DataFrame([{"code": x.code, "name": x.name} for x in candidates]).to_csv(
            cache_path, index=False, encoding="utf-8"
        )
        return candidates

    def get_history(self, symbol: str) -> pd.DataFrame:
        ak = _import_akshare()
        code = normalize_symbol(symbol)
        cache_dir = _ensure_cache_dir()
        cache_path = cache_dir / f"hist_{code}.csv"
        if cache_path.exists():
            hist_cache = pd.read_csv(cache_path)
            if len(hist_cache) >= MIN_HISTORY_BARS:
                return hist_cache.tail(HISTORY_LOOKBACK_DAYS).reset_index(drop=True)

        start_date = (date.today() - timedelta(days=HISTORY_LOOKBACK_DAYS * 3)).strftime(
            "%Y%m%d"
        )
        end_date = date.today().strftime("%Y%m%d")

        df = _call_with_retry(
            lambda: ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        )
        if df is None or df.empty:
            raise DataProviderError(f"{code} 未获取到历史数据。")

        rename_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "turnover",
            "涨跌幅": "pct_change",
        }
        hist = df.rename(columns=rename_map).copy()
        required = ["date", "open", "high", "low", "close", "volume"]
        for col in required:
            if col not in hist.columns:
                raise DataProviderError(f"{code} 历史数据缺少字段: {col}")
        hist["close"] = pd.to_numeric(hist["close"], errors="coerce")
        hist = hist.dropna(subset=["close"])
        hist = hist[hist["close"] > 0]
        if len(hist) < MIN_HISTORY_BARS:
            raise DataProviderError(
                f"{code} 有效历史数据不足（{len(hist)} < {MIN_HISTORY_BARS}）。"
            )
        hist = hist.tail(HISTORY_LOOKBACK_DAYS).reset_index(drop=True)
        hist.to_csv(cache_path, index=False, encoding="utf-8")
        return hist
