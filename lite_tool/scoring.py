from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

import numpy as np
import pandas as pd


def _clip_0_100(value: float) -> float:
    return float(max(0.0, min(100.0, value)))


def _max_drawdown(closes: pd.Series) -> float:
    running_max = closes.cummax()
    dd = closes / running_max - 1.0
    return float(dd.min())


@dataclass
class ScoreResult:
    code: str
    name: str
    score: float
    signal: str
    risk_tag: str
    valuation_score: float
    quality_score: float
    momentum_score: float
    volatility_score: float
    return_60d: float
    annual_volatility: float
    max_drawdown: float
    explanation: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def evaluate_candidate(code: str, name: str, hist: pd.DataFrame) -> ScoreResult:
    close = pd.to_numeric(hist["close"], errors="coerce").dropna()
    if len(close) < 80:
        raise ValueError(f"{code} 历史收盘数据不足。")

    ret = close.pct_change().dropna()
    annual_vol = float(ret.std(ddof=0) * np.sqrt(252))
    mdd = _max_drawdown(close)

    if len(close) >= 61:
        return_60d = float(close.iloc[-1] / close.iloc[-61] - 1.0)
    else:
        return_60d = float(close.iloc[-1] / close.iloc[0] - 1.0)

    low, high = float(close.min()), float(close.max())
    if high > low:
        position = (float(close.iloc[-1]) - low) / (high - low)
    else:
        position = 0.5

    valuation_score = _clip_0_100((1.0 - position) * 100.0)
    quality_score = _clip_0_100((1.0 + mdd) * 100.0)
    momentum_score = _clip_0_100(((return_60d + 0.20) / 0.60) * 100.0)
    volatility_score = _clip_0_100(((0.50 - annual_vol) / 0.50) * 100.0)

    score = round(
        0.30 * valuation_score
        + 0.25 * quality_score
        + 0.25 * momentum_score
        + 0.20 * volatility_score,
        1,
    )

    if annual_vol > 0.45 or mdd < -0.40:
        risk_tag = "高风险"
    elif annual_vol > 0.30 or mdd < -0.25:
        risk_tag = "中风险"
    else:
        risk_tag = "低风险"

    if score >= 70 and momentum_score >= 55 and valuation_score >= 50:
        signal = "关注"
    elif score >= 55:
        signal = "观察"
    else:
        signal = "回避"

    factor_scores = {
        "估值": valuation_score,
        "质量": quality_score,
        "动量": momentum_score,
        "波动": volatility_score,
    }
    best_factor = max(factor_scores.items(), key=lambda x: x[1])[0]
    weak_factor = min(factor_scores.items(), key=lambda x: x[1])[0]
    explanation = f"{best_factor}相对占优，{weak_factor}偏弱；建议结合行业与基本面二次确认。"

    return ScoreResult(
        code=code,
        name=name,
        score=score,
        signal=signal,
        risk_tag=risk_tag,
        valuation_score=round(valuation_score, 1),
        quality_score=round(quality_score, 1),
        momentum_score=round(momentum_score, 1),
        volatility_score=round(volatility_score, 1),
        return_60d=round(return_60d * 100.0, 2),
        annual_volatility=round(annual_vol * 100.0, 2),
        max_drawdown=round(mdd * 100.0, 2),
        explanation=explanation,
    )

