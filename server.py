#!/usr/bin/env python3
"""Flask Web API 服务"""

import sys
import os
import threading
import datetime
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yaml

from scrapers import SCRAPER_REGISTRY
from sorter import apply_sort
from exporters.feishu import FeishuExporter
from exporters.webhook import FeishuWebhookNotifier
from storage import has_data, load_data, save_data, list_dates, today_str, latest_date, get_novel_trend, init_db
from models.novel import NovelRank
from downloader import FanqieDownloader

app = Flask(__name__, static_folder="web", static_url_path="")
CORS(app)

# ============================================================
# 定时调度器
# ============================================================
_scheduler_timer = None
_scheduler_lock = threading.Lock()
_last_sync_result = {"time": None, "status": None, "detail": None}


def _run_scheduled_sync():
    """定时同步任务：全量抓取所有数据源"""
    global _last_sync_result
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[sync] [{now}] scheduled sync started...")
    errors = []
    total = 0
    for source_key, entry in SCRAPER_REGISTRY.items():
        try:
            scraper = get_scraper(source_key)
            if scraper:
                novels = scraper.scrape_all()
                save_data(source_key, novels)
                count = len(novels)
                total += count
                print(f"  [ok] {entry['name']}: {count} records")
        except Exception as e:
            errors.append(f"{entry['name']}: {e}")
            print(f"  [err] {entry['name']}: {e}")

    _last_sync_result = {
        "time": now,
        "status": "success" if not errors else "partial",
        "total": total,
        "errors": errors,
    }
    print(f"[sync] [{now}] sync done, total {total} records")

    # 发送飞书群通知
    try:
        config = load_config()
        feishu_cfg = config.get("feishu", {})
        webhook_url = feishu_cfg.get("webhook_url", "")
        app_url = feishu_cfg.get("app_url", "")
        if webhook_url and total > 0:
            notifier = FeishuWebhookNotifier(webhook_url, app_url)
            day = today_str()
            results = {}
            for sk, ent in SCRAPER_REGISTRY.items():
                if has_data(sk, day):
                    data = load_data(sk, day)
                    results[sk] = {"name": ent["name"], "count": len(data), "from_storage": False}
                else:
                    results[sk] = {"name": ent["name"], "count": 0, "from_storage": False}
            notifier.send_scrape_report(results, total, day, errors)
    except Exception as e:
        print(f"  [warn] feishu notify failed: {e}")

    # 调度下一次
    _schedule_next()


def _schedule_next():
    """根据配置计算下次执行时间并设置定时器"""
    global _scheduler_timer
    config = load_config()
    sync_time = config.get("schedule", {}).get("sync_time", "")
    enabled = config.get("schedule", {}).get("enabled", False)

    with _scheduler_lock:
        if _scheduler_timer:
            _scheduler_timer.cancel()
            _scheduler_timer = None

        if not enabled or not sync_time:
            return

        try:
            hour, minute = map(int, sync_time.split(":"))
        except (ValueError, AttributeError):
            return

        now = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)

        delay = (target - now).total_seconds()
        print(f"[schedule] 下次同步时间: {target.strftime('%Y-%m-%d %H:%M')} (约 {delay/3600:.1f} 小时后)")

        _scheduler_timer = threading.Timer(delay, _run_scheduled_sync)
        _scheduler_timer.daemon = True
        _scheduler_timer.start()


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 中的值覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.yaml")
    local_path = os.path.join(base_dir, "config.local.yaml")

    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # 合并本地配置（敏感信息），local 覆盖 base
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            local_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, local_config)

    return config


