#!/usr/bin/env python3
"""
用户名/密码登录，使用多种信号检测登录成功
增强等待和诊断
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

def wait_for_login_success(page, timeout=45000):
    """
    使用多种信号检测登录成功
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout / 1000:
        # 1. 检查 URL 是否跳离 /login
        if "/login" not in page.url:
            log("✅ 检测到 URL 跳转")
            return True
        # 2. 检查退出按钮
        try:
            if page.locator("button:has-text('退出'), a:has-text('退出'), button:has-text('Logout')").count() > 0:
                log("✅ 检测到退出按钮")
                return True
        except:
            pass
        # 3. 检查用户头像或用户菜单（常见 class）
        try:
            if page.locator("img[alt*='avatar'], .avatar, .user-avatar, [class*='avatar']").count() > 0:
                log("✅ 检测到用户头像")
                return True
        except:
            pass
        # 4. 检查页面标题是否包含非登录字样
        try:
            title = page.title()
            if "控制台" in title or "Dashboard" in title or "平台" in title:
                log(f"✅ 页面标题: {title}")
                return True
        except:
            pass
        # 5. 检查“一键配置QwenPaw”按钮
        try:
            if page.locator(f"button:has-text('{BUTTON_DEPLOY}'), a:has-text('{BUTTON_DEPLOY}')").count() > 0:
                log(f"✅ 检测到 '{BUTTON_DEPLOY}' 按钮")
                return True
        except:
            pass
        # 每 2 秒检查一次
        time.sleep(2)
    return False

def run():
    log("启动 Agentscope 自动登录（增强检测）")
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
            # 等待可能的重定向
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)
            screenshot(page, "01_login_page")

            # 如果已经登录（URL 不在 /login 且没有登录按钮）
            if "/login" not in page.url and page.locator("button:has-text('登录')").count() == 0:
                log("✅ 似乎已登录，跳过登录流程")
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

                # 点击登录按钮
                submit_btn = page.wait_for_selector(
                    "button:has-text('登录'), button[type='submit']",
                    timeout=10000
                )
                submit_btn.click()
                log("⏳ 已点击登录按钮，等待登录成功...")
                screenshot(page, "04_after_click")

                # 等待登录成功（最长 45 秒）
                success = wait_for_login_success(page, timeout=45000)
                if not success:
                    screenshot(page, "05_login_failed")
                    # 输出页面信息帮助调试
                    log(f"当前 URL: {page.url}")
                    log(f"页面标题: {page.title()}")
                    # 尝试获取错误信息
                    error = page.locator(".error, .alert, .message:has-text('错误')")
                    if error.count():
                        err_text = error.text_content()
                        log(f"❌ 登录失败: {err_text}")
                        raise RuntimeError(f"登录失败: {err_text}")
                    else:
                        # 输出部分 HTML
                        html_preview = page.content()[:1000]
                        log(f"页面内容预览: {html_preview}")
                        raise RuntimeError("登录超时：未检测到任何登录成功信号")

            log("✅ 登录成功")
            screenshot(page, "06_logged_in")

            # 等待页面完全加载
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)

            # 点击“打开QWENPAW”（跳过第一个按钮，因为登录后可能直接显示第二个）
            # 但为了以防万一，先检测第一个按钮是否存在，如果不存在直接点第二个
            try:
                deploy_btn = page.locator(f"button:has-text('{BUTTON_DEPLOY}'), a:has-text('{BUTTON_DEPLOY}')")
                if deploy_btn.count() > 0 and deploy_btn.is_visible():
                    deploy_btn.click()
                    log(f"✅ 点击 '{BUTTON_DEPLOY}'")
                    time.sleep(3)
            except:
                pass

            # 点击“打开QWENPAW”
            try:
                qwen_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_QWENPAW}'), a:has-text('{BUTTON_QWENPAW}')",
                    timeout=10000
                )
                if qwen_btn and qwen_btn.is_visible():
                    qwen_btn.click()
                    log(f"✅ 已点击 '{BUTTON_QWENPAW}'")
                    log("⏳ 等待 5 秒...")
                    time.sleep(5)
                    screenshot(page, "07_qwen_clicked")
                else:
                    log(f"⚠️ 按钮 '{BUTTON_QWENPAW}' 不可见")
                    screenshot(page, "07_qwen_not_found")
            except PlaywrightTimeoutError:
                log(f"⚠️ 未找到按钮 '{BUTTON_QWENPAW}'")
                screenshot(page, "07_qwen_not_found")

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功")

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
