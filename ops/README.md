# 小红书30天执行包

这个目录是可直接执行的运营资产，目标是用免费工具在30天内完成「涨粉 + 首批转化」。

## 文件说明

- `sku_pages.md`：店铺SKU标题、详情页结构、交付标准。
- `dm_sop.md`：评论回复、私信三段式、成交与售后脚本。
- `free_product_v1_execution.md`：Lite体验版7天落地排期、验收标准、风险默认策略。
- `../lite_tool/`：免费工具代码（AKShare + 每日3次限制 + Top3候选）。
- `content_calendar_30d.csv`：30天 x 每天2条内容排期（共60条）。
- `post_templates.md`：6个固定栏目模板和可直接复制的文案骨架。
- `lead_tracker_template.csv`：线索追踪表字段（含状态枚举）。
- `ab_test_tracker.csv`：A/B实验记录模板。
- `daily_ops_checklist.md`：每天60-90分钟执行清单。
- `compliance_checklist.md`：内容与私信合规检查。
- `weekly_review_template.md`：每周复盘模板。
- `funnel_report.py`：从线索CSV计算核心转化率。

## 快速开始（今天就能执行）

1. 把 `sku_pages.md` 的文案复制到小红书店铺商品详情。
2. 在小红书评论区统一使用关键词CTA：`评论“试用”`。
3. 用 `dm_sop.md` 话术回复评论和私信。
4. 按 `content_calendar_30d.csv` 发当天2条内容。
5. 每晚把数据写进 `lead_tracker_template.csv`（重点记录 `trial_id`、`trial_opened_at`、`runs_day1`、`limit_hit`、`offer_shown`）。
6. 每周日运行：

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/ops/funnel_report.py \
  /Users/chuan/Documents/Projects/Business/stock/ops/lead_tracker_template.csv
```

7. 免费工具本地启动（用于交付试用）：

```bash
python3 -m venv /Users/chuan/Documents/Projects/Business/stock/.venv
source /Users/chuan/Documents/Projects/Business/stock/.venv/bin/activate
pip install -r /Users/chuan/Documents/Projects/Business/stock/requirements.txt
streamlit run /Users/chuan/Documents/Projects/Business/stock/lite_tool/app.py
```

8. 生成可发用户的试用包（zip）：

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/lite_tool/build_trial_bundle.py
```

## 本月目标

- 精准粉丝：1000
- 线索响应：评论后10分钟内私信触达率 >= 90%
- 漏斗指标：
  - 评论 -> 私信 >= 25%
  - 私信 -> 19-39服务单 >= 10%
  - 19-39服务单 -> 299主商品 >= 20%
