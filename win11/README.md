# PDF标注工具 v7.3 — Windows 11 构建指南

## 目录结构

```
pdf-label-tool-tauri/
├── src-tauri/            # Tauri (Rust) 主程序
│   ├── src/lib.rs        # Windows 分支: 自动查找同目录 pdf-label-backend.exe
│   └── tauri.conf.json   # 打包配置 (resources: sidecar/* + frontend/*)
├── sidecar/
│   └── server.py         # FastAPI 后端 (OCR + PDF渲染 + 文件服务)
├── frontend/
│   └── index.html        # 前端 UI (原生 HTML/JS/Canvas)
└── win11/                # ← 本目录: Windows 构建工具包
    ├── build.ps1         # 一键构建脚本
    ├── requirements.txt  # Python sidecar 依赖
    ├── pdf-label-backend.spec  # PyInstaller 打包配置
    ├── font_patch.py     # Windows 字体路径自动适配 (runtime hook)
    └── README.md         # 本文档
```

## 前置条件

在 Windows 11 上安装以下工具（构建前必须完成）：

| 工具 | 下载地址 | 说明 |
|------|---------|------|
| **Python 3.11+** | https://www.python.org/downloads/ | 安装时勾选 "Add to PATH" |
| **Rust** | https://rustup.rs | 安装后重启终端 |
| **Node.js 18+** | https://nodejs.org | LTS 版本 |
| **MSVC Build Tools** | Visual Studio Installer | 勾选 "Desktop development with C++" |
| **WebView2** | https://developer.microsoft.com/microsoft-edge/webview2/ | 通常 Win11 已预装 |

确认安装成功：
```powershell
python --version    # 3.11+
rustc --version     # 1.77+
node --version      # 18+
cargo --version
```

## 构建步骤

### 方式一：一键脚本（推荐）

```powershell
cd pdf-label-tool-tauri
powershell -ExecutionPolicy Bypass -File win11/build.ps1
```

脚本会自动完成全部 5 个步骤（详见下方）。

### 方式二：手动分步执行

#### Step 1: 安装 Python 依赖

```powershell
cd win11
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

#### Step 2: PyInstaller 打包 sidecar

```powershell
cd win11
pyinstaller pdf-label-backend.spec --noconfirm
```

产物: `win11/dist/pdf-label-backend.exe` (~400-600MB)

#### Step 3: 拷贝 sidecar exe 到 Tauri 目录

```powershell
copy dist\pdf-label-backend.exe ..\src-tauri\pdf-label-backend.exe
```

#### Step 4: Tauri 构建

```powershell
cd ..   # 回到项目根目录
cargo tauri build
```

#### Step 5: 收集产物

安装包位于：
```
src-tauri/target/release/bundle/msi/*.msi      # MSI 安装包
src-tauri/target/release/bundle/nsis/*.exe     # NSIS 安装包
```

## 产物说明

| 文件 | 大小 | 说明 |
|------|------|------|
| `PDF标注工具_7.3.0_x64-setup.exe` | ~500-700MB | NSIS 安装包（内含 sidecar） |
| `PDF标注工具_7.3.0_x64_en-US.msi` | ~500-700MB | MSI 安装包 |

安装后可直接双击运行，无需安装 Python 或任何依赖。

## 离线使用

PaddleOCR 首次运行会自动下载模型（~50MB）。如需完全离线：

1. 在有网的 Windows 机器上安装并运行一次
2. 拷贝 `C:\Users\<用户名>\.paddleocr\` 目录
3. 粘贴到离线机器的相同路径

## 工作原理

```
┌─────────────────────────────────────┐
│         PDF标注工具.exe              │  ← Tauri 主程序 (Rust)
│  ┌─────────────────────────────┐    │
│  │     WebView2 (前端 UI)       │    │  ← frontend/index.html
│  └──────────┬──────────────────┘    │
│             │ HTTP (127.0.0.1:8502) │
│  ┌──────────▼──────────────────┐    │
│  │   pdf-label-backend.exe      │    │  ← PyInstaller 打包的 Python
│  │  (FastAPI + PyMuPDF + OCR)   │    │     sidecar (所有依赖内含)
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

- Tauri 启动时自动 spawn `pdf-label-backend.exe`（同目录查找）
- 前端通过 `fetch("http://127.0.0.1:8502/api/...")` 调用后端
- 关闭主程序时，Rust 侧自动 kill 子进程

## 常见问题

**Q: PyInstaller 报 "module not found"**
A: 运行 `python -c "import paddleocr; import fitz; import fastapi"` 确认依赖都已安装。

**Q: cargo tauri build 报 WebView2 错误**
A: 安装 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。

**Q: OCR 很慢或报错**
A: PaddleOCR 首次运行需下载模型。确保首次使用时有网络连接。

**Q: 标注序号字体显示异常**
A: font_patch.py 会自动使用 Windows 系统字体（微软雅黑/宋体）。确保 `C:\Windows\Fonts\msyh.ttc` 存在。

**Q: 构建出的 exe 体积太大**
A: PaddleOCR + PaddlePaddle 占约 400MB，无法进一步压缩。如不需要 OCR 功能，可在 `requirements.txt` 中移除 paddle 相关包。
