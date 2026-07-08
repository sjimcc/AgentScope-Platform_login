#!/usr/bin/env python3
"""
使用 Cookie 自动登录 https://platform.agentscope.io/ 并点击“打开 QwenPaw”按钮
增强登录状态检查，支持多种按钮文本。
环境变量：
  AGENTSCOPE_COOKIE  - 登录后的 Cookie 字符串（必填）
  AGENTSCOPE_HEADLESS - 是否无头模式（默认 true）
  TG_BOT_TOKEN       - Telegram Bot Token（可选）
  TG_CHAT_ID         - Telegram Chat ID（可选）
  LOGIN_SUCCESS_INDICATOR - 登录后页面的 CSS 选择器（可选）
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------- 配置 ----------
COOKIE_STR = os.getenv("AGENTSCOPE_COOKIE", "")
HEADLESS = os.getenv("AGENTSCOPE_HEADLESS", "true").lower() == "true"
LOGIN_URL = "https://platform.agentscope.io/"
TARGET_BUTTON_TEXTS = ["打开 QwenPaw", "QwenPaw", "Launch QwenPaw", "Open QwenPaw"]
LOGIN_SUCCESS_INDICATOR = os.getenv("LOGIN_SUCCESS_INDICATOR", "")  # 例如 ".user-avatar"

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")

# ---------- 日志 ----------
def log(level: str, msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

# ---------- Telegram 通知 ----------
def send_telegram(message: str) -> bool:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, json=data, timeout=30)
        resp.raise_for_status()
        log("INFO", "Telegram 消息发送成功")
        return True
    except Exception as e:
        log("ERROR", f"Telegram 发送失败: {e}")
        return False

# ---------- 解析 Cookie ----------
def parse_cookie_string(cookie_str: str, domain: str = "platform.agentscope.io"):
    cookies = []
    for item in cookie_str.split(';'):
        item = item.strip()
        if not item or '=' not in item:
            continue
        key, value = item.split('=', 1)
        cookies.append({
            "name": key.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
            "httpOnly": False,
            "secure": False,
            "sameSite": "Lax"
        })
    return cookies

# ---------- 检查 Cookie 过期 ----------
def check_cookie_expiry_from_browser(context):
    all_cookies = context.cookies()
    now = datetime.now(tz=timezone.utc)
    for c in all_cookies:
        if 'expires' in c and c['expires']:
            expiry_ts = c['expires']
            expiry_dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
            remaining = expiry_dt - now
            days = remaining.total_seconds() / 86400
            log("INFO", f"Cookie '{c['name']}' 过期时间: {expiry_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')} (剩余 {days:.1f} 天)")
            if days < 3:
                log("WARN", f"⚠️ Cookie '{c['name']}' 将在 {days:.1f} 天后过期，请及时更新")

# ---------- 增强版登录状态检查 ----------
def check_login_status(page) -> bool:
    """返回 True 表示已登录，False 表示未登录"""
    # 1. 检查是否存在“登录”按钮（未登录标志）
    login_btn = page.locator(
        "button:has-text('登录'), button:has-text('Sign in'), "
        "a:has-text('登录'), a:has-text('Sign in'), "
        "button:has-text('Login'), a:has-text('Login')"
    )
    if login_btn.count() and login_btn.is_visible():
        log("WARN", "检测到 '登录' 按钮，当前未登录")
        return False

    # 2. 自定义登录成功标志
    if LOGIN_SUCCESS_INDICATOR:
        try:
            page.wait_for_selector(LOGIN_SUCCESS_INDICATOR, timeout=5000)
            log("INFO", "✅ 检测到自定义登录成功标志元素")
            return True
        except PlaywrightTimeoutError:
            log("WARN", "未找到自定义登录成功标志元素")

    # 3. URL 是否包含登录路径
    current_url = page.url.lower()
    if "/login" in current_url or "/signin" in current_url:
        log("WARN", f"当前 URL 包含登录路径: {current_url}")
        return False

    # 4. 检查密码输入框
    password_input = page.locator("input[type='password']")
    if password_input.count():
        log("WARN", "页面存在密码输入框，可能未登录")
        return False

    # 5. 检查页面是否有“退出”按钮（有则说明已登录）
    logout_btn = page.locator("button:has-text('退出'), button:has-text('Logout'), a:has-text('退出'), a:has-text('Logout')")
    if logout_btn.count() and logout_btn.is_visible():
        log("INFO", "✅ 检测到退出按钮，已登录")
        return True

    # 6. 兜底：如果页面文本包含“登录”且无“退出”，认为未登录
    body_text = page.text_content("body").lower()
    if ("登录" in body_text or "sign in" in body_text) and not logout_btn.count():
        log("WARN", "页面包含登录字样且无退出按钮，可能未登录")
        return False

    log("INFO", "✅ 综合判断已登录")
    return True

# ---------- 主函数 ----------
def run():
    log("INFO", "启动 Agentscope Cookie 自动登录脚本 (增强检查)...")
    if not COOKIE_STR:
        log("ERROR", "请设置环境变量 AGENTSCOPE_COOKIE")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        cookies = parse_cookie_string(COOKIE_STR, domain="platform.agentscope.io")
        log("INFO", f"添加 {len(cookies)} 个 Cookie")
        context.add_cookies(cookies)

        page = context.new_page()
        try:
            log("INFO", f"正在访问 {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

            # 等待页面稳定
            page.wait_for_timeout(3000)

            # 检查 Cookie 过期
            check_cookie_expiry_from_browser(context)

            # 登录状态检查
            if not check_login_status(page):
                page.screenshot(path="login_failed.png")
                raise RuntimeError("登录状态检查失败：Cookie 无效或已过期")

            # 尝试点击目标按钮（多种文本）
            clicked = False
            for text in TARGET_BUTTON_TEXTS:
                try:
                    btn = page.wait_for_selector(
                        f"button:has-text('{text}'), a:has-text('{text}'), "
                        f"div:has-text('{text}') >> button, [role='button']:has-text('{text}')",
                        timeout=3000
                    )
                    if btn and btn.is_visible():
                        btn.click()
                        log("INFO", f"✅ 成功点击 '{text}'")
                        clicked = True
                        break
                except PlaywrightTimeoutError:
                    continue
            if not clicked:
                # 输出页面部分内容辅助调试
                page.screenshot(path="button_not_found.png")
                body_preview = page.text_content("body")[:500]
                log("ERROR", f"未找到任何匹配按钮，页面预览: {body_preview}")
                raise RuntimeError("未找到目标按钮")

            # 等待可能的跳转/新窗口
            time.sleep(3)
            log("INFO", "✅ 脚本执行成功")

            send_telegram(
                f"✅ <b>Agentscope 自动操作成功</b>\n"
                f"🍪 使用 Cookie 登录\n"
                f"⏱️ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📋 已点击目标按钮"
            )

        except Exception as e:
            log("ERROR", f"执行异常: {e}")
            page.screenshot(path="error_screenshot.png")
            send_telegram(
                f"❌ <b>Agentscope 自动操作失败</b>\n"
                f"⏱️ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📝 错误: {e}"
            )
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log("WARN", "用户中断")
        sys.exit(130)
    except Exception as e:
        log("ERROR", f"脚本失败: {e}")
        sys.exit(1)
