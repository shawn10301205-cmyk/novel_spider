from .base import BaseScraper
from .fanqie import FanqieScraper
from .shuqi import ShuqiScraper

# 爬虫注册表 - 新增数据源只需在此添加
SCRAPER_REGISTRY = {
    "fanqie": {"class": FanqieScraper, "name": "番茄小说"},
    "shuqi": {"class": ShuqiScraper, "name": "书旗小说"},
}

__all__ = ["BaseScraper", "FanqieScraper", "ShuqiScraper", "SCRAPER_REGISTRY"]
