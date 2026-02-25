"""数据存储层 - SQLite 存储，每条记录含常用字段 + 完整 JSON"""

import json
import os
import re
import sqlite3
from datetime import date, datetime
from typing import Optional

from models.novel import NovelRank


# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "novels.db")
# 旧 JSON 数据目录（兼容迁移）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """创建表和索引"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS novel_ranks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            source      TEXT NOT NULL,
            source_name TEXT NOT NULL DEFAULT '',
            rank        INTEGER NOT NULL,
            title       TEXT NOT NULL,
            author      TEXT NOT NULL DEFAULT '',
            category    TEXT NOT NULL DEFAULT '',
            gender      TEXT NOT NULL DEFAULT '',
            period      TEXT NOT NULL DEFAULT '',
            book_url    TEXT DEFAULT '',
            heat        TEXT DEFAULT '',
            heat_value  REAL DEFAULT 0,
            raw_json    TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_date ON novel_ranks(date);
        CREATE INDEX IF NOT EXISTS idx_source ON novel_ranks(source, date);
        CREATE INDEX IF NOT EXISTS idx_title ON novel_ranks(title);
        CREATE INDEX IF NOT EXISTS idx_author ON novel_ranks(author);
        CREATE INDEX IF NOT EXISTS idx_category ON novel_ranks(category, date);
        CREATE INDEX IF NOT EXISTS idx_gender ON novel_ranks(gender, date);
        CREATE INDEX IF NOT EXISTS idx_title_source ON novel_ranks(title, source, date);
    """)
    conn.commit()
    conn.close()


def parse_heat_value(heat_str: str) -> float:
    """解析热度文本为数值，如 '在读：41.1万' -> 411000.0"""
    if not heat_str:
        return 0.0
    cleaned = re.sub(r'^[^\d.]*', '', heat_str)
    m = re.match(r'([\d.]+)\s*(万)?', cleaned)
    if not m:
        return 0.0
    val = float(m.group(1))
    if m.group(2) == '万':
        val *= 10000
    return val


def today_str() -> str:
    return date.today().isoformat()


def has_data(source: str, day: Optional[str] = None) -> bool:
    """检查指定数据源某天是否有数据"""
    day = day or today_str()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM novel_ranks WHERE source=? AND date=?",
        (source, day)
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def save_data(source: str, novels: list[NovelRank], day: Optional[str] = None):
    """保存抓取结果到 SQLite"""
    day = day or today_str()
    conn = _get_conn()

    # 先删除同源同天旧数据（覆盖写入）
    conn.execute("DELETE FROM novel_ranks WHERE source=? AND date=?", (source, day))

    now = datetime.now().isoformat()
    rows = []
    for n in novels:
        d = n.to_dict()
        extra = d.get("extra", {})
        heat = extra.get("heat", "")
        hv = parse_heat_value(heat)
        rows.append((
            day,
            source,
            d.get("source", ""),   # source_name
            d.get("rank", 0),
            d.get("title", ""),
            d.get("author", ""),
            d.get("category", ""),
            d.get("gender", ""),
            d.get("period", ""),
            d.get("book_url", ""),
            heat,
            hv,
            json.dumps(d, ensure_ascii=False),
            now,
        ))

    conn.executemany("""
        INSERT INTO novel_ranks
            (date, source, source_name, rank, title, author, category, gender, period,
             book_url, heat, heat_value, raw_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()
    print(f"  💾 已保存 {len(novels)} 条 -> SQLite ({source}, {day})")


def load_data(source: str, day: Optional[str] = None) -> list[dict]:
    """加载某天某数据源的数据"""
    day = day or today_str()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT raw_json FROM novel_ranks WHERE source=? AND date=? ORDER BY rank",
        (source, day)
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append(json.loads(row["raw_json"]))

    print(f"  📂 已加载 {len(result)} 条 ({source}, {day})")
    return result


def list_dates() -> list[str]:
    """列出所有有数据的日期（降序）"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT date FROM novel_ranks ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return [row["date"] for row in rows]


def latest_date() -> str:
    """返回最近有数据的日期"""
    today = today_str()
    conn = _get_conn()

    # 今天有数据则用今天
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM novel_ranks WHERE date=?", (today,)
    ).fetchone()
    if row["cnt"] > 0:
        conn.close()
        return today

    # 否则取历史最新
    row = conn.execute(
        "SELECT date FROM novel_ranks ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["date"] if row else today


def get_novel_trend(title: str, source: Optional[str] = None, limit: int = 30) -> list[dict]:
    """查询某本小说历史热度数据，用于趋势图"""
    conn = _get_conn()

    if source:
        rows = conn.execute("""
            SELECT date, source, source_name, rank, heat, heat_value, category, gender, period, book_url, raw_json
            FROM novel_ranks
            WHERE title=? AND source=?
            ORDER BY date DESC
            LIMIT ?
        """, (title, source, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT date, source, source_name, rank, heat, heat_value, category, gender, period, book_url, raw_json
            FROM novel_ranks
            WHERE title=?
            ORDER BY date DESC
            LIMIT ?
        """, (title, limit)).fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "date": row["date"],
            "source": row["source"],
            "source_name": row["source_name"],
            "rank": row["rank"],
            "heat": row["heat"],
            "heat_value": row["heat_value"],
            "category": row["category"],
            "gender": row["gender"],
            "period": row["period"],
            "book_url": row["book_url"] or "",
        })

    return result