def save_config(config: dict):
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


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
    """排行榜数据（只读缓存，不自动抓取）"""
    source = request.args.get("source", "fanqie")
    gender = request.args.get("gender") or None
    period = request.args.get("period") or None
    sort_key = request.args.get("sort", "rank")
    force = request.args.get("force", "0") == "1"
    day = request.args.get("date") or None

    from_storage = False

    if force:
        # 强制抓取
        data = _scrape_and_save(source, gender, period)
        day = day or today_str()
    else:
        # 只读缓存，回退到最近有数据的日期
        if day is None:
            day = latest_date()
        if has_data(source, day):
            data = load_data(source, day)
            from_storage = True
        else:
            return jsonify({
                "code": 0,
                "data": [],
                "total": 0,
                "from_storage": False,
                "date": day,
                "msg": "暂无数据，请先拉取",
            })

    # 筛选
    if from_storage:
        if gender:
            gender_name = {"male": "男频", "female": "女频"}.get(gender, gender)
            data = [d for d in data if d.get("gender") == gender_name]
        if period:
            data = [d for d in data if d.get("period") == period]

    # 排序
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
    """汇总所有数据源（只读缓存，不自动抓取）"""
    gender = request.args.get("gender") or None
    period = request.args.get("period") or None
    sort_key = request.args.get("sort", "rank")
    force = request.args.get("force", "0") == "1"
    day = request.args.get("date") or None

    all_data = []
    any_stored = False

    if force:
        day = day or today_str()
        for source_key, entry in SCRAPER_REGISTRY.items():
            try:
                data = _scrape_and_save(source_key, gender, period)
                all_data.extend(data)
            except Exception as e:
                print(f"[warn] {entry['name']} scrape failed: {e}")
    else:
        # 只读缓存
        if day is None:
            day = latest_date()
        for source_key, entry in SCRAPER_REGISTRY.items():
            if has_data(source_key, day):
                data = load_data(source_key, day)
                any_stored = True
            else:
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
    day = request.args.get("date") or latest_date()

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
                "book_url": info["data"].get("book_url", ""),
                "sources": sorted(list(info["sources"])),
                "source_count": len(info["sources"]),
            })
    cross_platform.sort(key=lambda x: x["source_count"], reverse=True)

    # 热度 top 分类 (前15)
    top_categories = dict(category_counter.most_common(15))

    # --- 在读/热度排行 (男频/女频分开) ---
    import re
    def parse_heat(novel):
        extra = novel.get("extra", {})
        heat_str = extra.get("heat", "")
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

    heat_male = []
    heat_female = []
    for novel in all_novels:
        hv = parse_heat(novel)
        if hv <= 0:
            continue
        item = {
            "title": novel.get("title", ""),
            "author": novel.get("author", ""),
            "heat": novel.get("extra", {}).get("heat", ""),
            "word_count": novel.get("extra", {}).get("word_count", ""),
            "source": novel.get("source", ""),
            "book_url": novel.get("book_url", ""),
            "category": novel.get("category", ""),
            "_hv": hv,
        }
        gender = novel.get("gender", "")
        if gender == "男频":
            heat_male.append(item)
        elif gender == "女频":
            heat_female.append(item)

    heat_male.sort(key=lambda x: x["_hv"], reverse=True)
    heat_female.sort(key=lambda x: x["_hv"], reverse=True)
    # 去掉内部排序字段
    for lst in (heat_male, heat_female):
        for item in lst:
            item.pop("_hv", None)

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
            "heat_rank_male": heat_male[:30],
            "heat_rank_female": heat_female[:30],
            "has_data": True,
        },
    })


@app.route("/api/dates")
def api_dates():
    """获取有历史数据的日期列表"""
    dates = list_dates()
    return jsonify({"code": 0, "data": dates})


@app.route("/api/category-books")
def api_category_books():
    """获取指定分类的所有书籍详情，按热度排序"""
    import re

    category = request.args.get("category", "")
    day = request.args.get("date") or latest_date()
    sort_by = request.args.get("sort", "heat")  # heat | rank
    limit = request.args.get("limit", type=int)  # 可选限制条数

    if not category:
        return jsonify({"code": 1, "msg": "缺少 category 参数"})

    def _parse_heat(extra):
        heat_str = extra.get("heat", "")
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

    all_books = []
    for source_key, entry in SCRAPER_REGISTRY.items():
        if not has_data(source_key, day):
            continue
        data = load_data(source_key, day)
        for novel in data:
            if novel.get("category") == category:
                extra = novel.get("extra", {})
                all_books.append({
                    "title": novel.get("title", ""),
                    "author": novel.get("author", ""),
                    "category": novel.get("category", ""),
                    "gender": novel.get("gender", ""),
                    "period": novel.get("period", ""),
                    "source": novel.get("source", ""),
                    "book_url": novel.get("book_url", ""),
                    "rank": novel.get("rank", 0),
                    "latest_chapter": novel.get("latest_chapter", ""),
                    "extra": extra,
                    "heat_value": _parse_heat(extra),
                })

    # 按热度降序排列
    if sort_by == "heat":
        all_books.sort(key=lambda x: x["heat_value"], reverse=True)
    else:
        all_books.sort(key=lambda x: x["rank"])

    total = len(all_books)
    if limit and limit > 0:
        all_books = all_books[:limit]

    return jsonify({
        "code": 0,
        "data": all_books,
        "total": total,
        "returned": len(all_books),
        "category": category,
        "date": day,
    })


