from .base import BaseScraper
from .fanqie import FanqieScraper
from .shuqi import ShuqiScraper
from .qimao import QimaoScraper
from .zongheng import ZonghengScraper

# 爬虫注册表 - 新增数据源只需在此添加
SCRAPER_REGISTRY = {
    "fanqie": {"class": FanqieScraper, "name": "番茄小说"},
    "shuqi": {"class": ShuqiScraper, "name": "书旗小说"},
    "qimao": {"class": QimaoScraper, "name": "七猫小说"},
    "zongheng": {"class": ZonghengScraper, "name": "纵横中文网"},
}

__all__ = [
    "BaseScraper",
    "FanqieScraper",
    "ShuqiScraper",
    "QimaoScraper",
    "ZonghengScraper",
    "SCRAPER_REGISTRY",
]
