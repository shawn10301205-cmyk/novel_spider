"""纵横中文网排行榜爬虫"""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper
from models.novel import NovelRank


class ZonghengScraper(BaseScraper):
    """
    纵横中文网爬虫

    抓取 https://www.zongheng.com/rank 排行榜页面
    支持人气榜/月票榜/新书榜/点击榜/推荐榜/完结榜等
    """

    SOURCE_NAME = "纵横中文网"
    BASE_URL = "https://www.zongheng.com"
    RANK_URL = "https://www.zongheng.com/rank"

    # 榜单类型: rankType -> (中文名, nav参数)
    RANK_TYPES = {
        "1": ("月票榜", "monthly-ticket"),
        "3": ("24小时畅销榜", "one-day"),
        "4": ("新书榜", "new-book"),
        "5": ("点击榜", "click"),
        "6": ("推荐榜", "recommend"),
        "8": ("完结榜", "end"),
    }

    # period 参数映射
    PERIOD_MAP = {
        "read": "5",       # 阅读 -> 点击榜
        "hot": "default",  # 默认人气
        "new": "4",        # 新书榜
        "end": "8",        # 完结
        "click": "5",
        "monthly": "1",
        "recommend": "6",
    }

    GENDER_MAP = {"male": "男频", "female": "女频"}

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://www.zongheng.com/",
        }

    def get_categories(self) -> list[dict]:
        """返回榜单类型列表"""
        categories = [
            {"id": "default", "name": "人气榜", "gender": "male", "gender_name": "全部"},
        ]
        for rank_id, (name, nav) in self.RANK_TYPES.items():
            categories.append({
                "id": rank_id,
                "name": name,
                "gender": "male",
                "gender_name": "全部",
            })
        return categories

    def _fetch_rank(self, nav: str = "default", rank_type: str = "") -> list[NovelRank]:
        """抓取指定榜单页面"""
        params = {"nav": nav}
        if rank_type:
            params["rankType"] = rank_type

        rank_name = "人气榜"
        if rank_type and rank_type in self.RANK_TYPES:
            rank_name = self.RANK_TYPES[rank_type][0]

        print(f"  正在抓取: {self.SOURCE_NAME} {rank_name} ...")

        try:
            resp = requests.get(
                self.RANK_URL,
                params=params,
                headers=self._get_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {self.RANK_URL} - {e}")
            return []

        return self._parse_page(resp.text, rank_name)

    def _parse_page(self, html: str, rank_name: str) -> list[NovelRank]:
        """解析纵横排行榜页面"""
        import re
        soup = BeautifulSoup(html, "lxml")
        novels = []

        rank_idx = 0
        book_links = soup.select('a[href*="/detail/"]')

        seen_titles = set()
        for link in book_links:
            title = link.get_text(strip=True)
            if not title or len(title) < 2 or len(title) > 50:
                continue

            href = link.get("href", "")
            if "/detail/" not in href:
                continue

            if title in seen_titles:
                continue
            seen_titles.add(title)

            rank_idx += 1
            book_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

            # 从父级 zh-modules-rank-book 获取详细数据
            author = ""
            extra = {}
            book_module = link.find_parent(class_="zh-modules-rank-book")
            if book_module:
                # 作者
                author_link = book_module.select_one('a[href*="/show/userInfo/"]')
                if author_link:
                    author = author_link.get_text(strip=True)

                # 右侧数据栏: "作者|15938|月票" 或 "作者|387.9|万字"
                right_slot = book_module.select_one('.rank-content-default__right-slot')
                if right_slot:
                    slot_text = right_slot.get_text(strip=True)
                    # 提取数值 + 单位
                    m = re.search(r'([\d.]+)\s*(万字|月票|人气|点击|推荐票)', slot_text)
                    if m:
                        val, unit = m.group(1), m.group(2)
                        if unit == '万字':
                            extra['word_count'] = f"{val}万字"
                        else:
                            extra['heat'] = f"{val}{unit}"

            if not author:
                parent = link.parent
                if parent:
                    author_link = parent.select_one('a[href*="/show/userInfo/"]')
                    if author_link:
                        author = author_link.get_text(strip=True)
                    if not author:
                        grandparent = parent.parent
                        if grandparent:
                            author_link = grandparent.select_one('a[href*="/show/userInfo/"]')
                            if author_link:
                                author = author_link.get_text(strip=True)

            novels.append(NovelRank(
                rank=rank_idx,
                title=title,
                author=author,
                category=rank_name,
                gender="全部",
                period=rank_name,
                book_url=book_url,
                source=self.SOURCE_NAME,
                extra=extra,
            ))

        return novels

    def _fetch_main_page(self) -> dict[str, list[NovelRank]]:
        """
        抓取主页面，解析出所有区块的数据

        Returns:
            dict: {rank_name: list[NovelRank]}
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
        result = {}

        # 在主页面上解析不同的区块
        # 纵横主排行页面有多个区块: 人气榜/月票榜/新书榜
        # 先从默认页面抓取人气榜的数据
        novels = self._parse_page(resp.text, "人气榜")
        if novels:
            result["人气榜"] = novels

        return result

    def scrape_rank(
        self,
        category_id: str,
        gender: str = "male",
        period: str = "read"
    ) -> list[NovelRank]:
        """抓取指定榜单"""
        if category_id in self.RANK_TYPES:
            rank_name, nav = self.RANK_TYPES[category_id]
            return self._fetch_rank(nav, category_id)

        # 默认人气榜
        return self._fetch_rank("default")

    def scrape_all(
        self,
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """抓取所有/指定榜单"""
        all_novels = []

        if period and period in self.PERIOD_MAP:
            rank_type = self.PERIOD_MAP[period]
            if rank_type == "default":
                novels = self._fetch_rank("default")
            elif rank_type in self.RANK_TYPES:
                nav = self.RANK_TYPES[rank_type][1]
                novels = self._fetch_rank(nav, rank_type)
            else:
                novels = self._fetch_rank("default")
            return novels

        # 抓取主要榜单
        rank_list = [
            ("default", ""),      # 人气榜
            ("new-book", "4"),    # 新书榜
            ("click", "5"),      # 点击榜
            ("end", "8"),        # 完结榜
        ]

        for nav, rt in rank_list:
            novels = self._fetch_rank(nav, rt)
            all_novels.extend(novels)
            if self.delay > 0:
                time.sleep(self.delay)

        return all_novels
