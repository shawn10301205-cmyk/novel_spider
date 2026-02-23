"""书旗小说排行榜爬虫"""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper
from models.novel import NovelRank


class ShuqiScraper(BaseScraper):
    """
    书旗小说网爬虫

    抓取 https://www.shuqi.com/rank 页面
    该页面包含 17 个榜单区块，每个区块 10 本书
    """

    SOURCE_NAME = "书旗小说"
    BASE_URL = "https://www.shuqi.com"
    RANK_URL = "https://www.shuqi.com/rank"

    # rank key -> (gender, period 中文名)
    RANK_META = {
        "boyClick":    ("男频", "点击榜"),
        "girlClick":   ("女频", "点击榜"),
        "boyStore":    ("男频", "收藏榜"),
        "girlStore":   ("女频", "收藏榜"),
        "boyOrder":    ("男频", "订阅榜"),
        "girlOrder":   ("女频", "订阅榜"),
        "boyhot":      ("男频", "人气榜"),
        "girlhot":     ("女频", "人气榜"),
        "boyEnd":      ("男频", "完结榜"),
        "girlEnd":     ("女频", "完结榜"),
        "boyNew":      ("男频", "新书榜"),
        "girlNew":     ("女频", "新书榜"),
    }

    GENDER_MAP = {"male": "男频", "female": "女频"}
    PERIOD_MAP = {
        "click": "点击榜", "read": "点击榜",
        "store": "收藏榜",
        "order": "订阅榜",
        "hot": "人气榜",
        "end": "完结榜",
        "new": "新书榜",
    }

    def get_categories(self) -> list[dict]:
        """返回榜单列表作为分类"""
        categories = []
        seen = set()
        for rank_key, (gender_name, period_name) in self.RANK_META.items():
            gender_key = "male" if gender_name == "男频" else "female"
            if period_name not in seen:
                seen.add(period_name)
            categories.append({
                "id": rank_key,
                "name": period_name,
                "gender": gender_key,
                "gender_name": gender_name,
            })
        return categories

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

    def _fetch_all_sections(self) -> dict:
        """
        一次请求抓取 /rank 页面，解析所有区块

        Returns:
            dict: {rank_key: list[NovelRank]}
        """
        print(f"  正在抓取: {self.SOURCE_NAME} 总榜页 ...")

        try:
            resp = requests.get(self.RANK_URL, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {self.RANK_URL} - {e}")
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        sections = soup.select("div.comp-ranks-2")

        result = {}

        for sec in sections:
            # 从 "查看更多" 链接提取 rank key
            more_link = sec.select_one('a[href*="/ranklist?rank="]')
            if not more_link:
                continue

            href = more_link.get("href", "")
            rank_key = href.split("rank=")[-1] if "rank=" in href else ""
            if not rank_key or rank_key not in self.RANK_META:
                continue

            gender_name, period_name = self.RANK_META[rank_key]

            # 解析书籍列表
            novels = []
            book_links = sec.select('ul.cp-ranks-list a[href*="/book/"]')

            for link in book_links:
                no_el = link.select_one("i.no")
                bn_el = link.select_one("span.bn")
                au_el = link.select_one("span.au")

                if not bn_el:
                    continue

                rank_num = 0
                if no_el:
                    try:
                        rank_num = int(no_el.get_text(strip=True))
                    except ValueError:
                        rank_num = len(novels) + 1
                else:
                    rank_num = len(novels) + 1

                title = bn_el.get_text(strip=True)
                author = au_el.get_text(strip=True) if au_el else ""
                book_href = link.get("href", "")
                book_url = book_href if book_href.startswith("http") else f"{self.BASE_URL}{book_href}"

                if title:
                    novels.append(NovelRank(
                        rank=rank_num,
                        title=title,
                        author=author,
                        category=period_name,
                        gender=gender_name,
                        period=period_name,
                        book_url=book_url,
                        source=self.SOURCE_NAME,
                    ))

            result[rank_key] = novels

        return result

    def scrape_rank(
        self,
        category_id: str,
        gender: str = "male",
        period: str = "click"
    ) -> list[NovelRank]:
        """抓取指定榜单"""
        all_sections = self._fetch_all_sections()

        # 匹配 gender + period 对应的 rank key
        gender_name = self.GENDER_MAP.get(gender, gender)
        period_name = self.PERIOD_MAP.get(period, period)

        for rank_key, (gn, pn) in self.RANK_META.items():
            if gn == gender_name and pn == period_name:
                return all_sections.get(rank_key, [])

        return []

    def scrape_all(
        self,
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """抓取所有排行榜（一次请求获取全部数据）"""
        all_sections = self._fetch_all_sections()
        all_novels = []

        gender_filter = self.GENDER_MAP.get(gender) if gender else None
        period_filter = self.PERIOD_MAP.get(period) if period else None

        for rank_key, novels in all_sections.items():
            if rank_key not in self.RANK_META:
                continue

            gn, pn = self.RANK_META[rank_key]

            if gender_filter and gn != gender_filter:
                continue
            if period_filter and pn != period_filter:
                continue

            all_novels.extend(novels)

        return all_novels

    def scrape_categories(
        self,
        category_names: list[str],
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """按榜单名称抓取"""
        all_sections = self._fetch_all_sections()
        all_novels = []

        gender_filter = self.GENDER_MAP.get(gender) if gender else None

        for rank_key, novels in all_sections.items():
            if rank_key not in self.RANK_META:
                continue

            gn, pn = self.RANK_META[rank_key]

            if gender_filter and gn != gender_filter:
                continue
            if pn not in category_names and rank_key not in category_names:
                continue

            all_novels.extend(novels)

        return all_novels
