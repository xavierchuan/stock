from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import random
import time
from typing import Any, Callable, Dict, List, Tuple

import pandas as pd

from .config import FETCH_RETRIES, HISTORY_LOOKBACK_DAYS, MIN_HISTORY_BARS, RETRY_BASE_WAIT_SECONDS
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


def classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    network_signals = [
        "connection",
        "timeout",
        "timed out",
        "remote end closed",
        "ssl",
        "max retries",
        "http",
        "temporarily unavailable",
    ]
    return "network" if any(sig in msg for sig in network_signals) else "data"


def _call_with_retry(
    call: Callable[[], Any],
    retries: int = FETCH_RETRIES,
    wait_seconds: float = RETRY_BASE_WAIT_SECONDS,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return call()
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < retries:
                backoff = wait_seconds * (2 ** (attempt - 1))
                jitter = random.uniform(0.0, wait_seconds * 0.5)
                time.sleep(backoff + jitter)
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


def _clean_name(raw: object) -> str:
    name = str(raw).strip()
    if not name or name.lower() == "nan":
        return ""
    # Some quote feeds include spacing in Chinese names (e.g. "五 粮 液").
    return "".join(name.split())


class AKShareProvider:
    def _auto_cache_paths(self, cache_dir: Path, limit: int) -> List[Path]:
        exact = sorted(cache_dir.glob(f"auto_candidates_*_{limit}.csv"), reverse=True)
        if exact:
            return [p for p in exact if p.is_file()]
        return [p for p in sorted(cache_dir.glob("auto_candidates_*.csv"), reverse=True) if p.is_file()]

    def _load_auto_candidates_from_cache(self, cache_dir: Path, limit: int) -> List[Candidate]:
        for path in self._auto_cache_paths(cache_dir, limit):
            try:
                cached = pd.read_csv(path, dtype=str)
            except Exception:
                continue
            if cached.empty or "code" not in cached.columns:
                continue
            name_col = "name" if "name" in cached.columns else None
            candidates: List[Candidate] = []
            for _, row in cached.iterrows():
                code = str(row["code"]).strip()
                if not code or not code.isdigit() or len(code) != 6:
                    continue
                name = _clean_name(row[name_col]) if name_col else ""
                candidates.append(Candidate(code=code, name=name or code))
                if len(candidates) >= limit:
                    break
            if candidates:
                return candidates
        return []

    def _fetch_spot_dataframe(self) -> pd.DataFrame:
        ak = _import_akshare()
        errors: List[str] = []
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
        return df

    def _load_name_cache(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}
        try:
            df = pd.read_csv(path, dtype=str)
        except Exception:
            return {}
        if "code" not in df.columns or "name" not in df.columns:
            return {}

        code_series = df["code"].astype(str).str.extract(r"(\d{6})", expand=False)
        name_series = df["name"].astype(str).map(_clean_name)
        name_map: Dict[str, str] = {}
        for code, name in zip(code_series, name_series):
            if not isinstance(code, str):
                continue
            if not name:
                continue
            name_map[code] = name
        return name_map

    def _write_name_cache(self, path: Path, name_map: Dict[str, str]) -> None:
        rows = [{"code": code, "name": name} for code, name in sorted(name_map.items())]
        pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")

    def _name_cache_paths(self, cache_dir: Path) -> List[Path]:
        return [p for p in sorted(cache_dir.glob("stock_name_map_*.csv"), reverse=True) if p.is_file()]

    def resolve_names(self, codes: List[str]) -> Dict[str, str]:
        normalized_codes: List[str] = []
        for code in codes:
            try:
                normalized_codes.append(normalize_symbol(code))
            except ValueError:
                continue
        if not normalized_codes:
            return {}

        cache_dir = _ensure_cache_dir()
        today_key = date.today().strftime("%Y%m%d")
        today_cache_path = cache_dir / f"stock_name_map_{today_key}.csv"

        name_map = self._load_name_cache(today_cache_path)
        unresolved = [c for c in normalized_codes if c not in name_map]

        if unresolved:
            live_map: Dict[str, str] = {}
            try:
                spot = self._fetch_spot_dataframe().copy()
                code_col = _pick_first_existing(spot, ["代码", "symbol"])
                name_col = _pick_first_existing(spot, ["名称", "name"])
                spot[code_col] = spot[code_col].astype(str).str.extract(r"(\d{6})", expand=False)
                spot[name_col] = spot[name_col].astype(str).map(_clean_name)
                spot = spot.dropna(subset=[code_col, name_col])
                for _, row in spot.iterrows():
                    code = str(row[code_col])
                    name = _clean_name(row[name_col])
                    if not code or not code.isdigit() or len(code) != 6:
                        continue
                    if not name:
                        continue
                    live_map[code] = name
                if live_map:
                    self._write_name_cache(today_cache_path, live_map)
                    for code in unresolved:
                        if code in live_map:
                            name_map[code] = live_map[code]
            except Exception:
                fallback_paths = self._name_cache_paths(cache_dir)
                for fallback_path in fallback_paths:
                    fallback_map = self._load_name_cache(fallback_path)
                    for code in unresolved:
                        if code in fallback_map:
                            name_map[code] = fallback_map[code]
                    unresolved = [c for c in unresolved if c not in name_map]
                    if not unresolved:
                        break

        return {code: name_map[code] for code in normalized_codes if code in name_map}

    def get_auto_candidates(self, limit: int) -> List[Candidate]:
        cache_dir = _ensure_cache_dir()
        today_key = date.today().strftime("%Y%m%d")
        cache_path = cache_dir / f"auto_candidates_{today_key}_{limit}.csv"
        if cache_path.exists():
            today_cached = self._load_auto_candidates_from_cache(cache_dir, limit=limit)
            if today_cached:
                return today_cached

        try:
            spot = self._fetch_spot_dataframe().copy()
        except Exception as exc:
            fallback = self._load_auto_candidates_from_cache(cache_dir, limit=limit)
            if fallback:
                return fallback
            raise DataProviderError(f"自动候选池加载失败：{exc}") from exc

        code_col = _pick_first_existing(spot, ["代码", "symbol"])
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
            Candidate(code=row[code_col], name=_clean_name(row[name_col]) or str(row[code_col]))
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

    def get_history_safe(self, symbol: str) -> Tuple[pd.DataFrame | None, str | None, str | None]:
        try:
            hist = self.get_history(symbol)
            return hist, None, None
        except Exception as exc:
            return None, classify_error(exc), str(exc)
