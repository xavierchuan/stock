from __future__ import annotations

import os
import re
import sys
import time
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
    AUTO_FILL_POOL_SIZE,
    AUTO_FILL_TARGET,
    DISCLAIMER,
    FACTOR_HELP_TEXT,
    MAX_DAILY_RUNS,
    MAX_UNIVERSE_SIZE,
    METRIC_HELP_TEXT,
    MIN_SUCCESS_TO_CHARGE,
    PRODUCT_NAME,
    RUNTIME_BUDGET_SECONDS,
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
      .stApp {
        background: radial-gradient(circle at 5% 0%, #f6fbff 0%, #f9fbfd 35%, #ffffff 100%);
      }
      [data-testid="stToolbar"] { display: none !important; }
      [data-testid="stDecoration"] { display: none !important; }
      #MainMenu { visibility: hidden !important; }
      footer { visibility: hidden !important; }
      [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6edf5;
        border-radius: 12px;
        padding: 10px 12px;
      }
      div[data-testid="stStatusWidget"] {
        border: 1px solid #dbe7f5;
        border-radius: 12px;
      }
      div.stButton > button:first-child,
      div[data-testid="stFormSubmitButton"] > button:first-child {
        border-radius: 10px;
        font-weight: 700;
      }
      .note-card {
        background: #ffffff;
        border: 1px solid #e6edf5;
        border-radius: 12px;
        padding: 12px 14px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

provider = AKShareProvider()
MANUAL_UNIVERSE_LABEL = "我自己填股票代码"
AUTO_UNIVERSE_LABEL = "系统帮我选（热门成交股票）"


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
debug_mode = st.toggle("调试模式（显示原始报错）", value=False)

if remaining <= 0:
    st.error("今天的免费运行次数已用完。明天会自动恢复3次。")
    st.stop()

universe_mode = st.radio(
    "候选池来源",
    options=[MANUAL_UNIVERSE_LABEL, AUTO_UNIVERSE_LABEL],
    index=1,
    horizontal=True,
)
if universe_mode == AUTO_UNIVERSE_LABEL:
    st.caption("系统会先从当日成交活跃的股票里选一批，再帮你做体检。")
else:
    st.caption("只评估你输入的股票代码，更适合有明确关注名单的情况。")

with st.form("lite_form"):
    input_codes = ""
    auto_limit = 20
    if universe_mode == MANUAL_UNIVERSE_LABEL:
        input_codes = st.text_area(
            "输入股票代码（最多30只，逗号/空格分隔）",
            value="600519 000858 600036 000333 601318 000001",
            help="示例：600519, 000858, 600036",
        )
    else:
        auto_limit = st.slider(
            "系统自动选股数量（免费版上限30只）",
            min_value=10,
            max_value=MAX_UNIVERSE_SIZE,
            value=20,
            step=5,
        )
    submitted = st.form_submit_button("运行 Lite 体检（消耗1次）", type="primary")
    st.caption("点击后会进入处理中（约30-60秒），请勿重复点击。")


if submitted:
    run_status = st.status("正在处理，请勿重复点击", expanded=True)
    run_status.write("步骤1/3：准备候选池")

    started_at = time.time()
    budget_exhausted = False
    candidates: List[Candidate] = []
    errors: List[str] = []
    attempted_codes = set()
    network_fail_count = 0
    data_fail_count = 0

    if universe_mode == MANUAL_UNIVERSE_LABEL:
        codes = parse_codes(input_codes)
        if not codes:
            run_status.update(label="处理失败", state="error", expanded=True)
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
            with st.spinner("正在获取热门候选股票，首次可能需要30-60秒，请稍等..."):
                candidates = cached_auto_candidates(limit=auto_limit)
        except DataProviderError:
            run_status.update(label="处理失败", state="error", expanded=True)
            st.error("暂时没拿到自动候选池数据，请稍后重试。")
            st.stop()
        except Exception:  # pragma: no cover
            run_status.update(label="处理失败", state="error", expanded=True)
            st.error("自动候选池加载失败，请稍后重试。")
            st.stop()

    if not candidates:
        run_status.update(label="处理失败", state="error", expanded=True)
        st.error("本次未获得可用候选池，请稍后重试。")
        st.stop()

    st.write(f"本次候选池数量：{len(candidates)}")
    run_status.write("步骤2/3：计算体检结果")
    progress = st.progress(0)
    results = []

    processed_count = 0
    expected_count = len(candidates)
    for cand in candidates:
        if time.time() - started_at > RUNTIME_BUDGET_SECONDS:
            budget_exhausted = True
            break
        processed_count += 1
        attempted_codes.add(cand.code)
        hist, err_type, err_text = provider.get_history_safe(cand.code)
        if hist is None:
            if err_type == "network":
                network_fail_count += 1
            else:
                data_fail_count += 1
            errors.append(f"{cand.code} 失败: {err_text}")
            progress.progress(min(processed_count / max(expected_count, 1), 1.0))
            continue
        try:
            result = evaluate_candidate(cand.code, cand.name, hist)
            results.append(result.to_dict())
        except Exception as exc:
            data_fail_count += 1
            errors.append(f"{cand.code} 评分失败: {exc}")
        progress.progress(min(processed_count / max(expected_count, 1), 1.0))

    if (
        universe_mode == MANUAL_UNIVERSE_LABEL
        and len(results) < AUTO_FILL_TARGET
        and not budget_exhausted
    ):
        run_status.write("步骤2/3：自选结果不足3只，正在自动补位")
        try:
            supplement_pool = cached_auto_candidates(limit=min(MAX_UNIVERSE_SIZE, AUTO_FILL_POOL_SIZE))
        except Exception:
            supplement_pool = []
        supplement_candidates = [c for c in supplement_pool if c.code not in attempted_codes]
        needed = AUTO_FILL_TARGET - len(results)
        expected_count += min(len(supplement_candidates), max(needed, 0))
        for cand in supplement_candidates:
            if needed <= 0:
                break
            if time.time() - started_at > RUNTIME_BUDGET_SECONDS:
                budget_exhausted = True
                break
            processed_count += 1
            attempted_codes.add(cand.code)
            hist, err_type, err_text = provider.get_history_safe(cand.code)
            if hist is None:
                if err_type == "network":
                    network_fail_count += 1
                else:
                    data_fail_count += 1
                errors.append(f"{cand.code} 补位失败: {err_text}")
                progress.progress(min(processed_count / max(expected_count, 1), 1.0))
                continue
            try:
                result = evaluate_candidate(cand.code, cand.name, hist)
                results.append(result.to_dict())
                needed -= 1
            except Exception as exc:
                data_fail_count += 1
                errors.append(f"{cand.code} 补位评分失败: {exc}")
            progress.progress(min(processed_count / max(expected_count, 1), 1.0))

    if not results:
        run_status.update(label="处理失败", state="error", expanded=True)
        st.error("本次未生成有效结果，请稍后重试。")
        if errors:
            st.info("本次数据源波动较大，建议稍后重试。")
            if debug_mode:
                st.code("\n".join(errors[:12]))
        st.stop()

    success_count = len(results)
    failed_count = len(errors)
    attempted_count = success_count + failed_count

    charged = success_count >= MIN_SUCCESS_TO_CHARGE
    if charged:
        consume_run()
    else:
        st.warning(
            f"本次仅成功 {success_count} 只，未达到{MIN_SUCCESS_TO_CHARGE}只，不扣次数。可稍后重试。"
        )

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

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**工具用途**")
        st.write("先筛候选，不是买卖指令。")
    with col2:
        st.markdown("**当前结论**")
        st.write(f"{best['name']}：{best_signal}")
    with col3:
        st.markdown("**是否建议复核**")
        st.write(review_tip)
    with col4:
        st.markdown("**本次计次**")
        st.write("已扣1次" if charged else "未扣次数")

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

    s1, s2, s3 = st.columns(3)
    s1.metric("尝试评估", attempted_count)
    s2.metric("成功", success_count)
    s3.metric("跳过", failed_count)

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

        st.markdown("#### 本次处理摘要")
        st.caption(
            f"网络问题跳过 {network_fail_count} 只，数据问题跳过 {data_fail_count} 只。"
        )
        if budget_exhausted:
            st.warning(f"已触发 {RUNTIME_BUDGET_SECONDS} 秒处理预算，提前结束本次运行。")
        if debug_mode and errors:
            st.code("\n".join(errors[:12]))

    if errors:
        st.info(f"有 {len(errors)} 只股票因数据问题跳过，不影响 Top 3 结果。")
        if not debug_mode:
            st.caption("为保证页面易读，技术报错已默认隐藏。")

    run_status.write("步骤3/3：结果已生成")
    run_status.update(label="处理完成", state="complete", expanded=False)

    st.markdown("---")
    st.caption("完整版可解锁：完整榜单、结果导出、7天答疑与30天更新。")
