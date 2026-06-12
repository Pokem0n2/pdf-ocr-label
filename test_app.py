
import streamlit as st

st.set_page_config(
    page_title="PDF标注工具测试",
    layout="wide",
)

st.title("📄 PDF条文标注工具")

# 侧边栏
with st.sidebar:
    st.header("文件管理")
    uploaded_file = st.file_uploader("上传PDF", type=['pdf'])
    
    if uploaded_file:
        st.success(f"已上传: {uploaded_file.name}")
        st.session_state.has_pdf = True
    else:
        st.session_state.has_pdf = False

# 主内容区
if not st.session_state.get('has_pdf', False):
    st.info("👈 请从左侧上传PDF文件")
else:
    # 双栏布局
    left_col, right_col = st.columns([3, 2])
    
    with left_col:
        st.subheader("📄 PDF阅读器")
        st.write("左栏：PDF显示区域")
        st.button("运行AI预标注")
        
    with right_col:
        st.subheader("📝 识别结果编辑器")
        st.write("右栏：标注编辑区域")
        st.text_area("识别文本", value="测试文本", height=100)
