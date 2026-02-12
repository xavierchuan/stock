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

## 可执行文件 + 授权校验（不发源码）

### 1) 安装打包依赖

```bash
pip install -r /Users/chuan/Documents/Projects/Business/stock/requirements_build.txt
```

### 2) 生成密钥（只做一次）

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/lite_tool/generate_keys.py
cp ~/.factor_lab_keys/public_key.pem /Users/chuan/Documents/Projects/Business/stock/lite_tool/public_key.pem
```

说明：
- `private_key.pem` 只留在你本机，不要上传仓库
- `public_key.pem` 用于应用内验签（本地文件，已在 `.gitignore` 中）

### 3) 构建可执行文件

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/lite_tool/build_executable.py --clean
```

输出目录：

`/Users/chuan/Documents/Projects/Business/stock/lite_tool/dist_exec/`

### 4) 给用户签发授权文件

先拿用户机器码（或让用户运行程序看授权页面提示）：

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/lite_tool/show_machine_code.py
```

签发 `license.key`：

```bash
python3 /Users/chuan/Documents/Projects/Business/stock/lite_tool/issue_license.py \
  --private-key ~/.factor_lab_keys/private_key.pem \
  --license-id T20260212-001 \
  --days 30 \
  --machine-code <用户机器码> \
  --out /Users/chuan/Documents/Projects/Business/stock/license.key
```

把可执行文件目录 + `license.key` 一起发给用户即可。

## macOS 签名 + Notarize（Apple Developer）

你现在这个账号可以走完整流程，但需要先在 Apple Developer 里申请并安装 `Developer ID Application` 证书。

先确认本机证书：

```bash
security find-identity -v -p codesigning
```

如果结果里没有 `Developer ID Application: ...`，先去证书后台创建并导入到钥匙串，再继续。

### 1) 存储 notarytool 凭据（只做一次）

```bash
TEAM_ID=你的TeamID \
APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx \
bash /Users/chuan/Documents/Projects/Business/stock/lite_tool/setup_notary_profile.sh
```

说明：
- `APP_SPECIFIC_PASSWORD` 是 Apple ID 的 app 专用密码，不是登录密码
- 默认 profile 名是 `AC_NOTARY`，可用 `KEYCHAIN_PROFILE` 自定义

### 2) 构建 `.app` 并签名、notarize、staple

```bash
TEAM_ID=你的TeamID \
CERT_NAME='Developer ID Application: 你的名字 (TEAMID)' \
bash /Users/chuan/Documents/Projects/Business/stock/lite_tool/build_sign_notarize_app.sh
```

产物目录：

`/Users/chuan/Documents/Projects/Business/stock/lite_tool/dist_signed/`

主要文件：
- `BuffettLite.app`
- `BuffettLite.app.zip`（notarize 提交包）

### 3) 快速调试（先只打包签名，不提审）

```bash
CERT_NAME='Developer ID Application: 你的名字 (TEAMID)' \
SKIP_NOTARIZE=1 \
bash /Users/chuan/Documents/Projects/Business/stock/lite_tool/build_sign_notarize_app.sh
```

## 使用说明

1. 选择候选池来源（自选股票池/自动候选池）
2. 点击“运行 Lite 体检（消耗1次）”
3. 查看 Top 3 候选和一句话解释

## 免责声明

仅供研究与教育用途，不构成投资建议，不承诺收益。
