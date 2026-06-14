# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 将 sidecar/server.py 打包为 pdf-label-backend.exe
生成的 exe 包含所有 Python 依赖（FastAPI/PyMuPDF/PaddleOCR/numpy/Pillow）

用法:
    pyinstaller pdf-label-backend.spec --noconfirm

产物: dist/pdf-label-backend.exe (~400-600MB, 内含 PaddleOCR 模型)

注意: PaddleOCR 首次运行时会自动下载模型到 ~/.paddleocr/
      打包后离线使用需提前在有网环境运行一次让其下载模型,
      或手动将模型目录拷贝到目标机器。
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# === 收集隐式依赖 ===
datas = []
binaries = []
hiddenimports = []

# PaddleOCR / PaddlePaddle — 大量动态导入和数据文件
for pkg in ['paddleocr', 'paddle', 'paddlex']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# FastAPI / Uvicorn
for pkg in ['fastapi', 'uvicorn', 'starlette']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# PIL 字体支持
hiddenimports += ['PIL._tkinter_finder']

# multipart (FastAPI UploadFile)
hiddenimports += ['multipart']

a = Analysis(
    ['../sidecar/server.py'],
    pathex=['../sidecar'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['font_patch.py'],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython', 'jupyter'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pdf-label-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台窗口 — 方便调试; 发布时可改 False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
