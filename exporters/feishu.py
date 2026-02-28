"""飞书多维表格推送导出器"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from models.novel import NovelRank


class FeishuExporter:
    """飞书多维表格导出器"""

    TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    BITABLE_URL = "https://open.feishu.cn/open-apis/bitable/v1"

    def __init__(self, config: dict):
        """
        初始化飞书导出器

        Args:
            config: 飞书配置，包含 app_id, app_secret, app_token, table_id
        """
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self.app_token = config.get("app_token", "")
        self.table_id = config.get("table_id", "")
        self._token: Optional[str] = None

    def is_configured(self) -> bool:
        """检查飞书凭证是否已配置"""
        return all([self.app_id, self.app_secret, self.app_token, self.table_id])

    def _get_tenant_token(self) -> str:
        """获取 tenant_access_token"""
        if self._token:
            return self._token

        resp = requests.post(self.TOKEN_URL, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        })
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取飞书 token 失败: {data.get('msg')}")

        self._token = data["tenant_access_token"]
        return self._token

    def _get_headers(self) -> dict:
        """获取请求头"""
        token = self._get_tenant_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def export(self, novels: list[NovelRank], clear_existing: bool = True):
        """
        导出数据到飞书多维表格

        Args:
            novels: 排行榜数据
            clear_existing: 是否清除已有数据
        """
        if not self.is_configured():
            print("⚠ 飞书凭证未配置，请在 config.yaml 中填写飞书配置信息")
            print("  需要配置: app_id, app_secret, app_token, table_id")
            return

        print(f"📤 正在推送 {len(novels)} 条数据到飞书多维表格...")

        try:
            if clear_existing:
                self._clear_records()

            # 批量写入，每批 500 条
            batch_size = 500
            for i in range(0, len(novels), batch_size):
                batch = novels[i:i + batch_size]
                self._batch_create_records(batch)
                print(f"  ✓ 已写入 {min(i + batch_size, len(novels))}/{len(novels)} 条")

            print("✅ 飞书多维表格推送完成！")

        except Exception as e:
            print(f"❌ 飞书推送失败: {e}")

    def _clear_records(self):
        """清除多维表格中的已有记录"""
        url = f"{self.BITABLE_URL}/apps/{self.app_token}/tables/{self.table_id}/records"

        # 先获取所有记录 ID
        record_ids = []
        page_token = None

        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(url, headers=self._get_headers(), params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                print(f"  ⚠ 获取已有记录失败: {data.get('msg')}")
                return

            items = data.get("data", {}).get("items", [])
            record_ids.extend([item["record_id"] for item in items])

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data["data"].get("page_token")

        # 批量删除
        if record_ids:
            print(f"  正在清除 {len(record_ids)} 条已有记录...")
            batch_size = 500
            for i in range(0, len(record_ids), batch_size):
                batch_ids = record_ids[i:i + batch_size]
                delete_url = f"{url}/batch_delete"
                resp = requests.post(
                    delete_url,
                    headers=self._get_headers(),
                    json={"records": batch_ids}
                )
                resp.raise_for_status()

    @staticmethod
    def _today_timestamp():
        """获取今天 0 点的毫秒时间戳（北京时间）"""
        tz = timezone(timedelta(hours=8))
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(today.timestamp() * 1000)

    def _batch_create_records(self, novels: list[NovelRank]):
        """批量创建记录"""
        url = f"{self.BITABLE_URL}/apps/{self.app_token}/tables/{self.table_id}/records/batch_create"

        today_ts = self._today_timestamp()
        records = []
        for novel in novels:
            fields = {
                "文本": novel.title,
                "作者": novel.author,
                "分类": novel.category,
                "热度": novel.rank,
                "状态": novel.period if novel.period else "连载中",
                "来源": novel.source,
                "采集日期": today_ts,
            }
            records.append({"fields": fields})

        resp = requests.post(url, headers=self._get_headers(), json={"records": records})
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"批量创建记录失败: {data.get('msg')}")

    def create_table_if_needed(self):
        """
        检查并创建所需的数据表字段（需要手动创建表格，此方法仅提示所需字段）
        """
        print("📋 飞书多维表格所需字段：")
        fields = [
            ("文本", "文本 (书名)"),
            ("作者", "文本"),
            ("分类", "单选 (玄幻/都市/科幻/...)"),
            ("热度", "数字 (排名)"),
            ("状态", "单选 (连载中/已完结/断更)"),
            ("来源", "文本"),
            ("采集日期", "日期 (自动填充)"),
        ]
        for name, field_type in fields:
            print(f"  - {name}: {field_type}")
