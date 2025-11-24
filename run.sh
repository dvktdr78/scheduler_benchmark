#!/bin/bash
# 스케줄러 벤치마크 실행 스크립트

cd "$(dirname "$0")/python_webapp"
source venv/bin/activate
streamlit run app.py
