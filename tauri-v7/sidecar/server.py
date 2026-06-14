"""
PDF条文标注工具 v7.0 — FastAPI + 原生HTML/JS
后端：FastAPI (OCR + 文件服务)
前端：原生Canvas (PDF渲染、标注框交互、拖拽排序、键盘事件)

交互设计：
1. 左栏：SortableJS 拖拽排序标注块列表
2. 中栏：Canvas 渲染PDF，点击选中标注块，Delete键删除，Shift+框选新建
3. 右栏：选中块文本编辑
"""
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os, io, uuid, tempfile, json, base64
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI()

# ==================== 常量 ====================
OCR_ZOOM = 2
BOX_COLOR = "#1a73e8"
SEL_COLOR = "#dc3232"

# ==================== 全局状态 ====================
# 每个session独立状态
sessions = {}

def get_session(sid):
    if sid not in sessions:
        sessions[sid] = dict(doc=None, path=None, name=None, page=0, total=0,
                             anns={}, ocrd=set(), sel=None)
    return sessions[sid]

# ==================== OCR ====================
_ocr = None
def get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(lang='ch', use_doc_orientation_classify=False,
                         use_textline_orientation=False, use_doc_unwarping=False)
    return _ocr

def do_ocr(page_num, doc):
    ocr = get_ocr()
    page = doc[page_num]
    mat = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if img.shape[2] == 4:
        img = img[:, :, :3]
    result = ocr.ocr(img)
    item = result[0]
    anns = []
    for i in range(len(item.get('rec_texts', []))):
        poly = np.array(item['rec_polys'][i])
        x1, y1 = poly.min(axis=0)
        x2, y2 = poly.max(axis=0)
        text = item['rec_texts'][i]
        score = float(item['rec_scores'][i]) if i < len(item.get('rec_scores', [])) else 0.0
        anns.append({
            'id': uuid.uuid4().hex[:8],
            'bbox': [float(x1), float(y1), float(x2), float(y2)],
            'text': text, 'confidence': score, 'skipped': False,
        })
    return anns

def do_ocr_region(page_num, doc, bbox):
    """对指定区域进行OCR识别"""
    ocr = get_ocr()
    page = doc[page_num]
    mat = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if img.shape[2] == 4:
        img = img[:, :, :3]
    # 裁剪区域
    x1, y1, x2, y2 = [int(v) for v in bbox]
    h, w = img.shape[:2]
    x1 = max(0, min(x1, w))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h))
    y2 = max(0, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return ""
    crop = img[y1:y2, x1:x2]
    result = ocr.ocr(crop)
    item = result[0]
    texts = []
    for i in range(len(item.get('rec_texts', []))):
        texts.append(item['rec_texts'][i])
    return " ".join(texts)

# ==================== 渲染 ====================
def render_page(page_num, doc, anns=None, sel_idx=None):
    if doc is None:
        return None
    page = doc[page_num]
    mat = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")

    if not anns:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = None
    for fp in ["/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
               "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 16)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    for idx, ann in enumerate(anns):
        if ann.get('skipped'):
            continue
        bx1, by1, bx2, by2 = ann['bbox']
        is_sel = idx == sel_idx
        color = SEL_COLOR if is_sel else BOX_COLOR
        width = 4 if is_sel else 2
        # 解析颜色
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        draw.rectangle([bx1, by1, bx2, by2], outline=(r, g, b, 220), width=width)
        if is_sel:
            draw.rectangle([bx1, by1, bx2, by2], fill=(r, g, b, 45))
        lbl = str(idx + 1)
        bb = draw.textbbox((0, 0), lbl, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        lx, ly = bx1, by1 - th - 6
        if ly < 0:
            ly = by1
        draw.rectangle([lx, ly, lx + tw + 10, ly + th + 5], fill=(r, g, b, 240))
        draw.text((lx + 5, ly + 2), lbl, fill=(255, 255, 255, 255), font=font)

    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ==================== API Routes ====================

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Loading</h1>")

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    sid = uuid.uuid4().hex[:16]
    S = get_session(sid)
    tmp_path = os.path.join(tempfile.gettempdir(), f"pdf_{sid}.pdf")
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
    S['doc'] = fitz.open(tmp_path)
    S['path'] = tmp_path
    S['name'] = file.filename
    S['page'] = 0
    S['total'] = len(S['doc'])
    S['anns'] = {}
    S['ocrd'] = set()
    S['sel'] = None
    img_b64 = render_page(0, S['doc'])
    return {"sid": sid, "page": 1, "total": S['total'], "img": img_b64, "anns": []}

@app.post("/api/ocr")
async def api_ocr(sid: str = Form(...), page: int = Form(...)):
    S = get_session(sid)
    p = page - 1
    S['anns'][p] = do_ocr(p, S['doc'])
    S['ocrd'].add(p)
    S['sel'] = None
    img_b64 = render_page(p, S['doc'], S['anns'][p], None)
    return {"img": img_b64, "anns": S['anns'][p]}

@app.post("/api/ocr_region")
async def api_ocr_region(sid: str = Form(...), page: int = Form(...), bbox: str = Form(...)):
    S = get_session(sid)
    p = page - 1
    bbox_list = json.loads(bbox)
    text = do_ocr_region(p, S['doc'], bbox_list)
    return {"text": text}

@app.post("/api/page")
async def api_page(sid: str = Form(...), page: int = Form(...)):
    S = get_session(sid)
    p = max(0, min(page - 1, S['total'] - 1))
    S['page'] = p
    S['sel'] = None
    anns = S['anns'].get(p, [])
    img_b64 = render_page(p, S['doc'], anns, None)
    return {"page": p + 1, "img": img_b64, "anns": anns}

@app.post("/api/update")
async def api_update(sid: str = Form(...), anns: str = Form(...), sel: int = Form(None)):
    S = get_session(sid)
    S['anns'][S['page']] = json.loads(anns)
    S['sel'] = sel
    anns = S['anns'][S['page']]
    img_b64 = render_page(S['page'], S['doc'], anns, sel)
    return {"img": img_b64, "anns": anns}

@app.post("/api/export")
async def api_export(sid: str = Form(...)):
    S = get_session(sid)
    lines = [f"# {S['name']}", f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for p in sorted(S['anns'].keys()):
        anns = [a for a in S['anns'][p] if not a.get('skipped') and a['text'].strip()]
        if not anns:
            continue
        lines.append(f"========== 第 {p+1} 页 ==========\n")
        for a in anns:
            lines.append(a['text'].strip())
        lines.append("")
    text = "\n".join(lines)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    base = os.path.splitext(S.get('name', 'output'))[0]
    path = os.path.join(tempfile.gettempdir(), f"{base}_cleaned_{ts}.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return {"path": path, "text": text}

@app.get("/api/download")
async def download(path: str):
    return FileResponse(path, filename=os.path.basename(path))

# ==================== HTML Frontend ====================

if __name__ == "__main__":
    _h = os.environ.get("PDF_LABEL_HOST", "127.0.0.1")
    _p = int(os.environ.get("PDF_LABEL_PORT", "8502"))
    print(f"Starting on {_h}:{_p}")
    uvicorn.run(app, host=_h, port=_p)
