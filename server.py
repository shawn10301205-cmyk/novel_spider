#!/usr/bin/env python3
"""Flask Web API 服务"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yaml

from scrapers import SCRAPER_REGISTRY
from sorter import apply_sort
from exporters.feishu import FeishuExporter

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


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/api/sources")
def api_sources():
    """获取所有可用数据源"""
    sources = []
    for key, entry in SCRAPER_REGISTRY.items():
        sources.append({"id": key, "name": entry["name"]})
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
    """抓取排行榜"""
    source = request.args.get("source", "fanqie")
    gender = request.args.get("gender") or None
    period = request.args.get("period") or None
    category = request.args.get("category") or None
    sort_key = request.args.get("sort", "rank")

    scraper = get_scraper(source)
    if not scraper:
        return jsonify({"code": 1, "msg": f"不支持的数据源: {source}"})

    if category:
        category_names = [c.strip() for c in category.split(",")]
        novels = scraper.scrape_categories(
            category_names, gender=gender, period=period
        )
    else:
        novels = scraper.scrape_all(gender=gender, period=period)

    if sort_key:
        novels = apply_sort(novels, sort_key)

    data = [n.to_dict() for n in novels]
    return jsonify({"code": 0, "data": data, "total": len(data)})


@app.route("/api/scrape/all-sources")
def api_scrape_all_sources():
    """抓取所有数据源（汇总模式）"""
    gender = request.args.get("gender") or None
    period = request.args.get("period") or None
    sort_key = request.args.get("sort", "rank")

    config = load_config()
    all_novels = []

    for source_key, entry in SCRAPER_REGISTRY.items():
        try:
            scraper = entry["class"](config.get("scrape", {}))
            novels = scraper.scrape_all(gender=gender, period=period)
            all_novels.extend(novels)
        except Exception as e:
            print(f"⚠ {entry['name']} 抓取失败: {e}")

    if sort_key:
        all_novels = apply_sort(all_novels, sort_key)

    data = [n.to_dict() for n in all_novels]
    return jsonify({"code": 0, "data": data, "total": len(data)})


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

    from models.novel import NovelRank
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
