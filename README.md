# AgentScope-Platform_login
AgentScope Platform每3h检查状态,进行保活
获取 Cookie

使用浏览器（Chrome/Edge）登录 platform.agentscope.io

1.按 F12 打开开发者工具 → 切换到 Application（或 Storage）标签 → 左侧选择 Cookies → 找到该网站的域名

将所有 Cookie 的 Name 和 Value 按照 name1=value1; name2=value2 格式拼接，例如：


sessionid=abc123; csrftoken=xyz789; user_id=12345
添加 GitHub Secrets

进入仓库 → Settings → Secrets and variables → Actions

点击 New repository secret，分别添加上述变量（名称严格区分大小写）

示例值（仅作参考，请使用实际值）：

AGENTSCOPE_COOKIE: sessionid=abc123; csrftoken=xyz789; user_id=12345

TG_BOT_TOKEN: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

TG_CHAT_ID: -123456789

LOGIN_SUCCESS_INDICATOR: .user-avatar（若不需要可留空）
