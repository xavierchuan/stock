from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

# Ensure imports work even when streamlit is launched outside project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lite_tool.akshare_provider import AKShareProvider, Candidate, DataProviderError
from lite_tool.config import (
    DISCLAIMER,
    FACTOR_HELP_TEXT,
    MAX_DAILY_RUNS,
    MAX_UNIVERSE_SIZE,
    METRIC_HELP_TEXT,
    PRODUCT_NAME,
    SIGNAL_DISPLAY_MAP,
    XHS_NOTES_URL,
)
from lite_tool.limits import consume_run, runs_remaining
from lite_tool.licensing import (
    LicenseError,
    get_machine_code,
    resolve_license_path,
    resolve_public_key_path,
    verify_license_file,
)
from lite_tool.scoring import evaluate_candidate


st.set_page_config(page_title=PRODUCT_NAME, layout="wide")

# Hide Streamlit chrome (toolbar/menu/deploy) for end users.
st.markdown(
    """
    <style>
      [data-testid="stToolbar"] { display: none !important; }
      [data-testid="stDecoration"] { display: none !important; }
      #MainMenu { visibility: hidden !important; }
      footer { visibility: hidden !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

provider = AKShareProvider()


def require_license_enabled() -> bool:
    return os.getenv("LITE_REQUIRE_LICENSE", "0").strip().lower() in {"1", "true", "yes"}


def render_license_gate() -> None:
    machine_code = get_machine_code()
    key_path = resolve_public_key_path()
    lic_path = resolve_license_path()

    st.subheader("授权验证")
    st.caption(f"设备码：`{machine_code}`")

    if key_path is None:
        st.error("未找到 public_key.pem，无法校验授权。")
        st.stop()
    if lic_path is None:
        st.error("未找到 license.key。请联系服务方获取授权文件后重试。")
        st.stop()

    try:
        lic = verify_license_file(lic_path, key_path, machine_code=machine_code)
    except LicenseError as exc:
        st.error(f"授权校验失败：{exc}")
        st.stop()

    st.success(f"授权有效：{lic.license_id}（到期日 {lic.expires_at}）")


def parse_codes(raw_text: str) -> List[str]:
    items = re.split(r"[\s,，;；]+", raw_text.strip())
    codes = []
    for item in items:
        if not item:
            continue
        code = item.upper().replace(".SH", "").replace(".SZ", "")
        if code.isdigit() and len(code) == 6:
            codes.append(code)
    deduped = []
    seen = set()
    for code in codes:
        if code not in seen:
            seen.add(code)
            deduped.append(code)
    return deduped


def display_signal(raw_signal: str) -> str:
    return SIGNAL_DISPLAY_MAP.get(raw_signal, raw_signal)


@st.cache_data(ttl=900, show_spinner=False)
def cached_auto_candidates(limit: int) -> List[Candidate]:
    return provider.get_auto_candidates(limit=limit)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_history(code: str) -> pd.DataFrame:
    return provider.get_history(symbol=code)


st.title(PRODUCT_NAME)
st.caption("免费体验版：仅1个战法（巴菲特）| 每天最多3次运行 | 仅显示前3只候选")
st.warning(DISCLAIMER, icon="⚠️")
st.info("官方声明：Lite 体验版长期免费（0元）。请勿购买该免费安装包。", icon="ℹ️")

if require_license_enabled():
    render_license_gate()
else:
    st.caption(f"当前为开放试用模式（未启用授权校验）。设备码：`{get_machine_code()}`")

remaining = runs_remaining()
st.metric("今日剩余运行次数", f"{remaining}/{MAX_DAILY_RUNS}")

if remaining <= 0:
    st.error("今天的免费运行次数已用完。明天会自动恢复3次。")
    st.stop()

universe_mode = st.radio(
    "候选池来源",
    options=["自选股票池", "自动候选池（按成交额）"],
    index=1,
    horizontal=True,
)

with st.form("lite_form"):
    input_codes = ""
    auto_limit = 20
    if universe_mode == "自选股票池":
        input_codes = st.text_area(
            "输入股票代码（最多30只，逗号/空格分隔）",
            value="600519 000858 600036 000333 601318 000001",
            help="示例：600519, 000858, 600036",
        )
    else:
        auto_limit = st.slider(
            "自动候选池大小（免费版上限30只）",
            min_value=10,
            max_value=MAX_UNIVERSE_SIZE,
            value=20,
            step=5,
        )
    submitted = st.form_submit_button("运行 Lite 体检（消耗1次）", type="primary")


if submitted:
    candidates: List[Candidate] = []
    if universe_mode == "自选股票池":
        codes = parse_codes(input_codes)
        if not codes:
            st.error("请至少输入1个合法A股代码（6位数字）。")
            st.stop()
        if len(codes) > MAX_UNIVERSE_SIZE:
            st.info(f"免费版最多评估{MAX_UNIVERSE_SIZE}只，已自动截断。")
            codes = codes[:MAX_UNIVERSE_SIZE]
        name_map: Dict[str, str] = {}
        try:
            name_map = provider.resolve_names(codes)
        except Exception:  # pragma: no cover
            name_map = {}
        unresolved = [code for code in codes if code not in name_map]
        if unresolved:
            st.info(
                f"有 {len(unresolved)} 只股票名称暂未解析，已用代码展示，不影响体检结果。"
            )
        candidates = [Candidate(code=c, name=name_map.get(c, c)) for c in codes]
    else:
        try:
            candidates = cached_auto_candidates(limit=auto_limit)
        except DataProviderError as exc:
            st.error(str(exc))
            st.stop()
        except Exception as exc:  # pragma: no cover
            st.error(f"自动候选池加载失败：{exc}")
            st.stop()

    st.write(f"本次候选池数量：{len(candidates)}")
    progress = st.progress(0)
    results = []
    errors = []
    for i, cand in enumerate(candidates):
        try:
            hist = cached_history(cand.code)
            result = evaluate_candidate(cand.code, cand.name, hist)
            results.append(result.to_dict())
        except Exception as exc:
            errors.append(f"{cand.code} 失败: {exc}")
        progress.progress((i + 1) / len(candidates))

    if not results:
        st.error("本次未生成有效结果，请稍后重试。")
        if errors:
            st.info("本次数据源波动较大，建议稍后重试。")
        st.stop()

    consume_run()

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    top3 = df.head(3).copy()
    top3["signal_display"] = top3["signal"].map(display_signal)

    best = top3.iloc[0]
    best_signal = str(best["signal_display"])
    review_tip = "建议做二次复核（结合行业与基本面）"
    if best_signal == "先回避" or str(best["risk_tag"]) == "高风险":
        review_tip = "建议先回避高波动，再做复核"

    st.subheader("先看结论（新手版）")
    st.caption(
        "这是一个股票体检和候选筛选工具，帮你先看风险与优先级，不直接给买卖指令。"
    )
    st.caption(
        "巴菲特战法 Lite 是一个巴菲特风格的简化体检：用估值、质量、动量、波动四个维度给股票打分。"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**工具用途**")
        st.write("先筛候选，不是买卖指令。")
    with col2:
        st.markdown("**当前结论**")
        st.write(f"{best['name']}：{best_signal}")
    with col3:
        st.markdown("**是否建议复核**")
        st.write(review_tip)

    st.link_button("看原理和教学（小红书）", XHS_NOTES_URL)

    simple_display = top3[["code", "name", "signal_display", "risk_tag"]].rename(
        columns={
            "code": "代码",
            "name": "名称",
            "signal_display": "结论",
            "risk_tag": "风险标签",
        }
    )

    st.subheader("今日候选 Top 3（免费版仅展示前3只）")
    st.dataframe(simple_display, use_container_width=True, hide_index=True)

    st.subheader("一句话解释")
    st.success(f"当前最优候选：{best['name']}（{best_signal}，{best['risk_tag']}）")
    st.write(best["explanation"])

    with st.expander("进阶数据（想看原理再展开）", expanded=False):
        st.markdown("#### 三项指标")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("近60日涨跌(%)", f"{best['return_60d']}")
            st.caption(METRIC_HELP_TEXT["return_60d"])
        with m2:
            st.metric("年化波动(%)", f"{best['annual_volatility']}")
            st.caption(METRIC_HELP_TEXT["annual_volatility"])
        with m3:
            st.metric("最大回撤(%)", f"{best['max_drawdown']}")
            st.caption(METRIC_HELP_TEXT["max_drawdown"])

        st.markdown("#### 四因子分数（0-100）")
        factors = [
            ("估值分", "valuation_score"),
            ("质量分", "quality_score"),
            ("动量分", "momentum_score"),
            ("波动分", "volatility_score"),
        ]
        for label, field in factors:
            score_value = float(best[field])
            st.markdown(f"**{label}：{score_value:.1f} 分**")
            st.progress(max(0.0, min(1.0, score_value / 100.0)))
            st.caption(FACTOR_HELP_TEXT[field])

    if errors:
        st.info(f"有 {len(errors)} 只股票因数据问题跳过，不影响 Top 3 结果。")
        st.caption("为保证页面易读，技术报错已默认隐藏。")

    st.markdown("---")
    st.caption("完整版可解锁：完整榜单、结果导出、7天答疑与30天更新。")
