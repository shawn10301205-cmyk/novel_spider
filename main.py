#!/usr/bin/env python3
"""
番茄小说排行榜爬虫 - 命令行入口

用法:
    python main.py scrape                           # 抓取默认分类并在控制台展示
    python main.py scrape --gender male             # 只抓取男频
    python main.py scrape --period read             # 只抓取阅读榜
    python main.py scrape --category 都市日常,玄幻    # 指定分类
    python main.py scrape --export feishu           # 推送到飞书
    python main.py scrape --sort category           # 按分类排序
    python main.py scrape --group category          # 按分类分组展示
    python main.py download 7143038691944959011     # 下载指定小说
    python main.py download 7143038691944959011 --info-only   # 只查看信息
    python main.py categories                       # 列出所有可用分类
    python main.py feishu-fields                    # 显示飞书表格所需字段
"""

import argparse
import sys
import os

import yaml

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.fanqie import FanqieScraper
from exporters.console import ConsoleExporter
from exporters.feishu import FeishuExporter
from sorter import apply_sort, filter_by_gender, filter_by_category, filter_by_period
from downloader import FanqieDownloader


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
    """加载配置文件，支持 config.local.yaml 覆盖敏感信息"""
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


def get_scraper(source: str, config: dict):
    """根据来源获取爬虫实例"""
    scraper_map = {
        "fanqie": FanqieScraper,
        # 后续在此添加更多爬虫
    }

    scraper_cls = scraper_map.get(source)
    if not scraper_cls:
        print(f"❌ 不支持的来源: {source}")
        print(f"   支持的来源: {', '.join(scraper_map.keys())}")
        sys.exit(1)

    return scraper_cls(config.get("scrape", {}))


def cmd_scrape(args, config):
    """执行抓取命令"""
    source = args.source or config.get("scrape", {}).get("default_source", "fanqie")
    scraper = get_scraper(source, config)

    print(f"🕷 开始抓取 [{scraper.SOURCE_NAME}] 排行榜...")
    print()

    # 抓取数据
    if args.category:
        # 指定分类
        category_names = [c.strip() for c in args.category.split(",")]
        novels = scraper.scrape_categories(
            category_names,
            gender=args.gender,
            period=args.period
        )
    else:
        novels = scraper.scrape_all(
            gender=args.gender,
            period=args.period
        )

    if not novels:
        print("⚠ 未抓取到任何数据")
        return

    print(f"\n✅ 共抓取到 {len(novels)} 条数据")

    # 排序
    if args.sort:
        novels = apply_sort(novels, args.sort)

    # 控制台输出
    console_exporter = ConsoleExporter()
    console_exporter.export(novels, group_by=args.group or "none")

    # 飞书推送
    if args.export == "feishu":
        feishu_config = config.get("feishu", {})
        feishu = FeishuExporter(feishu_config)
        feishu.export(novels, clear_existing=not args.append)


def cmd_categories(args, config):
    """列出可用分类"""
    source = args.source or config.get("scrape", {}).get("default_source", "fanqie")
    scraper = get_scraper(source, config)

    categories = scraper.get_categories()

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"📋 {scraper.SOURCE_NAME} 可用分类", show_lines=True)
    table.add_column("分类名", style="bold white")
    table.add_column("频道", style="cyan")
    table.add_column("分类ID", style="dim")

    for cat in categories:
        table.add_row(cat["name"], cat["gender_name"], cat["id"])

    console.print(table)


def cmd_feishu_fields(args, config):
    """显示飞书表格所需字段"""
    feishu_config = config.get("feishu", {})
    feishu = FeishuExporter(feishu_config)
    feishu.create_table_if_needed()


def cmd_download(args, config):
    """下载小说"""
    dl_config = config.get("download", {})
    dl = FanqieDownloader(dl_config)

    if args.info_only:
        info = dl.get_book_info(args.book_id)
        if info:
            print(f"书名: {info.title}")
            print(f"作者: {info.author}")
            print(f"简介: {info.description[:200]}")
            print(f"标签: {', '.join(info.tags)}")
            print(f"章节数: {info.chapter_count}")
            print(f"完结: {info.finished}")
        else:
            print("❌ 获取书籍信息失败")
    elif args.chapters_only:
        chapters = dl.get_chapter_list(args.book_id)
        print(f"共 {len(chapters)} 章:")
        for i, ch in enumerate(chapters[:30], 1):
            vol = f" [{ch.volume}]" if ch.volume else ""
            print(f"  {i}. {ch.title}{vol}")
        if len(chapters) > 30:
            print(f"  ... (还有 {len(chapters) - 30} 章)")
    else:
        result = dl.download_book(args.book_id)
        if result:
            print(f"\n✅ 下载完成: {result}")
        else:
            print("\n❌ 下载失败")


def main():
    parser = argparse.ArgumentParser(
        description="📚 小说排行榜爬虫 - 抓取、排序、推送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py scrape                             抓取所有排行榜
  python main.py scrape --gender male --period read 抓取男频阅读榜
  python main.py scrape --category 都市日常          指定分类
  python main.py scrape --export feishu             推送到飞书
  python main.py scrape --sort category --group category  按分类排序和分组
  python main.py categories                         列出所有分类
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scrape 命令
    scrape_parser = subparsers.add_parser("scrape", help="抓取排行榜数据")
    scrape_parser.add_argument(
        "--source", type=str, default=None,
        help="数据来源 (默认: fanqie)"
    )
    scrape_parser.add_argument(
        "--gender", type=str, choices=["male", "female"], default=None,
        help="频道筛选: male(男频) / female(女频)"
    )
    scrape_parser.add_argument(
        "--period", type=str, choices=["read", "new"], default=None,
        help="榜单类型: read(阅读榜) / new(新书榜)"
    )
    scrape_parser.add_argument(
        "--category", type=str, default=None,
        help="分类名称，多个用逗号分隔 (如: 都市日常,玄幻)"
    )
    scrape_parser.add_argument(
        "--sort", type=str, choices=["rank", "category", "gender", "period"],
        default=None, help="排序方式"
    )
    scrape_parser.add_argument(
        "--group", type=str, choices=["none", "category", "gender"],
        default=None, help="分组展示方式"
    )
    scrape_parser.add_argument(
        "--export", type=str, choices=["feishu"], default=None,
        help="导出目标"
    )
    scrape_parser.add_argument(
        "--append", action="store_true", default=False,
        help="追加模式（不清除飞书已有数据）"
    )

    # categories 命令
    cat_parser = subparsers.add_parser("categories", help="列出可用分类")
    cat_parser.add_argument(
        "--source", type=str, default=None,
        help="数据来源 (默认: fanqie)"
    )

    # feishu-fields 命令
    subparsers.add_parser("feishu-fields", help="显示飞书表格所需字段")

    # download 命令
    dl_parser = subparsers.add_parser("download", help="下载小说")
    dl_parser.add_argument(
        "book_id", type=str,
        help="书籍 ID (从 fanqienovel.com/page/xxx 中获取)"
    )
    dl_parser.add_argument(
        "--info-only", action="store_true",
        help="只显示书籍信息，不下载"
    )
    dl_parser.add_argument(
        "--chapters-only", action="store_true",
        help="只显示章节列表，不下载"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = load_config()

    if args.command == "scrape":
        cmd_scrape(args, config)
    elif args.command == "categories":
        cmd_categories(args, config)
    elif args.command == "feishu-fields":
        cmd_feishu_fields(args, config)
    elif args.command == "download":
        cmd_download(args, config)


if __name__ == "__main__":
    main()
