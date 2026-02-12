from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

# Ensure imports work even when streamlit is launched outside project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lite_tool.akshare_provider import AKShareProvider, Candidate, DataProviderError
from lite_tool.config import DISCLAIMER, MAX_DAILY_RUNS, MAX_UNIVERSE_SIZE, PRODUCT_NAME
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

with st.form("lite_form"):
    universe_mode = st.radio(
        "候选池来源",
        options=["自选股票池", "自动候选池（按成交额）"],
        horizontal=True,
    )
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
        candidates = [Candidate(code=c, name=f"股票{c}") for c in codes]
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
            st.write("错误摘要：")
            st.code("\n".join(errors[:10]))
        st.stop()

    consume_run()

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    top3 = df.head(3).copy()
    display = top3[
        [
            "code",
            "name",
            "score",
            "signal",
            "risk_tag",
            "return_60d",
            "annual_volatility",
            "max_drawdown",
        ]
    ].rename(
        columns={
            "code": "代码",
            "name": "名称",
            "score": "体检分",
            "signal": "信号",
            "risk_tag": "风险标签",
            "return_60d": "近60日涨跌(%)",
            "annual_volatility": "年化波动(%)",
            "max_drawdown": "最大回撤(%)",
        }
    )
    st.subheader("今日候选 Top 3（免费版仅展示前3只）")
    st.dataframe(display, use_container_width=True, hide_index=True)

    best = top3.iloc[0]
    st.subheader("一句话解释")
    st.success(
        f"当前最优候选：{best['code']}（体检分 {best['score']}，{best['signal']}，{best['risk_tag']}）"
    )
    st.write(best["explanation"])

    with st.expander("查看四因子细分"):
        st.write(
            {
                "估值得分": best["valuation_score"],
                "质量得分": best["quality_score"],
                "动量得分": best["momentum_score"],
                "波动得分": best["volatility_score"],
            }
        )

    if errors:
        st.info(f"有 {len(errors)} 只股票因数据问题跳过，不影响 Top 3 结果。")
        st.code("\n".join(errors[:8]))

    st.markdown("---")
    st.caption("完整版可解锁：完整榜单、结果导出、7天答疑与30天更新。")
