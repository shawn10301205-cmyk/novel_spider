"""飞书 Webhook 机器人通知"""

import json
from datetime import datetime

import requests


class FeishuWebhookNotifier:
    """通过飞书自定义机器人 Webhook 发送通知"""

    def __init__(self, webhook_url: str, app_url: str = ""):
        self.webhook_url = webhook_url
        self.app_url = app_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def send_text(self, text: str) -> bool:
        """发送纯文本消息"""
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return self._send(payload)

    def send_scrape_report(self, results: dict, total: int, date: str, errors: list = None):
        """
        发送抓取完成的富文本卡片消息

        Args:
            results: 各数据源结果 {source_key: {name, count, from_storage, error?}}
            total: 总数据条数
            date: 数据日期
            errors: 错误列表
        """
        now = datetime.now().strftime("%H:%M:%S")

        # 构建各平台状态行
        source_lines = []
        for key, r in results.items():
            name = r.get("name", key)
            count = r.get("count", 0)
            if r.get("error"):
                source_lines.append(f"❌ {name}: 失败 ({r['error']})")
            elif r.get("from_storage"):
                source_lines.append(f"📦 {name}: {count} 条 (缓存)")
            else:
                source_lines.append(f"✅ {name}: {count} 条 (新抓取)")

        source_text = "\n".join(source_lines)

        # 构建互动卡片消息
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📅 **日期**: {date}\n⏰ **时间**: {now}\n📊 **总数据量**: **{total}** 条",
                },
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**各平台详情：**\n{source_text}",
                },
            },
        ]

        # 如果有错误
        if errors:
            error_text = "\n".join(f"⚠️ {e}" for e in errors)
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**异常信息：**\n{error_text}",
                },
            })

        # 添加查看看板按钮
        if self.app_url:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📊 打开市场看板"},
                        "type": "primary",
                        "url": self.app_url,
                    }
                ],
            })

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📚 小说排行榜数据更新完成",
                    },
                    "template": "turquoise",
                },
                "elements": elements,
            },
        }

        return self._send(card)

    def _send(self, payload: dict) -> bool:
        """发送消息到 Webhook"""
        if not self.is_configured():
            print("⚠ Webhook URL 未配置")
            return False

        try:
            resp = requests.post(
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0 or data.get("StatusCode") == 0:
                print("✅ 飞书群通知发送成功")
                return True
            else:
                print(f"❌ 飞书群通知发送失败: {data}")
                return False
        except Exception as e:
            print(f"❌ 飞书群通知异常: {e}")
            return False
