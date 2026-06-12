# PDF条文标注工具 v1.0

基于 Streamlit + PaddleOCR 的半自动标注工具，用于工程规范PDF的AI预标注 + 人工修正。

## 功能特性

- **AI预标注**：自动识别PDF中的文本、表格、公式区域
- **人工修正**：支持修改识别结果、调整区域边界
- **多类型支持**：文本条文、表格、公式、图片
- **数据集导出**：支持Alpaca格式的JSONL和CSV导出

## 安装

```bash
# 创建虚拟环境
python3 -m venv ~/pdf-label-env
source ~/pdf-label-env/bin/activate

# 安装依赖
pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install paddleocr pymupdf streamlit
pip install streamlit-drawable-canvas pandas pillow numpy
```

## 启动

```bash
cd ~/pdf-label-tool
./run.sh
```

或手动：
```bash
source ~/pdf-label-env/bin/activate
streamlit run app.py
```

## 使用说明

### 操作流程
1. 上传PDF文件
2. 点击「运行AI预标注」自动识别
3. 在右侧编辑器中修正识别结果
4. 逐页完成标注
5. 导出数据集

### 标注规范
- 📝 **文本条文**：规范正文、条款说明
- 📊 **表格**：数据表格、参数表
- 🔢 **公式**：数学公式、计算公式
- 🖼️ **图片/图示**：示意图、流程图
- ⏭️ **跳过**：目录、页眉页脚、广告页

### 快捷键
- 页面导航：上一页/下一页按钮
- 批量操作：跳过低置信度、全部标记为文本

## 访问地址

启动后访问：
- 本地：http://localhost:8501
- 局域网：http://<IP地址>:8501

## 技术栈

- **OCR引擎**：PaddleOCR 3.0 (PP-OCRv6)
- **PDF渲染**：PyMuPDF
- **Web界面**：Streamlit
- **数据存储**：SQLite/JSONL

## 数据集格式

### Alpaca JSONL
```json
{
  "instruction": "请解释以下工程规范条文：\n...",
  "input": "",
  "output": "...",
  "source": "PDF第1页",
  "type": "text",
  "confidence": 0.95,
  "bbox": [x1, y1, x2, y2]
}
```

## 注意事项

- 首次使用需要下载OCR模型（约100MB）
- 支持GPU加速（CUDA）
- 建议Chrome浏览器访问
