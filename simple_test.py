
import streamlit as st
import fitz
import os

st.set_page_config(
    page_title="PDF标注工具",
    layout="wide",
)

# 初始化
if 'pdf_doc' not in st.session_state:
    st.session_state.pdf_doc = None

# 侧边栏
with st.sidebar:
    st.header("文件")
    uploaded = st.file_uploader("上传PDF", type=['pdf'])
    
    if uploaded is not None:
        # 保存并打开
        tmp_path = f"/tmp/{uploaded.name}"
        with open(tmp_path, 'wb') as f:
            f.write(uploaded.getvalue())
        st.session_state.pdf_doc = fitz.open(tmp_path)
        st.success(f"已加载: {uploaded.name}")
    
    if st.session_state.pdf_doc:
        st.write(f"页数: {len(st.session_state.pdf_doc)}")

# 主区域
if st.session_state.pdf_doc is None:
    st.info("请上传PDF")
else:
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.header("📄 PDF阅读器")
        page = st.session_state.pdf_doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        st.image(pix.tobytes("png"), width=600)
        
    with col2:
        st.header("📝 编辑器")
        st.text_area("内容", value="测试", height=200)
