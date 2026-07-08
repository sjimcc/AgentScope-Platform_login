#!/usr/bin/env python3
"""
登录后先点击“一键配置QwenPaw”，等待其生效后再点击“打开QWENPAW”
使用 Enter 提交登录，基于 localStorage 检测登录成功
"""
import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

USERNAME = os.getenv("AGENTSCOPE_USERNAME", "")
PASSWORD = os.getenv("AGENTSCOPE_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")

BUTTON_DEPLOY = os.getenv("BUTTON_DEPLOY", "一键配置QwenPaw")
BUTTON_QWENPAW = os.getenv("BUTTON_QWENPAW", "打开QWENPAW")

LOGIN_URL = "https://platform.agentscope.io/login"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_tg(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            log(f"Telegram 发送失败: {e}")

def screenshot(page, name):
    try:
        page.screenshot(path=f"{name}.png")
        log(f"📸 截图: {name}.png")
    except Exception as e:
        log(f"截图失败 {name}: {e}")

def wait_for_token(page, timeout=60000):
    start = time.time()
    while (time.time() - start) < timeout / 1000:
        token = page.evaluate("() => localStorage.getItem('accessToken')")
        if token:
            log("✅ 检测到 accessToken，登录成功")
            return True
        error = page.locator(".error, .alert, .message:has-text('错误'), .message:has-text('失败')")
        if error.count():
            err_text = error.text_content()
            log(f"❌ 登录失败: {err_text}")
            return False
        time.sleep(2)
    return False

def run():
    log("启动 Agentscope 自动登录（先点击配置，再点打开）")
    if not USERNAME or not PASSWORD:
        log("❌ 请设置 AGENTSCOPE_USERNAME 和 AGENTSCOPE_PASSWORD")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        try:
            log(f"🌐 访问登录页面: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)
            screenshot(page, "01_login_page")

            # 检查是否已登录
            token = page.evaluate("() => localStorage.getItem('accessToken')")
            if token:
                log("✅ 已检测到 accessToken，跳过登录")
            else:
                log("📝 填写登录表单...")
                username_input = page.wait_for_selector("#account", timeout=10000)
                username_input.fill(USERNAME)
                log("✅ 已填写邮箱")
                screenshot(page, "02_username_filled")

                password_input = page.wait_for_selector("#password", timeout=10000)
                password_input.fill(PASSWORD)
                log("✅ 已填写密码")
                screenshot(page, "03_password_filled")

                log("⏳ 按 Enter 键提交登录...")
                password_input.press("Enter")
                screenshot(page, "04_after_enter")

                log("⏳ 等待 accessToken 出现...")
                success = wait_for_token(page, timeout=60000)
                if not success:
                    # 尝试点击登录按钮作为备选
                    log("⚠️ Enter 提交未生效，尝试点击登录按钮...")
                    submit_btn = page.locator("button:has-text('登录'), button[type='submit']")
                    if submit_btn.count():
                        submit_btn.click()
                        success = wait_for_token(page, timeout=30000)

                if not success:
                    screenshot(page, "05_login_failed")
                    storage = page.evaluate("() => localStorage")
                    log(f"当前 localStorage 内容: {storage}")
                    raise RuntimeError("登录超时或失败，未检测到 accessToken")

            log("✅ 登录成功")
            screenshot(page, "06_logged_in")

            # 等待页面完全加载
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)

            # ---------- 第一步：点击“一键配置QwenPaw” ----------
            log(f"🔍 查找 '{BUTTON_DEPLOY}' 按钮...")
            try:
                deploy_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_DEPLOY}'), a:has-text('{BUTTON_DEPLOY}')",
                    timeout=15000
                )
                if deploy_btn and deploy_btn.is_visible():
                    deploy_btn.click()
                    log(f"✅ 点击 '{BUTTON_DEPLOY}' 成功")
                    screenshot(page, "07_deploy_clicked")
                    # 点击后等待一段时间，让第二个按钮出现
                    log("⏳ 等待 5 秒，让 '打开QWENPAW' 按钮出现...")
                    time.sleep(5)
                else:
                    log(f"⚠️ 按钮 '{BUTTON_DEPLOY}' 不可见")
                    screenshot(page, "07_deploy_not_found")
                    # 如果第一个按钮不存在，可能已经处于可点击第二个的状态？但根据逻辑，必须先点第一个，所以报错
                    raise RuntimeError("未找到 '一键配置QwenPaw' 按钮，无法继续")
            except PlaywrightTimeoutError:
                log(f"❌ 超时未找到 '{BUTTON_DEPLOY}' 按钮")
                screenshot(page, "07_deploy_timeout")
                raise RuntimeError("超时未找到 '一键配置QwenPaw' 按钮")

            # ---------- 第二步：点击“打开QWENPAW” ----------
            log(f"🔍 查找 '{BUTTON_QWENPAW}' 按钮...")
            try:
                qwen_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_QWENPAW}'), a:has-text('{BUTTON_QWENPAW}')",
                    timeout=15000
                )
                if qwen_btn and qwen_btn.is_visible():
                    qwen_btn.click()
                    log(f"✅ 点击 '{BUTTON_QWENPAW}' 成功")
                    log("⏳ 等待 5 秒...")
                    time.sleep(5)
                    screenshot(page, "08_qwen_clicked")
                else:
                    log(f"⚠️ 按钮 '{BUTTON_QWENPAW}' 不可见")
                    screenshot(page, "08_qwen_not_found")
                    raise RuntimeError("未找到 '打开QWENPAW' 按钮")
            except PlaywrightTimeoutError:
                log(f"❌ 超时未找到 '{BUTTON_QWENPAW}' 按钮")
                screenshot(page, "08_qwen_timeout")
                raise RuntimeError("超时未找到 '打开QWENPAW' 按钮")

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功（依次点击了两个按钮）")

        except Exception as e:
            log(f"❌ 异常: {e}")
            screenshot(page, "error")
            send_tg(f"❌ Agentscope 脚本失败\n错误: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 脚本退出: {e}")
        sys.exit(1)
