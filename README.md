# Agent 工作台

Windows 桌面应用：双模型协作、实验群聊、可控自主对话、每席表达风格、显式长期记忆管理和风格/记忆导出。

## 启动

1. 安装 Python 3.11 或 3.12（含 Python Launcher、Tk）及 Microsoft Edge WebView2 Runtime。
2. 运行 `setup.cmd` 创建本包的 `.venv` 并安装固定版本 pywebview/pythonnet 等依赖。
3. 运行 `check.cmd` 检查依赖、源码语法与前端文件；成功后运行 `start.cmd`。

也可使用自备 Python：`python -m pip install -r requirements.txt`，再运行 `python -B app.py`。`python -B app.py --check` 为只读检查，不打开窗口、模型或本机资料。

## 配置模型

首次启动没有模型配置、密钥、聊天或记忆。在界面的模型设置添加自己的模型。API 密钥由当前 Windows 用户的 DPAPI 加密存入本地，不能直接把密钥文件复制给另一账号。真实请求按所选服务商计费；本机 Codex 通道调用已安装并登录的 Codex 客户端，不代表离线模型或免费调用。

本机通道通过 PATH 或标准安装位置发现原生 Codex 程序，也可手动选择路径。未安装 Codex 时可使用自行配置的兼容 API。自动发现和连接测试由用户主动触发，正常打开页面不会自动请求模型。接口地址要求 HTTPS。

协作轮数、请求次数、超时和上下文上限都由后端校验；自主对话达到上限会停止。记忆仅显式保存；可查看、修改、删除与清空。性格示例是新写的“明快助手”和“沉稳助手”，不是作者的私人设定；兼容 ID 仍为 `lele/jingshui`。

## 源码与本地资料

`frontend/src` 是前端，`frontend/dist` 是可直接运行的构建文件。Python 根目录为桥接、模型通道、协作/聊天、存储实现。

运行后会在本包 `data/` 生成模型配置、加密密钥、聊天、记忆、会话、窗口握手记录和 WebView 缓存。该目录已整体忽略，不应提交或公开。聊天导出同样可能含私人内容；请保存到仓库之外。仓库内修改 `persona_catalog.json` 是修改公开示例，私人设定请在界面编辑并保存到本地会话。

未收录作者的聊天、记忆、密钥、自定义人格原文、词库、路径、协议房间或浏览器记录；不再附带已停用的文件房间界面与命令。无需工具中心、DeepSeek Harness 或 Codex 插件目录即可启动。

## 开发

修改前端需要带 npm 的 Node.js 22.8+：运行 `build-frontend.cmd`，或在 `frontend` 中依次执行 `npm ci`、`npm test`、`npm run build`。正常运行不需要 Node。

后端测试：`python -B -m unittest discover -s tests -p "test_*.py"`。测试使用假模型，不发送真实 API 请求。完整 Windows/WebView2 窗口验收应在目标主机完成。

## 可选与工具中心联动

两个仓库独立。将本包目录名保持为 `agent-workbench`，与 `personal-tool-center` 放在同一父目录即可由中心发现；其他位置可设置 `AGENT_WORKBENCH_ENTRY` 为本包 `app.py` 的绝对路径。中心使用自己的 Python 启动它，因此中心也必须安装其 requirements。没有安装本包时，中心的对应入口会显示不可用。

## 许可

本项目自有源码及文档采用 **MIT License**，见 [LICENSE](LICENSE)。允许商用、修改和闭源改编，分发副本或主要代码时须保留版权与许可声明；无担保及责任范围以英文许可原文为准。

第三方代码、依赖、图片/角色、商标与模型服务仍按各自条款使用，范围和声明见 [NOTICE.md](NOTICE.md) 及 `licenses/`。本包不包含作者的个人运行资料或角色素材。