@app.route("/api/category-rank")
def api_category_rank():
    """分类排行：按各分类在读前10热度值累加倒排"""
    import re
    from collections import defaultdict

    day = request.args.get("date") or latest_date()

    def _parse_heat(extra):
        heat_str = extra.get("heat", "")
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

    # 收集全部数据
    all_novels = []
    for source_key, entry in SCRAPER_REGISTRY.items():
        if has_data(source_key, day):
            all_novels.extend(load_data(source_key, day))

    if not all_novels:
        return jsonify({"code": 0, "data": [], "date": day})

    # 按分类归组，每个分类收集所有热度值
    cat_books = defaultdict(list)
    for novel in all_novels:
        cat = novel.get("category", "未分类")
        hv = _parse_heat(novel.get("extra", {}))
        cat_books[cat].append({
            "title": novel.get("title", ""),
            "author": novel.get("author", ""),
            "heat": novel.get("extra", {}).get("heat", ""),
            "heat_value": hv,
            "source": novel.get("source", ""),
            "gender": novel.get("gender", ""),
            "book_url": novel.get("book_url", ""),
        })

    # 每个分类取热度前10累加
    category_rank = []
    for cat, books in cat_books.items():
        books.sort(key=lambda x: x["heat_value"], reverse=True)
        top10 = books[:10]
        total_heat = sum(b["heat_value"] for b in top10)
        category_rank.append({
            "category": cat,
            "total_heat": total_heat,
            "book_count": len(books),
            "top10_count": len(top10),
            "top10": top10,
        })

    # 按累加热度倒排
    category_rank.sort(key=lambda x: x["total_heat"], reverse=True)

    return jsonify({
        "code": 0,
        "data": category_rank,
        "total": len(category_rank),
        "date": day,
    })


