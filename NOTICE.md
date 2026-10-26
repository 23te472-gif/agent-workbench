# 项目许可与第三方声明

## 项目自身代码

本项目作者有权授权的自有源码及文档采用 MIT License，完整条款见根目录 [LICENSE](LICENSE)。版权署名为 `Copyright (c) 2026 23te472-gif and contributors`，使用公开 GitHub 署名，不写入真实姓名或本机路径。

MIT 允许使用、修改、再分发、商用和闭源改编；分发软件副本或其主要部分时须保留版权和许可声明。软件按原样提供，具体权利和责任以 LICENSE 原文为准。

第三方代码、依赖与其原有版权声明仍适用各自许可；根目录 MIT 不替换、删除或扩张第三方授权。不以本项目名义对第三方权利重新授予许可。

## 前端第三方代码

构建产物包含以下依赖的代码；许可原文保存在 `licenses/`，并保留构建产物中的许可注释。

| 组件 | 许可 | 上游 |
|---|---|---|
| React / React DOM / Scheduler | MIT | https://github.com/facebook/react |
| lucide-react | ISC；其中源自 Feather 的图标另保留 MIT 声明 | https://github.com/lucide-icons/lucide |
| esbuild（构建工具） | MIT；包内不附带其可执行文件 | https://github.com/evanw/esbuild |

`licenses/lucide-react-LICENSE` 同时保留 Lucide 与 Feather/Cole Bemis 的相应声明。使用本项目 MIT 代码时，仍需随附所分发第三方代码的许可和版权信息。

## 外部安装的 Python 依赖

依赖由使用者通过 pip 安装，本源码包不捆绑其实现、运行环境或二进制。

| 依赖 | 许可说明 | 上游 |
|---|---|---|
| pywebview | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| pythonnet | MIT | https://github.com/pythonnet/pythonnet |
| Pillow | 依安装版本附带的 PIL/Pillow 许可；上游现使用 MIT-CMU 标识，旧版本曾标为 HPND；相关库另有声明 | https://github.com/python-pillow/Pillow/blob/main/LICENSE |

保留了本机已有 pywebview/pythonnet 的许可原文。其他传递依赖按所安装版本的许可使用；重新分发安装后的依赖或可执行程序时，应一并核对并保留其完整声明。

## 素材、数据与外部服务

源码包不附带作者的角色图片、宝可梦图标合集、游戏图像、模型权重、聊天、密钥、游戏库或其他个人资料。项目 MIT 不授予第三方角色、图片、商标或使用者自行添加素材的权利。Steam、宝可梦及模型/平台名称的兼容性引用不表示品牌授权或背书。

模型 API、Codex 客户端和其他外部服务仍受其服务条款约束；本项目 MIT 不提供服务额度、账号或密钥，也不替服务商授权模型输出。公开上传的源码与后续运行产生的私人数据应继续分离。

## 适用记录

2026-10-26：项目维护者明确选择 MIT 用于这份独立源码导出。此次只更新本地发布包，没有上传 GitHub，也没有修改现用安装或桌宠包。

许可参考：[MIT 标准文本](https://choosealicense.com/licenses/mit/)、[GitHub 仓库许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)。此记录不是第三方认证或权利登记证明。
