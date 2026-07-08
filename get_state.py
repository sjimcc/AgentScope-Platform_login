# get_state.py
from playwright.sync_api import sync_playwright
import json, base64

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    print("浏览器已打开，请登录 https://platform.agentscope.io/")
    page.goto("https://platform.agentscope.io/")
    input("登录成功后，按 Enter 继续...")
    state = context.storage_state()
    b64 = base64.b64encode(json.dumps(state).encode()).decode()
    print("\n--- 复制以下 Base64 到 GitHub Secret AGENTSCOPE_STATE ---\n")
    print(b64)
    print("\n----------------------------------------------------------")
    # 可选保存到文件
    with open("state_b64.txt", "w") as f:
        f.write(b64)
    print("已同时保存到 state_b64.txt 文件")
    browser.close()
