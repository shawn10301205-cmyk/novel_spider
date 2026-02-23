"""番茄小说网排行榜爬虫"""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper
from models.novel import NovelRank


class FanqieScraper(BaseScraper):
    """番茄小说网爬虫"""

    SOURCE_NAME = "番茄小说"
    BASE_URL = "https://fanqienovel.com"

    # 性别映射: 参数名 -> URL 参数
    GENDER_MAP = {
        "male": "1",    # 男频
        "female": "0",  # 女频
    }

    # 性别 ID -> 中文显示名
    GENDER_NAMES = {
        "1": "男频",
        "0": "女频",
    }

    # 榜单类型映射
    PERIOD_MAP = {
        "new": "1",     # 新书榜
        "read": "2",    # 阅读榜
    }

    # 榜单类型 -> 中文显示名
    PERIOD_NAMES = {
        "1": "新书榜",
        "2": "阅读榜",
    }

    # 男频分类
    MALE_CATEGORIES = {
        "1141": "西方奇幻",
        "1140": "东方仙侠",
        "8": "科幻末世",
        "261": "都市日常",
        "124": "都市修真",
        "1014": "都市高武",
        "273": "历史古代",
        "27": "战神赘婿",
        "263": "都市种田",
        "258": "传统玄幻",
        "272": "历史脑洞",
        "539": "悬疑脑洞",
        "262": "都市脑洞",
        "257": "玄幻脑洞",
        "751": "悬疑灵异",
        "504": "抗战谍战",
        "746": "游戏体育",
        "718": "动漫衍生",
        "1016": "男频衍生",
    }

    # 女频分类
    FEMALE_CATEGORIES = {
        "1139": "古风世情",
        "8": "科幻末世",
        "746": "游戏体育",
        "1015": "女频衍生",
        "248": "玄幻言情",
        "23": "种田",
        "79": "年代",
        "267": "现言脑洞",
        "246": "宫斗宅斗",
        "539": "悬疑脑洞",
        "253": "古言脑洞",
        "24": "快穿",
        "749": "青春甜宠",
        "745": "星光璀璨",
        "747": "女频悬疑",
        "750": "职场婚恋",
        "748": "豪门总裁",
        "1017": "民国言情",
    }

    def _get_headers(self) -> dict:
        """获取请求头（番茄小说专用，不能包含 Accept-Encoding）"""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

    def get_categories(self) -> list[dict]:
        """获取所有分类列表"""
        categories = []

        for cat_id, cat_name in self.MALE_CATEGORIES.items():
            categories.append({
                "id": cat_id,
                "name": cat_name,
                "gender": "male",
                "gender_name": "男频",
            })

        for cat_id, cat_name in self.FEMALE_CATEGORIES.items():
            categories.append({
                "id": cat_id,
                "name": cat_name,
                "gender": "female",
                "gender_name": "女频",
            })

        return categories

    def scrape_rank(
        self,
        category_id: str,
        gender: str = "male",
        period: str = "read"
    ) -> list[NovelRank]:
        """抓取指定分类的排行榜"""
        gender_code = self.GENDER_MAP.get(gender, "1")
        period_code = self.PERIOD_MAP.get(period, "2")

        # 获取分类名
        if gender == "male":
            category_name = self.MALE_CATEGORIES.get(category_id, "未知分类")
        else:
            category_name = self.FEMALE_CATEGORIES.get(category_id, "未知分类")

        url = f"{self.BASE_URL}/rank/{gender_code}_{period_code}_{category_id}"

        print(f"  正在抓取: {self.GENDER_NAMES[gender_code]} - "
              f"{self.PERIOD_NAMES[period_code]} - {category_name} ...")

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {url} - {e}")
            return []

        return self._parse_rank_page(
            resp.text, category_name,
            self.GENDER_NAMES[gender_code],
            self.PERIOD_NAMES[period_code]
        )

    def _parse_rank_page(
        self,
        html: str,
        category: str,
        gender_name: str,
        period_name: str
    ) -> list[NovelRank]:
        """
        解析排行榜页面 HTML

        番茄小说页面结构:
        div.muye-rank-book-list
          └── div.rank-book-item  (每个排名条目)
                ├── div.book-item-text
                │     ├── div.title > a[href="/page/xxx"]  (书名+链接)
                │     ├── a[href="/author-page/xxx"]  (作者)
                │     └── a[href="/reader/xxx"]  (最新章节)
                └── ...
        """
        soup = BeautifulSoup(html, "lxml")
        novels = []

        # 方法1: 尝试用 rank-book-item 容器
        rank_items = soup.select("div.rank-book-item")
        if rank_items:
            return self._parse_by_containers(rank_items, category, gender_name, period_name)

        # 方法2: 回退 - 从页面所有链接中提取
        return self._parse_by_links(soup, category, gender_name, period_name)

    def _parse_by_containers(
        self,
        rank_items,
        category: str,
        gender_name: str,
        period_name: str
    ) -> list[NovelRank]:
        """通过排名容器解析"""
        novels = []
        for idx, item in enumerate(rank_items, 1):
            try:
                # 书名
                title_link = item.select_one('a[href*="/page/"]')
                title = title_link.get_text(strip=True) if title_link else ""
                book_url = ""
                if title_link and title_link.get("href"):
                    href = title_link["href"]
                    book_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                # 作者
                author_link = item.select_one('a[href*="/author-page/"]')
                author = author_link.get_text(strip=True) if author_link else ""
                author_url = ""
                if author_link and author_link.get("href"):
                    href = author_link["href"]
                    author_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                # 最新章节
                chapter_link = item.select_one('a[href*="/reader/"]')
                latest_chapter = ""
                if chapter_link:
                    latest_chapter = chapter_link.get_text(strip=True)
                    if latest_chapter.startswith("最近更新："):
                        latest_chapter = latest_chapter[5:]

                if title:
                    novels.append(NovelRank(
                        rank=idx,
                        title=self._clean_text(title),
                        author=self._clean_text(author),
                        category=category,
                        gender=gender_name,
                        period=period_name,
                        latest_chapter=self._clean_text(latest_chapter),
                        book_url=book_url,
                        author_url=author_url,
                        source=self.SOURCE_NAME,
                    ))
            except Exception as e:
                print(f"  ⚠ 解析第{idx}项失败: {e}")

        return novels

    def _parse_by_links(
        self,
        soup: BeautifulSoup,
        category: str,
        gender_name: str,
        period_name: str
    ) -> list[NovelRank]:
        """
        回退解析：从页面链接提取排行数据
        """
        novels = []

        # 收集书籍链接（去重保序）
        seen_hrefs = set()
        books = []  # (title, href)
        for link in soup.select('a[href*="/page/"]'):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if text and href and href not in seen_hrefs:
                seen_hrefs.add(href)
                books.append((text, href))

        # 收集作者链接（去重保序）
        seen_authors = set()
        authors = []  # (name, href)
        for link in soup.select('a[href*="/author-page/"]'):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and href not in seen_authors:
                seen_authors.add(href)
                authors.append((text, href))

        # 收集章节链接
        chapters = []
        for link in soup.select('a[href*="/reader/"]'):
            text = link.get_text(strip=True)
            if text:
                if text.startswith("最近更新："):
                    text = text[5:]
                chapters.append(text)

        for idx, (title, href) in enumerate(books):
            author_name = authors[idx][0] if idx < len(authors) else ""
            author_href = authors[idx][1] if idx < len(authors) else ""
            latest = chapters[idx] if idx < len(chapters) else ""

            book_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            author_url = author_href if author_href.startswith("http") else f"{self.BASE_URL}{author_href}" if author_href else ""

            novels.append(NovelRank(
                rank=idx + 1,
                title=self._clean_text(title),
                author=self._clean_text(author_name),
                category=category,
                gender=gender_name,
                period=period_name,
                latest_chapter=self._clean_text(latest),
                book_url=book_url,
                author_url=author_url,
                source=self.SOURCE_NAME,
            ))

        return novels

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本中的字体反爬私有 Unicode 字符"""
        # 移除 Unicode 私有使用区字符 (PUA)
        # E000-F8FF: BMP 私有使用区
        return "".join(c for c in text if not (0xE000 <= ord(c) <= 0xF8FF))

    def scrape_all(
        self,
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """抓取所有排行榜数据"""
        all_novels = []

        # 确定要抓取的频道
        genders = [gender] if gender else ["male", "female"]
        # 确定要抓取的榜单类型
        periods = [period] if period else ["read", "new"]

        for g in genders:
            categories = self.MALE_CATEGORIES if g == "male" else self.FEMALE_CATEGORIES

            for p in periods:
                for cat_id in categories:
                    novels = self.scrape_rank(cat_id, g, p)
                    all_novels.extend(novels)
                    # 请求间隔
                    if self.delay > 0:
                        time.sleep(self.delay)

        return all_novels

    def scrape_categories(
        self,
        category_names: list[str],
        gender: Optional[str] = None,
        period: Optional[str] = None
    ) -> list[NovelRank]:
        """按分类名称抓取指定分类"""
        all_novels = []
        genders = [gender] if gender else ["male", "female"]
        periods = [period] if period else ["read", "new"]

        for g in genders:
            categories = self.MALE_CATEGORIES if g == "male" else self.FEMALE_CATEGORIES

            for p in periods:
                for cat_id, cat_name in categories.items():
                    if cat_name in category_names:
                        novels = self.scrape_rank(cat_id, g, p)
                        all_novels.extend(novels)
                        if self.delay > 0:
                            time.sleep(self.delay)

        return all_novels
