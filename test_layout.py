
import streamlit as st

st.set_page_config(layout="wide")

# 初始化session state
if 'pdf_document' not in st.session_state:
    st.session_state.pdf_document = None

# 模拟上传后设置pdf_document
# 在实际应用中，这是由file_uploader触发的
if st.sidebar.button("模拟上传PDF"):
    import fitz
    st.session_state.pdf_document = fitz.open('/home/spark/pdf-label-tool/test_gb50204_v2.pdf')
    st.rerun()

# 主内容区
if st.session_state.pdf_document is None:
    st.info("请上传PDF")
else:
    left_col, right_col = st.columns([3, 2])
    with left_col:
        st.subheader("📄 PDF阅读器")
        st.write("PDF内容显示在这里")
    with right_col:
        st.subheader("📝 识别结果编辑器")
        st.write("标注编辑在这里")
