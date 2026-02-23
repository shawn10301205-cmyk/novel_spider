"""七猫小说排行榜爬虫"""

import re
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

    HTML 结构:
      li.rank-list-item
        a.s-book-title  -> 书名 + 链接
        span.s-book-info -> 作者 + 分类链接
        span.s-book-update -> 最新章节
        em.rank-num + em.rank-unit -> 热度
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
        "read": "hot",
        "hot": "hot",
        "new": "new",
        "over": "over",
        "collect": "collect",
        "update": "update",
    }

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.qimao.com/paihang",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
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
        """抓取单个榜单页面 (可能有多页，先抓第1页)"""
        # 先尝试不带 /date/ 的 URL, 失败再加
        url = f"{self.BASE_URL}/paihang/{gender_key}/{rank_key}/"
        gender_name = self.GENDERS.get(gender_key, gender_key)
        rank_name = self.RANK_TYPES.get(rank_key, rank_key)

        print(f"  正在抓取: {self.SOURCE_NAME} {gender_name} - {rank_name} ...")

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code == 405:
                # 尝试带 /date/ 的备用 URL
                url = f"{self.BASE_URL}/paihang/{gender_key}/{rank_key}/date/"
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

        items = soup.select("li.rank-list-item")

        for idx, item in enumerate(items, start=1):
            try:
                # 书名 + 链接
                title_a = item.select_one("a.s-book-title")
                if not title_a:
                    continue
                title = title_a.get_text(strip=True)
                if not title:
                    continue

                href = title_a.get("href", "")
                book_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                # 作者 + 分类 + 字数 + 状态 (from span.s-book-info)
                author = ""
                category = ""
                word_count = ""
                status = ""
                info_span = item.select_one("span.s-book-info")
                if info_span:
                    for a in info_span.select("a"):
                        link_href = a.get("href", "")
                        if "/zuozhe/" in link_href:
                            author = a.get_text(strip=True)
                        elif "/shuku/a-" in link_href:
                            category = a.get_text(strip=True)
                    # em 标签里有字数和状态
                    for em in info_span.select("em"):
                        em_text = em.get_text(strip=True)
                        if "万字" in em_text or "字" in em_text:
                            word_count = em_text
                        elif em_text in ("连载中", "已完结"):
                            status = em_text

                # 简介
                intro = ""
                intro_span = item.select_one("span.s-book-intro")
                if intro_span:
                    intro = intro_span.get_text(strip=True)

                # 最新章节
                latest_chapter = ""
                update_span = item.select_one("span.s-book-update")
                if update_span:
                    update_a = update_span.select_one("a")
                    if update_a:
                        latest_chapter = update_a.get_text(strip=True)
                    else:
                        latest_chapter = update_span.get_text(strip=True)
                    latest_chapter = re.sub(r'^最近更新\s*', '', latest_chapter)
                    latest_chapter = re.sub(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$', '', latest_chapter).strip()

                # 热度
                heat = ""
                rank_num = item.select_one("em.rank-num")
                rank_unit = item.select_one("em.rank-unit")
                if rank_num:
                    heat = rank_num.get_text(strip=True)
                    if rank_unit:
                        heat += rank_unit.get_text(strip=True)

                extra = {}
                if heat:
                    extra["heat"] = heat
                if word_count:
                    extra["word_count"] = word_count
                if status:
                    extra["status"] = status
                if intro:
                    extra["intro"] = intro

                novels.append(NovelRank(
                    rank=idx,
                    title=title,
                    author=author,
                    category=category or rank_name,
                    gender=gender_name,
                    period=rank_name,
                    latest_chapter=latest_chapter,
                    book_url=book_url,
                    source=self.SOURCE_NAME,
                    extra=extra,
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
