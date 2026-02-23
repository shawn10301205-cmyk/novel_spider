"""数据存储层 - 按天存储抓取结果到 data/{YYYY-MM-DD}/ 目录"""

import json
import os
from datetime import date, datetime
from typing import Optional

from models.novel import NovelRank


# 存储目录：项目根目录下的 data/
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _ensure_dir(day: Optional[str] = None):
    day = day or today_str()
    day_dir = os.path.join(DATA_DIR, day)
    os.makedirs(day_dir, exist_ok=True)
    return day_dir


def _data_path(source: str, day: str) -> str:
    """数据文件路径: data/{YYYY-MM-DD}/{source}.json"""
    return os.path.join(DATA_DIR, day, f"{source}.json")


def _legacy_data_path(source: str, day: str) -> str:
    """兼容旧格式: data/{source}_{YYYY-MM-DD}.json"""
    return os.path.join(DATA_DIR, f"{source}_{day}.json")


def today_str() -> str:
    return date.today().isoformat()


def has_data(source: str, day: Optional[str] = None) -> bool:
    """检查指定数据源某天是否有数据"""
    day = day or today_str()
    # 先查新路径, 再查旧路径
    return os.path.exists(_data_path(source, day)) or os.path.exists(_legacy_data_path(source, day))


def save_data(source: str, novels: list[NovelRank], day: Optional[str] = None):
    """保存抓取结果到日期文件夹"""
    day = day or today_str()
    _ensure_dir(day)
    path = _data_path(source, day)

    payload = {
        "source": source,
        "date": day,
        "updated_at": datetime.now().isoformat(),
        "total": len(novels),
        "novels": [n.to_dict() for n in novels],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  💾 已保存 {len(novels)} 条 -> {path}")


def load_data(source: str, day: Optional[str] = None) -> list[dict]:
    """加载某天某数据源的数据, 兼容新旧两种路径"""
    day = day or today_str()

    # 优先新路径
    path = _data_path(source, day)
    if not os.path.exists(path):
        # 尝试旧路径
        path = _legacy_data_path(source, day)
        if not os.path.exists(path):
            return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"  📂 已加载 {data.get('total', 0)} 条 ({source}, {day})")
    return data.get("novels", [])


def list_dates() -> list[str]:
    """列出所有有数据的日期"""
    os.makedirs(DATA_DIR, exist_ok=True)
    dates = set()
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        # 新格式: data/2026-02-23/ (目录)
        if os.path.isdir(item_path) and len(item) == 10 and item[4] == '-':
            dates.add(item)
        # 旧格式: data/fanqie_2026-02-23.json (文件)
        elif item.endswith(".json"):
            parts = item.rsplit("_", 1)
            if len(parts) == 2:
                day = parts[1].replace(".json", "")
                dates.add(day)
    return sorted(dates, reverse=True)
