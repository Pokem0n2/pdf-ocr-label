
import streamlit as st
import fitz
import os

st.set_page_config(
    page_title="PDF标注工具",
    layout="wide",
)

# 初始化并直接加载PDF
if 'pdf_doc' not in st.session_state:
    st.session_state.pdf_doc = None

# 模拟已上传PDF
if st.session_state.pdf_doc is None:
    pdf_path = '/home/spark/pdf-label-tool/test_gb50204_v2.pdf'
    if os.path.exists(pdf_path):
        st.session_state.pdf_doc = fitz.open(pdf_path)
        st.session_state.pdf_name = os.path.basename(pdf_path)

# 侧边栏
with st.sidebar:
    st.header("文件")
    if st.session_state.pdf_doc:
        st.write(f"已加载: {st.session_state.pdf_name}")
        st.write(f"页数: {len(st.session_state.pdf_doc)}")
    else:
        st.error("PDF未加载")

# 主区域 - 双栏
if st.session_state.pdf_doc is None:
    st.error("无法显示PDF")
else:
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.header("📄 PDF阅读器")
        st.write("这是左栏 - PDF显示区域")
        
        # 显示PDF第一页
        page = st.session_state.pdf_doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        st.image(pix.tobytes("png"), width=600)
        
    with col2:
        st.header("📝 识别结果编辑器")
        st.write("这是右栏 - 标注编辑区域")
        st.text_area("识别文本", value="测试文本内容", height=200)
        st.button("保存标注")
