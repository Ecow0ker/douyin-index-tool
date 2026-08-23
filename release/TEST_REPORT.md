# v1.1.0 测试报告

测试日期：2026-08-23

- Python 单元测试：11/11 通过；源码 ZIP 解压后再次运行：11/11 通过。
- 当前源码和 macOS x64 发行 APP 的界面自测：22/22 通过，最小用户可见字号为 12px。
- 默认关键词为“华为”；重置按钮恢复“华为”，对应源码与发行 APP 检查通过。
- “关于”按钮、弹窗打开/关闭、版本、QQ群、GitHub 入口和图标检查全部通过。
- macOS x64 与 arm64 APP 的 Info.plist、v1.1.0 版本、代码签名结构和架构检查通过。
- Apple Silicon APP 由 universal2 Python/cffi 交叉构建；原生界面启动复测由 GitHub Actions 的 arm64 runner 执行。
- Windows 文件确认为 PE32+ x86-64 GUI 可执行文件，包含应用图标和内嵌 Python/WebView/cryptography 运行资源；Windows 原生启动复测由 GitHub Actions 执行。
- GitHub Actions 的 macOS Intel、macOS arm64、Windows x64 工作流 YAML 解析通过。
- 抖音公开加密响应烟雾测试通过：AES 响应解密成功并返回 20 个热词。
- 源码 ZIP 不包含虚拟环境、构建目录、账号文件、Cookie 文件、egg-info 或 Python 缓存。
- 四个发行文件的 SHA-256 校验全部通过，校验表使用 LF 换行。