@app.route("/api/novel/trend")
def api_novel_trend():
    """查询某本小说历史热度趋势"""
    title = request.args.get("title", "").strip()
    source = request.args.get("source") or None
    limit = request.args.get("limit", 30, type=int)

    if not title:
        return jsonify({"code": 1, "msg": "缺少 title 参数"})

    data = get_novel_trend(title, source=source, limit=limit)
    return jsonify({
        "code": 0,
        "data": data,
        "title": title,
        "total": len(data),
    })


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


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    """获取设置"""
    config = load_config()
    schedule = config.get("schedule", {})
    return jsonify({
        "code": 0,
        "data": {
            "sync_time": schedule.get("sync_time", ""),
            "enabled": schedule.get("enabled", False),
            "last_sync": _last_sync_result,
        },
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    """保存设置"""
    body = request.get_json(force=True)
    config = load_config()

    if "schedule" not in config:
        config["schedule"] = {}

    sync_time = body.get("sync_time", "").strip()
    enabled = body.get("enabled", False)

    # 校验时间格式
    if sync_time:
        try:
            h, m = map(int, sync_time.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            sync_time = f"{h:02d}:{m:02d}"
        except (ValueError, AttributeError):
            return jsonify({"code": 1, "msg": "时间格式错误，请使用 HH:MM"})

    config["schedule"]["sync_time"] = sync_time
    config["schedule"]["enabled"] = bool(enabled)
    save_config(config)

    # 重新调度
    _schedule_next()

    return jsonify({
        "code": 0,
        "msg": "设置已保存",
        "data": {
            "sync_time": sync_time,
            "enabled": enabled,
        },
    })


@app.route("/api/notify", methods=["POST"])
def api_notify():
    """手动发送飞书群通知"""
    config = load_config()
    feishu_cfg = config.get("feishu", {})
    webhook_url = feishu_cfg.get("webhook_url", "")
    app_url = feishu_cfg.get("app_url", "")

    if not webhook_url:
        return jsonify({"code": 1, "msg": "Webhook URL 未配置"})

    notifier = FeishuWebhookNotifier(webhook_url, app_url)

    day = today_str()
    results = {}
    for source_key, entry in SCRAPER_REGISTRY.items():
        if has_data(source_key, day):
            data = load_data(source_key, day)
            results[source_key] = {"name": entry["name"], "count": len(data), "from_storage": True}
        else:
            results[source_key] = {"name": entry["name"], "count": 0, "from_storage": False}

    total = sum(r["count"] for r in results.values())
    ok = notifier.send_scrape_report(results, total, day)

    if ok:
        return jsonify({"code": 0, "msg": "通知发送成功"})
    else:
        return jsonify({"code": 1, "msg": "通知发送失败"})


# ============================================================
# 下载相关 API（通过 Tomato-Novel-Downloader 代理）
# ============================================================

def _get_downloader():
    config = load_config()
    return FanqieDownloader(config.get("download", {}))


@app.route("/api/tomato/check")
def api_tomato_check():
    """检查 Tomato 服务状态"""
    dl = _get_downloader()
    status = dl.check_tomato()
    return jsonify({"code": 0, "data": status})


@app.route("/api/book/info")
def api_book_info():
    """获取书籍详情"""
    book_id = request.args.get("book_id", "").strip()
    if not book_id:
        return jsonify({"code": 1, "msg": "缺少 book_id 参数"})

    dl = _get_downloader()
    info = dl.get_book_info(book_id)

    if not info:
        return jsonify({"code": 1, "msg": "获取书籍信息失败"})

    return jsonify({"code": 0, "data": info.to_dict()})


@app.route("/api/book/search")
def api_book_search():
    """搜索小说"""
    keyword = request.args.get("q", "").strip()
    if not keyword:
        return jsonify({"code": 1, "msg": "缺少搜索关键词"})

    dl = _get_downloader()
    results = dl.search_books(keyword)
    return jsonify({"code": 0, "data": results, "total": len(results)})


@app.route("/api/book/chapters")
def api_book_chapters():
    """获取书籍章节列表"""
    book_id = request.args.get("book_id", "").strip()
    if not book_id:
        return jsonify({"code": 1, "msg": "缺少 book_id 参数"})

    dl = _get_downloader()
    chapters = dl.get_chapter_list(book_id)

    return jsonify({
        "code": 0,
        "data": [ch.to_dict() for ch in chapters],
        "total": len(chapters),
    })


@app.route("/api/book/download", methods=["POST"])
def api_book_download():
    """提交下载任务到 Tomato 服务"""
    body = request.get_json(force=True)
    book_id = body.get("book_id", "").strip()
    if not book_id:
        return jsonify({"code": 1, "msg": "缺少 book_id 参数"})

    dl = _get_downloader()
    result = dl.start_download(book_id)

    if result["success"]:
        return jsonify({"code": 0, "data": result})
    else:
        return jsonify({"code": 1, "msg": result["error"]})


@app.route("/api/book/download/status")
def api_book_download_status():
    """查询下载进度"""
    book_id = request.args.get("book_id", "").strip() or None

    dl = _get_downloader()
    jobs = dl.get_download_status(book_id)

    return jsonify({
        "code": 0,
        "data": [j.to_dict() for j in jobs],
        "total": len(jobs),
    })


@app.route("/api/book/download/cancel", methods=["POST"])
def api_book_download_cancel():
    """取消下载任务"""
    body = request.get_json(force=True)
    job_id = body.get("job_id")
    if not job_id:
        return jsonify({"code": 1, "msg": "缺少 job_id 参数"})

    dl = _get_downloader()
    ok = dl.cancel_download(int(job_id))
    if ok:
        return jsonify({"code": 0, "msg": "已取消"})
    else:
        return jsonify({"code": 1, "msg": "取消失败"})


@app.route("/api/book/library")
def api_book_library():
    """获取已下载的书库"""
    dl = _get_downloader()
    items = dl.get_library()
    return jsonify({"code": 0, "data": items, "total": len(items)})


if __name__ == "__main__":
    # 初始化数据库 & 启动时自动调度
    init_db()
    _schedule_next()
    app.run(host="0.0.0.0", port=8081, debug=True)
