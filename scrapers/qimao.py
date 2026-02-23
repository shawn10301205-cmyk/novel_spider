"""七猫小说排行榜爬虫"""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper
from models.novel import NovelRank


class QimaoScraper(BaseScraper):
    """
    七猫小说网爬虫

    抓取 https://www.qimao.com/paihang 页面
    支持男频/女频 × 5种榜单（大热榜/新书榜/完结榜/收藏榜/更新榜）
    """

    SOURCE_NAME = "七猫小说"
    BASE_URL = "https://www.qimao.com"

    # 频道
    GENDERS = {
        "boy": "男频",
        "girl": "女频",
    }
    GENDER_MAP = {"male": "boy", "female": "girl"}

    # 榜单类型
    RANK_TYPES = {
        "hot": "大热榜",
        "new": "新书榜",
        "over": "完结榜",
        "collect": "收藏榜",
        "update": "更新榜",
    }

    # period 参数映射
    PERIOD_MAP = {
        "read": "hot",    # 阅读 -> 大热
        "hot": "hot",
        "new": "new",
        "over": "over",
        "collect": "collect",
        "update": "update",
    }

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://www.qimao.com/",
        }

    def get_categories(self) -> list[dict]:
        """返回所有榜单作为分类"""
        categories = []
        for gender_key, gender_name in self.GENDERS.items():
            g = "male" if gender_key == "boy" else "female"
            for rank_key, rank_name in self.RANK_TYPES.items():
                categories.append({
                    "id": f"{gender_key}_{rank_key}",
                    "name": rank_name,
                    "gender": g,
                    "gender_name": gender_name,
                })
        return categories

    def _fetch_rank_page(self, gender_key: str, rank_key: str) -> list[NovelRank]:
        """抓取单个榜单页面"""
        url = f"{self.BASE_URL}/paihang/{gender_key}/{rank_key}/date/"
        gender_name = self.GENDERS.get(gender_key, gender_key)
        rank_name = self.RANK_TYPES.get(rank_key, rank_key)

        print(f"  正在抓取: {self.SOURCE_NAME} {gender_name} - {rank_name} ...")

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {url} - {e}")
            return []

        return self._parse_page(resp.text, gender_name, rank_name)

    def _parse_page(self, html: str, gender_name: str, rank_name: str) -> list[NovelRank]:
        """解析七猫排行榜页面"""
        soup = BeautifulSoup(html, "lxml")
        novels = []

        # 七猫页面: .rank-list > li 结构
        items = soup.select("li")
        rank_idx = 0

        for item in items:
            try:
                # 书名链接: a[href*="/shuku/"]
                title_link = item.select_one('a[href*="/shuku/"]')
                if not title_link:
                    continue

                title_el = title_link.select_one(".book-name") or title_link
                title = ""

                # 尝试多种选择器获取书名
                for sel in [".book-name", ".tit", "h3", "h4", ".name"]:
                    el = item.select_one(sel)
                    if el:
                        title = el.get_text(strip=True)
                        break

                if not title:
                    # 从链接文本获取
                    title = title_link.get_text(strip=True)
                    # 如果文本太长，可能包含了其他信息，跳过
                    if len(title) > 50:
                        continue

                if not title:
                    continue

                rank_idx += 1

                # 书籍链接
                href = title_link.get("href", "")
                book_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                # 作者
                author = ""
                author_link = item.select_one('a[href*="/zuozhe/"]')
                if author_link:
                    author = author_link.get_text(strip=True)

                # 分类
                category = ""
                cat_links = item.select('a[href*="/shuku/a-"]')
                for cl in cat_links:
                    cat_text = cl.get_text(strip=True)
                    if cat_text and cat_text != "都市":  # 取子分类
                        category = cat_text
                if not category:
                    for cl in cat_links:
                        cat_text = cl.get_text(strip=True)
                        if cat_text:
                            category = cat_text
                            break

                # 字数
                word_count = ""
                text_content = item.get_text()
                import re
                wc_match = re.search(r'([\d.]+万字)', text_content)
                if wc_match:
                    word_count = wc_match.group(1)

                # 热度
                heat = ""
                heat_match = re.search(r'([\d.]+\s*万?\s*热度)', text_content)
                if heat_match:
                    heat = heat_match.group(1).strip()

                novels.append(NovelRank(
                    rank=rank_idx,
                    title=title,
                    author=author,
                    category=category or rank_name,
                    gender=gender_name,
                    period=rank_name,
                    book_url=book_url,
                    source=self.SOURCE_NAME,
                    extra={"word_count": word_count, "heat": heat} if (word_count or heat) else {},
                ))

            except Exception as e:
                print(f"  ⚠ 解析条目失败: {e}")
                continue

        return novels

    def scrape_rank(
        self,
        category_id: str,
        gender: str = "male",
        period: str = "hot"
    ) -> list[NovelRank]:
        """抓取指定榜单"""
        gender_key = self.GENDER_MAP.get(gender, "boy")
        rank_key = self.PERIOD_MAP.get(period, period)
        return self._fetch_rank_page(gender_key, rank_key)

    def scrape_all(
        self,
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """抓取所有排行榜"""
        all_novels = []

        genders = [self.GENDER_MAP.get(gender, gender)] if gender else list(self.GENDERS.keys())
        rank_types = [self.PERIOD_MAP.get(period, period)] if period else list(self.RANK_TYPES.keys())

        for g in genders:
            for r in rank_types:
                novels = self._fetch_rank_page(g, r)
                all_novels.extend(novels)
                if self.delay > 0:
                    time.sleep(self.delay)

        return all_novels