# ============================================================
# 数据迁移：旧 JSON -> SQLite
# ============================================================
def migrate_json_data():
    """扫描旧的 JSON 文件，导入 SQLite"""
    init_db()
    imported = 0

    if not os.path.isdir(DATA_DIR):
        print("⚠ 数据目录不存在，跳过迁移")
        return 0

    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)

        # 新格式目录: data/2026-02-23/
        if os.path.isdir(item_path) and len(item) == 10 and item[4] == '-':
            day = item
            for json_file in os.listdir(item_path):
                if not json_file.endswith(".json"):
                    continue
                source_key = json_file.replace(".json", "")
                filepath = os.path.join(item_path, json_file)
                count = _import_json_file(filepath, source_key, day)
                imported += count

        # 旧格式文件: data/fanqie_2026-02-23.json
        elif item.endswith(".json") and "_" in item:
            parts = item.rsplit("_", 1)
            if len(parts) == 2:
                source_key = parts[0]
                day = parts[1].replace(".json", "")
                filepath = os.path.join(DATA_DIR, item)
                count = _import_json_file(filepath, source_key, day)
                imported += count

    print(f"✅ 迁移完成，共导入 {imported} 条记录")
    return imported


def _import_json_file(filepath: str, source_key: str, day: str) -> int:
    """导入单个 JSON 文件"""
    conn = _get_conn()

    # 检查是否已导入
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM novel_ranks WHERE source=? AND date=?",
        (source_key, day)
    ).fetchone()
    if row["cnt"] > 0:
        conn.close()
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ⚠ 读取失败 {filepath}: {e}")
        conn.close()
        return 0

    novels = data.get("novels", [])
    if not novels:
        conn.close()
        return 0

    now = datetime.now().isoformat()
    rows = []
    for d in novels:
        extra = d.get("extra", {})
        heat = extra.get("heat", "")
        hv = parse_heat_value(heat)
        rows.append((
            day,
            source_key,
            d.get("source", ""),   # source_name
            d.get("rank", 0),
            d.get("title", ""),
            d.get("author", ""),
            d.get("category", ""),
            d.get("gender", ""),
            d.get("period", ""),
            d.get("book_url", ""),
            heat,
            hv,
            json.dumps(d, ensure_ascii=False),
            now,
        ))

    conn.executemany("""
        INSERT INTO novel_ranks
            (date, source, source_name, rank, title, author, category, gender, period,
             book_url, heat, heat_value, raw_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()
    print(f"  📥 导入 {len(rows)} 条 <- {filepath}")
    return len(rows)


# 启动时自动初始化
init_db()
