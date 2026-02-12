# 巴菲特战法 Lite 体验版（免费）

本工具是免费体验版，固定限制如下：

- 仅 1 个战法（巴菲特）
- 每天最多运行 3 次
- 仅展示前 3 只候选
- 仅基础体检页（不含导出、历史对比、组合回测）
- 官方售价 0 元，请勿购买 Lite 安装包

## 启动方式

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r /Users/chuan/Documents/Projects/Business/stock/requirements.txt
streamlit run /Users/chuan/Documents/Projects/Business/stock/lite_tool/app.py
```

## 双击运行（发试用用户）

### 生成试用压缩包

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/lite_tool/build_trial_bundle.py
```

生成后文件在：

`/Users/chuan/Documents/Projects/Business/stock/lite_tool/dist/`

### 双击启动文件

- Mac：`start_lite.command`
- Windows：`start_lite.bat`

## 使用说明

1. 选择候选池来源（自选股票池/自动候选池）
2. 点击“运行 Lite 体检（消耗1次）”
3. 查看 Top 3 候选和一句话解释

## 免责声明

仅供研究与教育用途，不构成投资建议，不承诺收益。
