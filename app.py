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
    return HTMLResponse(content=HTML_PAGE)

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
HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>PDF条文标注工具 v7.3</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; }
.header { background: #fff; border-bottom: 1px solid #ddd; padding: 12px 20px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.header h1 { font-size: 18px; color: #333; margin-right: auto; }
.btn { padding: 6px 14px; border: 1px solid #ddd; border-radius: 4px; background: #fff; cursor: pointer; font-size: 13px; }
.btn:hover { background: #f0f0f0; }
.btn-primary { background: #1a73e8; color: #fff; border-color: #1a73e8; }
.btn-primary:hover { background: #1557b0; }
.btn-danger { background: #dc3232; color: #fff; border-color: #dc3232; }
.page-info { font-size: 14px; color: #666; min-width: 60px; text-align: center; }
input[type="number"] { width: 50px; padding: 4px; border: 1px solid #ddd; border-radius: 4px; }
.main { display: flex; height: calc(100vh - 60px); }
.panel { background: #fff; border-right: 1px solid #ddd; overflow-y: auto; }
.panel-left { width: 15%; min-width: 180px; }
.panel-center { width: 50%; display: flex; flex-direction: column; }
.panel-right { width: 35%; min-width: 280px; border-right: none; border-left: 1px solid #ddd; }
.panel h3 { padding: 12px 16px; font-size: 14px; border-bottom: 1px solid #eee; }
#ann-list { padding: 8px; }
.ann-item { padding: 8px 12px; margin: 4px 0; border: 1px solid #e0e0e0; border-radius: 4px; cursor: grab; background: #fff; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.ann-item:hover { border-color: #1a73e8; }
.ann-item.selected { border-color: #dc3232; background: #fff5f5; }
.ann-item.multi-selected { border-color: #ff9800; background: #fff8e1; }
.ann-item.dragging { opacity: 0.5; }
.ann-item .num { width: 22px; height: 22px; border-radius: 50%; background: #1a73e8; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
.ann-item.selected .num { background: #dc3232; }
.ann-item.multi-selected .num { background: #ff9800; }
.ann-item .text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ann-item .conf { color: #888; font-size: 11px; flex-shrink: 0; }
.ann-item .skip-badge { color: #999; font-size: 11px; }
#canvas-container { flex: 1; overflow: auto; display: flex; align-items: center; justify-content: center; background: #e8e8e8; position: relative; }
#pdf-canvas { cursor: crosshair; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
#pdf-canvas.select-mode { cursor: pointer; }
#text-editor { width: 100%; height: calc(100% - 50px); border: none; padding: 16px; font-size: 14px; line-height: 1.6; resize: none; outline: none; }
#text-editor:disabled { background: #f5f5f5; color: #999; }
.status-bar { padding: 8px 16px; font-size: 12px; color: #888; border-top: 1px solid #eee; }
.help { padding: 12px 16px; font-size: 12px; color: #666; line-height: 1.8; }
.help kbd { background: #f0f0f0; border: 1px solid #ccc; border-radius: 3px; padding: 1px 5px; font-family: monospace; }
.hidden { display: none; }
</style>
</head>
<body>
<div class="header">
    <h1>📄 PDF条文标注工具 v7.3</h1>
    <span id="version-check" style="color:#dc3232; font-size:12px; margin-right:10px;">(请确认看到此红色文字)</span>
    <input type="file" id="file-input" accept=".pdf" class="hidden">
    <button class="btn" onclick="document.getElementById('file-input').click()">📁 上传PDF</button>
    <button class="btn" id="btn-prev">⬅</button>
    <span class="page-info" id="page-info">未加载</span>
    <button class="btn" id="btn-next">➡</button>
    <input type="number" id="page-jump" value="1" min="1">
    <button class="btn" id="btn-jump">Go</button>
    <button class="btn btn-primary" id="btn-ocr">🤖 识别本页</button>
    <button class="btn" id="btn-export">📤 导出清洗文本</button>
    <a id="download-link" class="hidden" download></a>
</div>
<div class="main">
    <div class="panel panel-left">
        <h3>标注块（拖拽排序）</h3>
        <div id="ann-list"></div>
        <div class="help">
            <b>快捷键：</b><br>
            <kbd>↑</kbd> <kbd>↓</kbd> 调整选中块位置<br>
            <kbd>Delete</kbd> 删除选中<br>
            <kbd>Shift</kbd>+拖拽 框选多选/新建<br>
            <kbd>Ctrl</kbd>+点击 多选切换<br>
            点击标注块选中，再次点击取消<br>
            右侧：显示全部文本，可直接编辑
        </div>
    </div>
    <div class="panel-center">
        <div id="canvas-container">
            <canvas id="pdf-canvas"></canvas>
        </div>
        <div class="status-bar" id="status">请上传PDF文件</div>
    </div>
    <div class="panel panel-right">
        <h3>识别文本</h3>
        <textarea id="text-editor" placeholder="选中标注块后在此编辑文本..." disabled></textarea>
    </div>
</div>

<script>
// ==================== 状态 ====================
let sid = null;
let page = 1, total = 1;
let anns = [];
let selIdx = -1;
let multiSel = [];  // 多选索引数组
let imgWidth = 0, imgHeight = 0;
let scale = 1;  // 显示缩放

// ==================== Canvas ====================
const canvas = document.getElementById('pdf-canvas');
const ctx = canvas.getContext('2d');
let img = new Image();
let isDragging = false, dragStart = null, isShift = false;

// ==================== 渲染 ====================
function renderList() {
    const list = document.getElementById('ann-list');
    list.innerHTML = '';
    anns.forEach((ann, idx) => {
        const div = document.createElement('div');
        let cls = 'ann-item';
        if (idx === selIdx) cls += ' selected';
        else if (multiSel.includes(idx)) cls += ' multi-selected';
        if (ann.skipped) cls += ' skipped';
        div.className = cls;
        div.draggable = true;
        div.dataset.idx = idx;
        div.innerHTML = `<span class="num">${idx+1}</span><span class="text">${escapeHtml(ann.text || '')}</span><span class="conf">${(ann.confidence*100).toFixed(0)}%</span>${ann.skipped ? '<span class="skip-badge">⏭</span>' : ''}`;
        div.onclick = (e) => {
            if (e.shiftKey) {
                toggleMultiSel(idx);
            } else {
                selectAnn(idx);
            }
        };
        div.ondragstart = (e) => { e.dataTransfer.setData('text/plain', idx); div.classList.add('dragging'); };
        div.ondragend = () => div.classList.remove('dragging');
        div.ondragover = (e) => { e.preventDefault(); };
        div.ondrop = (e) => {
            e.preventDefault();
            const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
            const toIdx = parseInt(div.dataset.idx);
            if (fromIdx !== toIdx) {
                const item = anns.splice(fromIdx, 1)[0];
                anns.splice(toIdx, 0, item);
                if (selIdx === fromIdx) selIdx = toIdx;
                else if (selIdx > fromIdx && selIdx <= toIdx) selIdx--;
                else if (selIdx < fromIdx && selIdx >= toIdx) selIdx++;
                updateServer();
            }
        };
        list.appendChild(div);
    });
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function renderCanvas() {
    if (!img.src) return;
    const container = document.getElementById('canvas-container');
    const maxW = container.clientWidth - 40;
    const maxH = container.clientHeight - 40;
    scale = Math.min(maxW / imgWidth, maxH / imgHeight, 1);
    canvas.width = imgWidth * scale;
    canvas.height = imgHeight * scale;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // 绘制标注框
    anns.forEach((ann, idx) => {
        if (ann.skipped) return;
        const [x1, y1, x2, y2] = ann.bbox;
        const isSel = idx === selIdx;
        const isMulti = multiSel.includes(idx);
        if (isSel) {
            ctx.strokeStyle = '#dc3232';
            ctx.lineWidth = 3;
        } else if (isMulti) {
            ctx.strokeStyle = '#ff9800';
            ctx.lineWidth = 2.5;
        } else {
            ctx.strokeStyle = '#1a73e8';
            ctx.lineWidth = 1.5;
        }
        ctx.strokeRect(x1 * scale, y1 * scale, (x2-x1) * scale, (y2-y1) * scale);
        if (isSel || isMulti) {
            ctx.fillStyle = isSel ? 'rgba(220, 50, 50, 0.1)' : 'rgba(255, 152, 0, 0.08)';
            ctx.fillRect(x1 * scale, y1 * scale, (x2-x1) * scale, (y2-y1) * scale);
        }
        // 编号标签
        ctx.fillStyle = isSel ? '#dc3232' : (isMulti ? '#ff9800' : '#1a73e8');
        const lbl = String(idx + 1);
        ctx.font = 'bold 13px sans-serif';
        const tm = ctx.measureText(lbl);
        const tw = tm.width + 8, th = 18;
        ctx.fillRect(x1 * scale, y1 * scale - th, tw, th);
        ctx.fillStyle = '#fff';
        ctx.fillText(lbl, x1 * scale + 4, y1 * scale - 4);
    });
}

function selectAnn(idx) {
    // 再次点击已选中的块，取消选中
    if (idx === selIdx && multiSel.length === 0) {
        selIdx = -1;
        renderList();
        renderCanvas();
        return;
    }
    selIdx = idx;
    multiSel = [];  // 单选时清空多选
    renderList();
    renderCanvas();
    // 光标定位到对应行
    focusEditorLine(idx);
}

function toggleMultiSel(idx) {
    const pos = multiSel.indexOf(idx);
    if (pos >= 0) {
        multiSel.splice(pos, 1);
    } else {
        multiSel.push(idx);
    }
    if (multiSel.length === 1) {
        selIdx = multiSel[0];
    } else {
        selIdx = -1;
    }
    renderList();
    renderCanvas();
}

// 右侧始终显示全部文本，始终可编辑
function updateRightPanel() {
    const editor = document.getElementById('text-editor');
    editor.disabled = false;
    const lines = anns
        .filter(a => !a.skipped)
        .map((a, i) => '[' + (i+1) + '] ' + (a.text || ''));
    editor.value = lines.join(`
`);
}

// 光标定位到第idx行（0-based）
function focusEditorLine(idx) {
    const editor = document.getElementById('text-editor');
    if (idx < 0 || idx >= anns.length) return;
    // 计算行前字符位置
    let pos = 0;
    for (let i = 0; i < idx; i++) {
        pos += ('[' + (i+1) + '] ' + (anns[i].text || '')).length + 1; // +1 for \n
    }
    // 定位到行首 '[' 后面
    pos += ('[' + (idx+1) + '] ').length;
    editor.setSelectionRange(pos, pos);
    editor.focus();
}

// 解析右侧全部文本，同步回标注块
function parseAndSaveAllText() {
    const editor = document.getElementById('text-editor');
    const text = editor.value;
    // 按 [N] 前缀分割，支持 N 从1开始
    const regex = /\[(\d+)\] /g;
    const matches = [];
    let m;
    while ((m = regex.exec(text)) !== null) {
        matches.push({ index: m.index, num: parseInt(m[1]) });
    }
    // 提取每个标注块的文本
    for (let i = 0; i < matches.length; i++) {
        const start = matches[i].index + ('[' + matches[i].num + '] ').length;
        const end = (i + 1 < matches.length) ? matches[i + 1].index : text.length;
        const blockText = text.substring(start, end).replace(/\\\\n$/, ''); // 去掉末尾换行
        const annIdx = matches[i].num - 1; // 编号从1开始，索引从0开始
        if (annIdx >= 0 && annIdx < anns.length) {
            anns[annIdx].text = blockText;
        }
    }
    renderList();
}

// ==================== 鼠标交互 ====================
canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;
    isShift = e.shiftKey;
    if (isShift) {
        isDragging = true;
        dragStart = {x, y};
        canvas.style.cursor = 'crosshair';
    } else {
        // 点击检测
        let clicked = -1;
        for (let i = anns.length - 1; i >= 0; i--) {
            const [x1, y1, x2, y2] = anns[i].bbox;
            if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
                clicked = i;
                break;
            }
        }
        if (clicked >= 0) {
            if (e.ctrlKey || e.metaKey) {
                toggleMultiSel(clicked);
            } else {
                selectAnn(clicked);
            }
        } else {
            // 点击空白处，取消选中
            if (selIdx !== -1 || multiSel.length > 0) {
                selIdx = -1;
                multiSel = [];
                renderList();
                renderCanvas();
            }
        }
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (!isDragging || !isShift) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;
    renderCanvas();
    // 绘制拖拽框
    ctx.strokeStyle = '#28a745';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(dragStart.x * scale, dragStart.y * scale, (x - dragStart.x) * scale, (y - dragStart.y) * scale);
    ctx.setLineDash([]);
});

canvas.addEventListener('mouseup', async (e) => {
    if (!isDragging || !isShift) {
        isDragging = false;
        return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;
    const x1 = Math.min(dragStart.x, x), x2 = Math.max(dragStart.x, x);
    const y1 = Math.min(dragStart.y, y), y2 = Math.max(dragStart.y, y);
    
    // 检查是否框选了已有标注块
    const boxSelected = [];
    for (let i = 0; i < anns.length; i++) {
        const [ax1, ay1, ax2, ay2] = anns[i].bbox;
        // 计算框与标注块的重叠面积
        const ix1 = Math.max(x1, ax1), iy1 = Math.max(y1, ay1);
        const ix2 = Math.min(x2, ax2), iy2 = Math.min(y2, ay2);
        if (ix2 > ix1 && iy2 > iy1) {
            boxSelected.push(i);
        }
    }
    
    if (boxSelected.length > 0) {
        // 框选了已有标注块，进行多选
        multiSel = boxSelected;
        selIdx = -1;
        renderList();
        renderCanvas();
        updateServer();
    } else if (x2 - x1 > 10 && y2 - y1 > 10) {
        // 新建标注块，并立刻OCR识别
        document.getElementById('status').textContent = '正在识别新建区域...';
        const bbox = [x1, y1, x2, y2];
        const r = await postForm('/api/ocr_region', { sid, page, bbox: JSON.stringify(bbox) });
        const newAnn = { 
            id: generateId(), 
            bbox: bbox, 
            text: r.text || '', 
            confidence: 1.0, 
            skipped: false 
        };
        anns.push(newAnn);
        selectAnn(anns.length - 1);
        updateRightPanel();
        updateServer();
        document.getElementById('status').textContent = '新建并识别完成';
    }
    
    isDragging = false;
    dragStart = null;
    canvas.style.cursor = 'pointer';
});

function generateId() {
    return Math.random().toString(36).substr(2, 8);
}

// ==================== 键盘事件 ====================
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
    if (e.key === 'Delete' || e.key === 'Backspace') {
        if (multiSel.length > 0) {
            // 删除多选
            const sorted = [...multiSel].sort((a, b) => b - a);
            for (let idx of sorted) {
                anns.splice(idx, 1);
            }
            multiSel = [];
            selIdx = -1;
            updateServer();
            updateRightPanel();
        } else if (selIdx >= 0 && selIdx < anns.length) {
            anns.splice(selIdx, 1);
            selIdx = -1;
            updateServer();
            updateRightPanel();
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (selIdx > 0) {
            // 交换选中块与上一个块的位置
            [anns[selIdx], anns[selIdx - 1]] = [anns[selIdx - 1], anns[selIdx]];
            selIdx--;
            updateServer();
            updateRightPanel();
        }
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (selIdx >= 0 && selIdx < anns.length - 1) {
            // 交换选中块与下一个块的位置
            [anns[selIdx], anns[selIdx + 1]] = [anns[selIdx + 1], anns[selIdx]];
            selIdx++;
            updateServer();
            updateRightPanel();
        }
    }
});

// ==================== 文本编辑自动保存 ====================
let saveTimeout = null;
document.getElementById('text-editor').addEventListener('input', (e) => {
    // 解析全部文本，同步回标注块
    parseAndSaveAllText();
    // 防抖自动保存到服务器
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
        updateServer();
    }, 500);
});

// ==================== API ====================
async function postForm(url, data) {
    const form = new FormData();
    for (const k in data) form.append(k, data[k]);
    const r = await fetch(url, { method: 'POST', body: form });
    return r.json();
}

async function updateServer() {
    if (!sid) return;
    const r = await postForm('/api/update', { sid, anns: JSON.stringify(anns), sel: selIdx });
    if (r.img) { img.src = 'data:image/png;base64,' + r.img; img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); }; }
}

// 上传
document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    const r = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await r.json();
    sid = data.sid; page = data.page; total = data.total; anns = data.anns; selIdx = -1; multiSel = [];
    document.getElementById('page-info').textContent = page + ' / ' + total;
    document.getElementById('page-jump').value = page;
    document.getElementById('page-jump').max = total;
    if (data.img) { img.src = 'data:image/png;base64,' + data.img; img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); renderList(); updateRightPanel(); }; }
    document.getElementById('status').textContent = '已加载: ' + data.name;
    // 重置file-input，允许再次选择相同文件
    e.target.value = '';
});

// 翻页
document.getElementById('btn-prev').addEventListener('click', async () => {
    if (page <= 1) return;
    const r = await postForm('/api/page', { sid, page: page - 1 });
    page = r.page; anns = r.anns; selIdx = -1; multiSel = [];
    document.getElementById('page-info').textContent = page + ' / ' + total;
    document.getElementById('page-jump').value = page;
    if (r.img) { img.src = 'data:image/png;base64,' + r.img; img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); renderList(); updateRightPanel(); }; }
});

document.getElementById('btn-next').addEventListener('click', async () => {
    if (page >= total) return;
    const r = await postForm('/api/page', { sid, page: page + 1 });
    page = r.page; anns = r.anns; selIdx = -1; multiSel = [];
    document.getElementById('page-info').textContent = page + ' / ' + total;
    document.getElementById('page-jump').value = page;
    if (r.img) { img.src = 'data:image/png;base64,' + r.img; img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); renderList(); updateRightPanel(); }; }
});

document.getElementById('btn-jump').addEventListener('click', async () => {
    const p = parseInt(document.getElementById('page-jump').value);
    if (!p || p < 1 || p > total) return;
    const r = await postForm('/api/page', { sid, page: p });
    page = r.page; anns = r.anns; selIdx = -1; multiSel = [];
    document.getElementById('page-info').textContent = page + ' / ' + total;
    document.getElementById('page-jump').value = page;
    if (r.img) { img.src = 'data:image/png;base64,' + r.img; img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); renderList(); updateRightPanel(); }; }
});

// OCR
document.getElementById('btn-ocr').addEventListener('click', async () => {
    if (!sid) return;
    document.getElementById('status').textContent = '正在识别...';
    const r = await postForm('/api/ocr', { sid, page });
    anns = r.anns; selIdx = -1; multiSel = [];
    if (r.img) { img.src = 'data:image/png;base64,' + r.img; img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); renderList(); updateRightPanel(); }; }
    document.getElementById('status').textContent = '识别完成，共 ' + anns.length + ' 个标注块';
});

// 导出
document.getElementById('btn-export').addEventListener('click', async () => {
    if (!sid) return;
    document.getElementById('status').textContent = '正在导出...';
    const r = await postForm('/api/export', { sid });
    document.getElementById('status').textContent = '导出完成';
    // 下载
    const a = document.getElementById('download-link');
    a.href = '/api/download?path=' + encodeURIComponent(r.path);
    a.download = r.path.split('/').pop();
    a.click();
});

// 窗口resize
window.addEventListener('resize', () => { renderCanvas(); });

// 初始化
img.onload = () => { imgWidth = img.naturalWidth; imgHeight = img.naturalHeight; renderCanvas(); };
</script>
</body>
</html>
'''

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8502)
