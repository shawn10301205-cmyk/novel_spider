"""爬虫基类 - 定义所有爬虫的统一接口"""

from abc import ABC, abstractmethod
from typing import Optional
from models.novel import NovelRank


class BaseScraper(ABC):
    """爬虫抽象基类，所有站点爬虫需继承此类"""

    # 站点名称，子类必须定义
    SOURCE_NAME: str = ""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.delay = self.config.get("delay", 1)
        self.user_agent = self.config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    @abstractmethod
    def get_categories(self) -> list[dict]:
        """
        获取可用分类列表

        Returns:
            list[dict]: 每项包含 {id, name, gender, period} 等信息
        """
        pass

    @abstractmethod
    def scrape_rank(
        self,
        category_id: str,
        gender: str = "male",
        period: str = "read"
    ) -> list[NovelRank]:
        """
        抓取指定分类的排行榜

        Args:
            category_id: 分类 ID
            gender: 频道，"male" 或 "female"
            period: 榜单类型，"read"(阅读榜) 或 "new"(新书榜)

        Returns:
            list[NovelRank]: 排行榜数据列表
        """
        pass

    @abstractmethod
    def scrape_all(
        self,
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """
        抓取所有（或指定频道/榜单类型的全部）排行榜

        Args:
            gender: 可选，筛选频道
            period: 可选，筛选榜单类型

        Returns:
            list[NovelRank]: 合并的排行榜数据列表
        """
        pass

    def _get_headers(self) -> dict:
        """获取默认请求头"""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
