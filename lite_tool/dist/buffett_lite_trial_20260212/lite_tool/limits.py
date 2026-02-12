from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict

from .config import MAX_DAILY_RUNS, STATE_DIR, STATE_FILE


def _default_state(today: str) -> Dict[str, object]:
    return {"date": today, "count": 0}


def _load_raw_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def get_today_state() -> Dict[str, object]:
    today = date.today().isoformat()
    raw = _load_raw_state(STATE_FILE)
    if raw.get("date") != today:
        return _default_state(today)
    count = int(raw.get("count", 0))
    if count < 0:
        count = 0
    if count > MAX_DAILY_RUNS:
        count = MAX_DAILY_RUNS
    return {"date": today, "count": count}


def save_state(state: Dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def runs_remaining() -> int:
    state = get_today_state()
    return max(0, MAX_DAILY_RUNS - int(state["count"]))


def consume_run() -> int:
    state = get_today_state()
    state["count"] = min(MAX_DAILY_RUNS, int(state["count"]) + 1)
    save_state(state)
    return int(state["count"])

