#!/usr/bin/env python3
"""Flask Web API 服务"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yaml

from scrapers.fanqie import FanqieScraper
from sorter import apply_sort, filter_by_gender, filter_by_category, filter_by_period
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
    scrapers = {"fanqie": FanqieScraper}
    cls = scrapers.get(source, FanqieScraper)
    return cls(config.get("scrape", {}))


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/api/categories")
def api_categories():
    """获取分类列表"""
    source = request.args.get("source", "fanqie")
    scraper = get_scraper(source)
    categories = scraper.get_categories()
    return jsonify({"code": 0, "data": categories})


@app.route("/api/scrape")
def api_scrape():
    """抓取排行榜"""
    source = request.args.get("source", "fanqie")
    gender = request.args.get("gender")  # male / female / None
    period = request.args.get("period")  # read / new / None
    category = request.args.get("category")  # 分类名，逗号分隔
    sort_key = request.args.get("sort", "rank")

    scraper = get_scraper(source)

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


@app.route("/api/scrape/single")
def api_scrape_single():
    """抓取单个分类的排行榜"""
    source = request.args.get("source", "fanqie")
    gender = request.args.get("gender", "male")
    period = request.args.get("period", "read")
    category_id = request.args.get("category_id", "")

    if not category_id:
        return jsonify({"code": 1, "msg": "缺少 category_id 参数"})

    scraper = get_scraper(source)
    novels = scraper.scrape_rank(category_id, gender, period)
    data = [n.to_dict() for n in novels]
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
