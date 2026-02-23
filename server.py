#!/usr/bin/env python3
"""Flask Web API 服务"""

import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yaml

from scrapers import SCRAPER_REGISTRY
from sorter import apply_sort
from exporters.feishu import FeishuExporter
from storage import has_data, load_data, save_data, list_dates, today_str
from models.novel import NovelRank

app = Flask(__name__, static_folder="web", static_url_path="")
CORS(app)


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def get_scraper(source: str = "fanqie"):
    config = load_config()
    entry = SCRAPER_REGISTRY.get(source)
    if not entry:
        return None
    return entry["class"](config.get("scrape", {}))


def _scrape_and_save(source_key: str, gender=None, period=None):
    """抓取数据并存储，返回 dict 列表"""
    scraper = get_scraper(source_key)
    if not scraper:
        return []
    novels = scraper.scrape_all(gender=gender, period=period)
    save_data(source_key, novels)
    return [n.to_dict() for n in novels]


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/api/sources")
def api_sources():
    """获取所有可用数据源"""
    sources = []
    for key, entry in SCRAPER_REGISTRY.items():
        sources.append({
            "id": key,
            "name": entry["name"],
            "has_today": has_data(key),
        })
    return jsonify({"code": 0, "data": sources})


@app.route("/api/categories")
def api_categories():
    """获取分类列表"""
    source = request.args.get("source", "fanqie")
    scraper = get_scraper(source)
    if not scraper:
        return jsonify({"code": 1, "msg": f"不支持的数据源: {source}"})
    categories = scraper.get_categories()
    return jsonify({"code": 0, "data": categories})


@app.route("/api/scrape")
def api_scrape():
    """抓取排行榜（优先读缓存）"""
    source = request.args.get("source", "fanqie")
    gender = request.args.get("gender") or None
    period = request.args.get("period") or None
    sort_key = request.args.get("sort", "rank")
    force = request.args.get("force", "0") == "1"
    day = request.args.get("date") or today_str()

    from_storage = False

    # 优先读取已有数据
    if not force and has_data(source, day):
        data = load_data(source, day)
        from_storage = True
    else:
        data = _scrape_and_save(source, gender, period)

    # 筛选
    if from_storage:
        if gender:
            gender_name = {"male": "男频", "female": "女频"}.get(gender, gender)
            data = [d for d in data if d.get("gender") == gender_name]
        if period:
            data = [d for d in data if d.get("period") == period]

    # 排序（将 dict 转回 NovelRank 排序再转回）
    if sort_key and sort_key != "rank":
        novels = [NovelRank(**{k: v for k, v in d.items() if k != "author_url"}) for d in data]
        novels = apply_sort(novels, sort_key)
        data = [n.to_dict() for n in novels]

    return jsonify({
        "code": 0,
        "data": data,
        "total": len(data),
        "from_storage": from_storage,
        "date": day,
    })


@app.route("/api/scrape/all-sources")
def api_scrape_all_sources():
    """汇总所有数据源（优先读取已有数据）"""
    gender = request.args.get("gender") or None
    period = request.args.get("period") or None
    sort_key = request.args.get("sort", "rank")
    force = request.args.get("force", "0") == "1"
    day = request.args.get("date") or today_str()

    all_data = []
    any_stored = False

    for source_key, entry in SCRAPER_REGISTRY.items():
        if not force and has_data(source_key, day):
            data = load_data(source_key, day)
            any_stored = True
        else:
            try:
                data = _scrape_and_save(source_key, gender, period)
            except Exception as e:
                print(f"⚠ {entry['name']} 抓取失败: {e}")
                continue

        # 筛选
        if gender:
            gender_name = {"male": "男频", "female": "女频"}.get(gender, gender)
            data = [d for d in data if d.get("gender") == gender_name]
        if period:
            data = [d for d in data if d.get("period") == period]

        all_data.extend(data)

    # 排序
    if sort_key and sort_key != "rank":
        novels = [NovelRank(**{k: v for k, v in d.items() if k != "author_url"}) for d in all_data]
        novels = apply_sort(novels, sort_key)
        all_data = [n.to_dict() for n in novels]

    return jsonify({
        "code": 0,
        "data": all_data,
        "total": len(all_data),
        "from_storage": any_stored,
        "date": day,
    })


