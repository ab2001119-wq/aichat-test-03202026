import streamlit.web.cli as stcli
import os, sys

def resolve_path(path):
    # 這個函數能確保程式打包後，還能找到你的 app.py
    resolved_path = os.path.abspath(os.path.join(os.getcwd(), path))
    return resolved_path

if __name__ == "__main__":
    # 告訴系統我們要執行 app.py
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())