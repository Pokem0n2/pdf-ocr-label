
import streamlit as st
import fitz
import os

st.set_page_config(layout="wide")

# 初始化session state
if 'pdf_document' not in st.session_state:
    st.session_state.pdf_document = None
    st.session_state.pdf_path = None
    st.session_state.current_page = 0
    st.session_state.total_pages = 0
    st.session_state.annotations = {}
    st.session_state.zoom_level = 2.0

# 模拟已经上传了PDF（直接设置，不通过file_uploader）
if st.session_state.pdf_document is None:
    pdf_path = '/home/spark/pdf-label-tool/test_gb50204_v2.pdf'
    if os.path.exists(pdf_path):
        st.session_state.pdf_document = fitz.open(pdf_path)
        st.session_state.pdf_path = pdf_path
        st.session_state.total_pages = len(st.session_state.pdf_document)
        st.session_state.current_page = 0

# 侧边栏
with st.sidebar:
    st.header("📁 文件管理")
    
    if st.session_state.pdf_document is not None:
        st.write(f"已加载: {os.path.basename(st.session_state.pdf_path)}")
        st.write(f"总页数: {st.session_state.total_pages}")
        
        st.divider()
        st.header("🧭 页面导航")
        st.write(f"第 {st.session_state.current_page + 1} / {st.session_state.total_pages} 页")
    else:
        st.info("请上传PDF")

# 主内容区
if st.session_state.pdf_document is None:
    st.info("👈 请从左侧上传PDF文件开始标注")
else:
    # 双栏布局
    left_col, right_col = st.columns([3, 2])
    
    with left_col:
        st.subheader("📄 PDF阅读器")
        st.button("🤖 运行AI预标注")
        st.write("PDF页面显示在这里")
        
    with right_col:
        st.subheader("📝 识别结果编辑器")
        st.info("点击左侧「运行AI预标注」按钮开始识别")
