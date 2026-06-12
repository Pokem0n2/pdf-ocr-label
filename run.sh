#!/bin/bash
# PDF条文标注工具启动脚本

# 激活虚拟环境
source ~/pdf-label-env/bin/activate

# 设置环境变量
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 启动Streamlit
cd ~/pdf-label-tool
streamlit run app.py "$@"
