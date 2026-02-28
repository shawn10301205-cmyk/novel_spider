"""
飞书多维表格 API 工具
用于将小说数据推送到飞书多维表格

使用方法:
    from feishu_bitable import FeishuBitable

    bitable = FeishuBitable()
    # 写入单条数据
    bitable.add_record({"文本": "书名", "作者": "xxx", "热度": 100})
    # 批量写入
    bitable.batch_add_records([...])
    # 查询数据
    records = bitable.list_records()
"""

import requests
import time
import json
from datetime import datetime, timezone, timedelta


class FeishuBitable:
    """飞书多维表格 API 封装"""

    # ====== 配置区域（按需修改）======
    APP_ID = "cli_a917ef7a7eb85cc8"
    APP_SECRET = "2mlszAby4Ywn3IR8cKOodNtUjIBdYRKt"
    APP_TOKEN = "TmTYbWhw9aYNZdsYoEDc61Henxg"  # 多维表格 app_token
    TABLE_ID = "tblU2vhvqvzIQIjm"                # 数据表 table_id
    # ================================

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self):
        self._token = None
        self._token_expire_at = 0

    @property
    def token(self):
        """获取 tenant_access_token，自动刷新"""
        if time.time() >= self._token_expire_at:
            self._refresh_token()
        return self._token

    def _refresh_token(self):
        """刷新 tenant_access_token"""
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.APP_ID,
            "app_secret": self.APP_SECRET
        })
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data}")
        self._token = data["tenant_access_token"]
        # 提前 5 分钟刷新
        self._token_expire_at = time.time() + data.get("expire", 7200) - 300
        print(f"✅ Token 刷新成功，有效期至 {time.strftime('%H:%M:%S', time.localtime(self._token_expire_at))}")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _table_url(self, path=""):
        return f"{self.BASE_URL}/bitable/v1/apps/{self.APP_TOKEN}/tables/{self.TABLE_ID}{path}"

    # ==================== 写入操作 ====================

    @staticmethod
    def _today_timestamp():
        """获取今天 0 点的毫秒时间戳（北京时间）"""
        tz = timezone(timedelta(hours=8))
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(today.timestamp() * 1000)

    def _auto_fill_date(self, fields: dict) -> dict:
        """自动填充采集日期（如果未指定）"""
        if "采集日期" not in fields:
            fields["采集日期"] = self._today_timestamp()
        return fields

    def add_record(self, fields: dict) -> dict:
        """
        新增单条记录（自动填充采集日期）

        Args:
            fields: 字段字典，例如 {"文本": "斗破苍穹", "作者": "天蚕土豆", "热度": 98500}

        Returns:
            新增记录的信息
        """
        fields = self._auto_fill_date(fields)
        url = self._table_url("/records")
        resp = requests.post(url, headers=self._headers(), json={"fields": fields})
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"新增记录失败: {data}")
        print(f"✅ 新增记录成功: {fields.get('文本', '')}")
        return data["data"]["record"]

    def batch_add_records(self, records_list: list) -> list:
        """
        批量新增记录（每批最多 500 条）

        Args:
            records_list: 字段字典列表，例如 [{"文本": "书名", "作者": "xx"}, ...]

        Returns:
            新增记录列表
        """
        all_results = []
        # 自动填充日期
        records_list = [self._auto_fill_date(r) for r in records_list]
        # 分批处理，每批 500 条
        for i in range(0, len(records_list), 500):
            batch = records_list[i:i + 500]
            url = self._table_url("/records/batch_create")
            body = {"records": [{"fields": r} for r in batch]}
            resp = requests.post(url, headers=self._headers(), json=body)
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(f"批量新增失败 (第{i // 500 + 1}批): {data}")
            results = data["data"]["records"]
            all_results.extend(results)
            print(f"✅ 第{i // 500 + 1}批写入成功，本批 {len(results)} 条")
        print(f"📊 共写入 {len(all_results)} 条记录")
        return all_results

    # ==================== 查询操作 ====================

    def list_records(self, page_size=100, filter_expr=None) -> list:
        """
        查询记录

        Args:
            page_size: 每页数量，最大 500
            filter_expr: 筛选表达式，例如 'CurrentValue.[热度] > 50000'

        Returns:
            记录列表
        """
        all_records = []
        page_token = None

        while True:
            url = self._table_url("/records/search")
            body = {"page_size": page_size}
            if filter_expr:
                body["filter"] = {"conjunction": "and", "conditions": []}
            if page_token:
                body["page_token"] = page_token

            resp = requests.post(url, headers=self._headers(), json=body)
            data = resp.json()
            if data.get("code") != 0:
                raise Exception(f"查询记录失败: {data}")

            items = data["data"].get("items", [])
            all_records.extend(items)

            if not data["data"].get("has_more"):
                break
            page_token = data["data"].get("page_token")

        print(f"📋 共查询到 {len(all_records)} 条记录")
        return all_records

    # ==================== 更新操作 ====================

    def update_record(self, record_id: str, fields: dict) -> dict:
        """更新单条记录"""
        url = self._table_url(f"/records/{record_id}")
        resp = requests.put(url, headers=self._headers(), json={"fields": fields})
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"更新记录失败: {data}")
        print(f"✅ 更新记录成功: {record_id}")
        return data["data"]["record"]

    # ==================== 删除操作 ====================

    def delete_records(self, record_ids: list):
        """批量删除记录"""
        url = self._table_url("/records/batch_delete")
        resp = requests.post(url, headers=self._headers(), json={"records": record_ids})
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"删除记录失败: {data}")
        print(f"🗑️ 删除 {len(record_ids)} 条记录成功")


# ==================== 工具函数 ====================
def _extract_text(value):
    """从飞书文本字段中提取纯文本"""
    if isinstance(value, list):
        return "".join(item.get("text", "") for item in value if isinstance(item, dict))
    return str(value) if value else ""


# ==================== 使用示例 ====================
if __name__ == "__main__":
    bitable = FeishuBitable()

    # 示例：批量写入小说数据（采集日期会自动填充为今天）
    novels = [
        {
            "文本": "吞噬星空",
            "作者": "我吃西红柿",
            "分类": "科幻",
            "热度": 92000,
            "字数(万)": 450,
            "状态": "已完结",
            "来源": "起点中文网"
        },
        {
            "文本": "全职高手",
            "作者": "蝴蝶蓝",
            "分类": "游戏",
            "热度": 88000,
            "字数(万)": 530,
            "状态": "已完结",
            "来源": "起点中文网"
        },
    ]

    print("=== 批量写入小说数据 ===")
    bitable.batch_add_records(novels)

    print("\n=== 查询所有记录 ===")
    records = bitable.list_records()
    for r in records:
        fields = r["fields"]
        name = _extract_text(fields.get("文本", "未知"))
        author = _extract_text(fields.get("作者", "未知"))
        热度 = fields.get("热度", 0)
        print(f"  📖 {name} - {author} | 热度: {热度}")
