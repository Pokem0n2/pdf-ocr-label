# PDF条文标注工具 v7.3

基于 FastAPI + PaddleOCR 的半自动标注工具，用于工程规范PDF的OCR识别 + 人工校验 → 导出清洗纯文本。

## 功能特性

- **OCR识别**：本地PaddleOCR PP-OCRv6模型，无需API Key
- **人工校验**：逐页手动校验，右侧显示全部文本，可直接编辑
- **纯文本导出**：导出清洗后的纯文本文件（.txt）
- **三栏布局**：左栏标注列表、中栏PDF画布、右栏文本编辑
- **交互操作**：拖拽排序、Shift框选多选/新建、Ctrl+点击多选

## Linux 安装与启动

```bash
# 创建虚拟环境
python3 -m venv ~/pdf-label-env
source ~/pdf-label-env/bin/activate

# 安装依赖
pip install fastapi uvicorn python-multipart pymupdf pillow numpy
pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install paddlex
```

```bash
# 启动
cd ~/pdf-label-tool
source ~/pdf-label-env/bin/activate
python app.py
```

## Windows 11 安装与启动

### 方式一：Python 原版（需安装 Python 环境）

```powershell
# 创建虚拟环境
python -m venv pdf-label-env
pdf-label-env\Scripts\activate

# 安装依赖
pip install fastapi uvicorn python-multipart pymupdf pillow numpy
pip install paddlepaddle
pip install paddleocr paddlex

# 启动
python app.py
```

### 方式二：Tauri 桌面版（免安装 Python，推荐）

无需配置 Python 环境，构建后得到独立 .exe 安装包，双击即可运行。

**前置条件**：Python 3.11+、Rust、Node.js 18+、MSVC Build Tools

```powershell
# 一键构建（自动完成 Python依赖→PyInstaller打包→Tauri编译）
cd pdf-ocr-label
powershell -ExecutionPolicy Bypass -File win11\build.ps1
```

构建产物位于 `win11\output\`，包含 `.exe` 和 `.msi` 安装包（约500-700MB，内含全部依赖）。

安装后双击桌面图标即可使用，完全离线运行（首次使用 OCR 需联网下载模型约50MB）。

> 详细构建说明见 [win11/README.md](win11/README.md)

## 使用说明

### 操作流程
1. 上传PDF文件
2. 点击「识别本页」自动OCR识别
3. 在右侧面板查看全部文本，直接编辑修改
4. 逐页完成标注校验
5. 导出清洗纯文本

### 快捷键
- `↑` `↓`：调整选中标注块位置（交换顺序）
- `Delete`：删除选中标注块（支持多选删除）
- `Shift`+拖拽：框选多选已有标注块，或框选空白区域新建标注块
- `Ctrl`+点击：多选切换
- 点击标注块选中，再次点击取消选中

### 右侧文本编辑
- 右侧始终显示当前页全部文本，格式：`[1] 文本内容`
- 直接编辑文本，修改自动保存到对应标注块
- 点击左侧标注块，光标自动定位到对应行

## 访问地址

启动后访问：
- 本地：http://localhost:8502
- 局域网：http://<IP地址>:8502

## 技术栈

- **OCR引擎**：PaddleOCR PP-OCRv6（本地模型）
- **PDF渲染**：PyMuPDF
- **Web框架**：FastAPI + 原生HTML/JS
- **导出格式**：纯文本（.txt）

## 注意事项

- 首次使用需要下载OCR模型（约100MB）
- 支持GPU加速（CUDA）
- 建议Chrome浏览器访问
- 三栏宽度比例：15% : 50% : 35%
