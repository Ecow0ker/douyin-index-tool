# 抖音指数查询工具

当前版本：`v1.1.0`

Windows 和 macOS 提供系统 WebView 图形界面，Linux 提供命令行入口。软件通过使用者本人扫码登录的抖音创作者中心会话查询指数，支持多人依次登录、多账号轮换、批量查询和 CSV 导出。

## 主要功能

- 在软件登录窗口打开抖音创作者中心并扫码登录。
- 多位使用者依次扫码，保存多个本机账号。
- 支持顺序轮换或随机切换；登录失效、频率受限时切换下一账号。
- 一行一个关键词，自动去重并批量查询。
- 查询抖音综合指数、抖音搜索指数。
- 查询最长过去半年的日期范围。
- 支持日、周、月、季度、年度日均聚合。
- 自定义请求间隔，显示任务进度、倒计时和实时日志。
- 支持暂停、继续、停止任务。
- 在软件内查看结果，导出 Excel 可直接打开的 UTF-8 BOM CSV。
- 提供演示模式、界面自动测试和命令行入口。

## 下载

在 [GitHub Releases](https://github.com/Ecow0ker/douyin-index-tool/releases) 下载对应文件：

| 系统 | 处理器 | 文件 |
|---|---|---|
| Windows | 64 位 Intel/AMD | `douyin-index-tool-v1.1.0-windows-x64.exe` |
| macOS | Intel | `douyin-index-tool-v1.1.0-macos-x64.zip` |
| macOS | Apple Silicon（M 系列） | `douyin-index-tool-v1.1.0-macos-arm64.zip` |
| Windows、macOS、Linux | Python 源码 | `douyin-index-tool-v1.1.0-source.zip` |

Windows 下载 EXE 后直接运行。macOS 解压 ZIP 后运行“抖音指数查询工具.app”。macOS 首次启动若提示来源限制，可右键 APP 选择“打开”。

## 图形界面使用

1. 打开“账号中心”，点击“打开登录窗口”。
2. 使用抖音扫码，确认登录窗口已经进入“抖音指数”页面。
3. 返回软件，点击“同步当前登录账号”。
4. 添加其他使用者时，先在登录窗口退出当前账号，再让下一位扫码并同步。
5. 在“查询任务”输入关键词和日期，选择指数类型、聚合周期、请求间隔和导出目录。
6. 点击“开始查询”；完成后在结果表查看数据或打开导出目录。

## 登录数据与隐私

图形界面不显示原始 Cookie。已同步的登录会话写入当前用户的本机应用数据目录，并设置为仅当前用户可读：

- macOS：`~/Library/Application Support/CrossPlatformTools/抖音指数查询工具/`
- Windows：`%APPDATA%\CrossPlatformTools\抖音指数查询工具\`

账号文件、真实 Cookie、访问令牌和导出数据不写入项目目录。上传 GitHub 前仍建议执行 `git status --ignored` 检查待提交内容。

## 从源码运行图形界面

### macOS

```bash
python3 -m venv .webviewvenv
.webviewvenv/bin/python -m pip install -r requirements-webview.txt
PYTHONPATH=src .webviewvenv/bin/python run_webview_gui.py
```

也可双击 `macOS_启动图形界面.command`。

### Windows

```powershell
py -3.12 -m venv .webviewvenv
.\.webviewvenv\Scripts\python.exe -m pip install -r requirements-webview.txt
$env:PYTHONPATH = "src"
.\.webviewvenv\Scripts\python.exe run_webview_gui.py
```

也可双击 `Windows_启动图形界面.pyw`。

## Linux 命令行

```bash
./Linux_命令行.sh query \
  --keyword 女性 --keyword 生育 \
  --start 2026-07-01 --end 2026-08-01 \
  --cookie-file ./cookie.txt \
  --period monthly \
  --output ./抖音指数.csv
```

图形界面通过扫码同步会话；命令行通过 `--cookie-file` 读取当前使用者自行保存的本机 Cookie 文件。

## 构建发行文件

### macOS Intel

```bash
TARGET_ARCH=x64 ./build_macos.sh
```

### macOS Apple Silicon

```bash
TARGET_ARCH=arm64 ./build_macos.sh
```

### Windows x64 原生构建

在 Windows PowerShell 运行：

```powershell
.\build_windows.ps1
```

### 在 macOS/Linux 交叉生成 Windows 便携 EXE

需要 `mingw-w64`：

```bash
./build_windows_python_releases.sh
```

### 打包

打包当前 macOS 架构、源码和已生成的 Windows EXE：

```bash
./package_release.sh
```

集齐 macOS x64、macOS arm64 和 Windows x64 后生成完整发行目录：

```bash
./package_python_releases.sh
```

## GitHub Actions

- `.github/workflows/build-macos.yml`：分别在 Intel 和 Apple Silicon runner 构建、测试、验证签名与界面，然后上传 ZIP。
- `.github/workflows/build-windows.yml`：在 Windows x64 runner 运行测试、构建 EXE、执行界面自测并上传产物。
- 推送 `v*` 标签或在 Actions 页面手动触发均会执行构建。

建议发布步骤：

```bash
git add .
git commit -m "Release v1.1.0"
git tag v1.1.0
git push origin main --tags
```

Actions 完成后，将三个系统产物及 `release/douyin-index-tool-v1.1.0-source.zip`、`release/SHA256SUMS-v1.1.0.txt` 上传到 GitHub Release。

## 当前接口契约

- 页面：`https://creator.douyin.com/creator-micro/creator-count/arithmetic-index`
- 关键词趋势：`POST /api/v2/index/get_multi_keyword_hot_trend`
- 有效日期：`POST /api/v2/index/get_keyword_valid_date`
- 热门关键词：`GET /api/v2/index/get_hot_words`
- 热门话题：`GET /api/v2/index/get_hot_topics`

趋势请求包含 `keyword_list`、`start_date`、`end_date` 和 `app_name=aweme`。接口响应可能携带 `x-encrypted: 1/2`，解密兼容代码集中在 `src/douyin_index_tool/crypto.py`。平台调整接口时集中修改 `src/douyin_index_tool/api.py`。

## 测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 run_webview_gui.py --demo --ui-self-test-output ./ui-test.json
```

测试覆盖接口解析与解密、账号保存与轮换、聚合与导出、演示查询、关于弹窗、跨平台仓库结构和桌面界面。

## 联系

- QQ群：610645081
