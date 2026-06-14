# ==============================================================
# Windows 字体路径适配 patch
# ==============================================================
# 问题: sidecar/server.py 的 render_page() 函数中字体路径硬编码为 Linux:
#   /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc
#   /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
#   /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
#
# Windows 上这些路径不存在, 导致标注序号字体 fallback 到 default (很小)
#
# 解决: 在构建前手动修改 sidecar/server.py 的字体查找逻辑
#       或使用 PyInstaller 的 runtime hook 自动 patch
#
# 这个 hook 在 PyInstaller 打包的 exe 启动时自动执行
# ==============================================================

"""
PyInstaller runtime hook — Windows 字体自动适配
在 server.py 导入前执行, 确保 PIL 能找到合适的中文字体
"""

import os
import sys

if sys.platform == "win32":
    # Windows 字体候选路径 (按优先级)
    _win_fonts = [
        # 系统中文字体
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),    # 微软雅黑
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyhbd.ttc"),   # 微软雅黑粗
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simsun.ttc"),   # 宋体
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),   # 黑体
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "Deng.ttf"),     # 等线
        # 英文字体 (fallback)
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
    ]

    # 同时修改 PIL 的默认字体搜索路径
    # 这样即使 server.py 中的 Linux 路径全部 miss, fallback 也能用 Windows 字体
    os.environ.setdefault("PIL_FONT_DIRECTORY",
                          os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
