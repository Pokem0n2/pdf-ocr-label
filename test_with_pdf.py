
import streamlit as st
import fitz

st.set_page_config(layout="wide")

# 初始化session state
if 'pdf_document' not in st.session_state:
    st.session_state.pdf_document = None
    st.session_state.pdf_path = None
    st.session_state.current_page = 0
    st.session_state.total_pages = 0
    st.session_state.annotations = {}
    st.session_state.zoom_level = 2.0

# 模拟已经上传了PDF
if st.session_state.pdf_document is None:
    # 模拟上传
    st.session_state.pdf_document = fitz.open('/home/spark/pdf-label-tool/test_gb50204_v2.pdf')
    st.session_state.pdf_path = '/home/spark/pdf-label-tool/test_gb50204_v2.pdf'
    st.session_state.total_pages = len(st.session_state.pdf_document)
    st.session_state.current_page = 0

# 侧边栏
with st.sidebar:
    st.header("文件管理")
    st.write(f"已加载: test_gb50204_v2.pdf")
    st.write(f"总页数: {st.session_state.total_pages}")

# 主内容区 - 双栏
left_col, right_col = st.columns([3, 2])

with left_col:
    st.subheader("📄 PDF阅读器")
    st.button("运行AI预标注")
    
    # 渲染PDF
    page = st.session_state.pdf_document[st.session_state.current_page]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    st.image(pix.tobytes("png"), use_container_width=True)

with right_col:
    st.subheader("📝 识别结果编辑器")
    st.info("点击左侧「运行AI预标注」按钮开始识别")