@app.route("/api/fetch-all", methods=["POST"])
def api_fetch_all():
    """一键全量抓取所有数据源并按天存储"""
    day = today_str()
    force = request.args.get("force", "0") == "1"
    results = {}
    errors = []

    for source_key, entry in SCRAPER_REGISTRY.items():
        # 如果不强制刷新且已有今日数据，跳过
        if not force and has_data(source_key, day):
            stored = load_data(source_key, day)
            results[source_key] = {
                "name": entry["name"],
                "count": len(stored),
                "from_storage": True,
            }
            continue

        try:
            data = _scrape_and_save(source_key)
            results[source_key] = {
                "name": entry["name"],
                "count": len(data),
                "from_storage": False,
            }
        except Exception as e:
            errors.append(f"{entry['name']}: {str(e)}")
            results[source_key] = {
                "name": entry["name"],
                "count": 0,
                "error": str(e),
            }

    total = sum(r["count"] for r in results.values())

    return jsonify({
        "code": 0,
        "data": results,
        "total": total,
        "date": day,
        "errors": errors,
    })


@app.route("/api/dashboard")
def api_dashboard():
    """市场分析汇总看板数据"""
    day = request.args.get("date") or today_str()

    # 收集所有数据源的数据
    all_novels = []
    source_stats = {}

    for source_key, entry in SCRAPER_REGISTRY.items():
        data = load_data(source_key, day) if has_data(source_key, day) else []
        source_stats[entry["name"]] = len(data)
        all_novels.extend(data)

    if not all_novels:
        return jsonify({
            "code": 0,
            "data": {
                "date": day,
                "total": 0,
                "source_stats": source_stats,
                "category_stats": {},
                "gender_stats": {},
                "period_stats": {},
                "cross_platform": [],
                "has_data": False,
            },
        })

    # 分类统计
    category_counter = Counter()
    gender_counter = Counter()
    period_counter = Counter()
    title_sources = {}  # title -> set of sources

    for novel in all_novels:
        cat = novel.get("category", "未分类")
        gender = novel.get("gender", "未知")
        period = novel.get("period", "未知")
        source = novel.get("source", "未知")
        title = novel.get("title", "")

        category_counter[cat] += 1
        gender_counter[gender] += 1
        period_counter[period] += 1

        if title:
            if title not in title_sources:
                title_sources[title] = {"sources": set(), "data": novel}
            title_sources[title]["sources"].add(source)

    # 跨平台热门书籍（出现在 2 个及以上平台的）
    cross_platform = []
    for title, info in title_sources.items():
        if len(info["sources"]) >= 2:
            cross_platform.append({
                "title": title,
                "author": info["data"].get("author", ""),
                "category": info["data"].get("category", ""),
                "sources": sorted(list(info["sources"])),
                "source_count": len(info["sources"]),
            })
    cross_platform.sort(key=lambda x: x["source_count"], reverse=True)

    # 热度 top 分类 (前15)
    top_categories = dict(category_counter.most_common(15))

    return jsonify({
        "code": 0,
        "data": {
            "date": day,
            "total": len(all_novels),
            "source_stats": source_stats,
            "category_stats": top_categories,
            "gender_stats": dict(gender_counter),
            "period_stats": dict(period_counter),
            "cross_platform": cross_platform[:20],
            "has_data": True,
        },
    })


@app.route("/api/dates")
def api_dates():
    """获取有历史数据的日期列表"""
    dates = list_dates()
    return jsonify({"code": 0, "data": dates})


@app.route("/api/feishu/push", methods=["POST"])
def api_feishu_push():
    """推送到飞书"""
    config = load_config()
    feishu_config = config.get("feishu", {})
    feishu = FeishuExporter(feishu_config)

    if not feishu.is_configured():
        return jsonify({"code": 1, "msg": "飞书凭证未配置"})

    body = request.get_json(force=True)
    novels_data = body.get("data", [])

    novels = []
    for d in novels_data:
        novels.append(NovelRank(
            rank=d.get("rank", 0),
            title=d.get("title", ""),
            author=d.get("author", ""),
            category=d.get("category", ""),
            gender=d.get("gender", ""),
            period=d.get("period", ""),
            latest_chapter=d.get("latest_chapter", ""),
            book_url=d.get("book_url", ""),
            source=d.get("source", ""),
        ))

    try:
        feishu.export(novels, clear_existing=body.get("clear", True))
        return jsonify({"code": 0, "msg": "推送成功"})
    except Exception as e:
        return jsonify({"code": 1, "msg": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
