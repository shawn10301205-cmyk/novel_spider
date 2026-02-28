"""
番茄小说下载器 — 对接 Tomato-Novel-Downloader Web API

通过调用 Tomato-Novel-Downloader 的 HTTP API 实现小说下载。
Tomato 服务负责解密和下载正文，本模块只做转发和状态管理。

使用前提:
    1. 下载 Tomato-Novel-Downloader Release 版本
    2. 启动服务: ./tomato-dl --server
    3. 在 config.yaml 中配置 tomato_url

使用方法:
    from downloader import FanqieDownloader

    dl = FanqieDownloader(config.get("download", {}))
    info = dl.get_book_info("7143038691944959011")
    dl.start_download("7143038691944959011")
    status = dl.get_download_status("7143038691944959011")
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

import requests


# ── 数据模型 ────────────────────────────────────────

@dataclass
class BookInfo:
    """书籍信息"""
    book_id: str = ""
    title: str = ""
    author: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    chapter_count: int = 0
    word_count: int = 0
    finished: Optional[bool] = None
    cover_url: str = ""
    score: float = 0.0
    read_count: str = ""
    category: str = ""

    def to_dict(self) -> dict:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "tags": self.tags,
            "chapter_count": self.chapter_count,
            "word_count": self.word_count,
            "finished": self.finished,
            "cover_url": self.cover_url,
            "score": self.score,
            "read_count": self.read_count,
            "category": self.category,
        }


@dataclass
class ChapterInfo:
    """章节信息"""
    chapter_id: str
    title: str
    volume: str = ""

    def to_dict(self) -> dict:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "volume": self.volume,
        }


@dataclass
class DownloadProgress:
    """下载进度"""
    book_id: str = ""
    title: str = ""
    job_id: int = 0
    total: int = 0
    done: int = 0
    failed: int = 0
    status: str = "pending"  # pending / queued / running / done / error
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "job_id": self.job_id,
            "total": self.total,
            "done": self.done,
            "failed": self.failed,
            "status": self.status,
            "message": self.message,
        }


# ── 下载器 ──────────────────────────────────────────

class FanqieDownloader:
    """
    番茄小说下载器

    通过 Tomato-Novel-Downloader 的 Web API 实现下载功能。
    本模块自身也提供基础的书籍信息和章节列表获取（直接从番茄网站获取）。
    """

    BASE_URL = "https://fanqienovel.com"
    DIRECTORY_API = "https://fanqienovel.com/api/reader/directory/detail"

    def __init__(self, config: dict):
        # Tomato 服务地址
        self.tomato_url = config.get(
            "tomato_url", "http://127.0.0.1:18423"
        ).rstrip("/")

        self.timeout = config.get("request_timeout", 15)
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    # ── Tomato 服务连接检测 ───────────────────────────

    def check_tomato(self) -> dict:
        """
        检查 Tomato 服务是否可用

        Returns:
            服务状态信息，包含 version、use_official_api 等
            连接失败返回 {"connected": False, "error": "..."}
        """
        try:
            resp = requests.get(
                f"{self.tomato_url}/api/status",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            data["connected"] = True
            return data
        except Exception as e:
            return {"connected": False, "error": str(e)}

    # ── 书籍信息（通过 Tomato API）─────────────────────

    def get_book_info(self, book_id: str) -> Optional[BookInfo]:
        """
        获取书籍信息

        优先通过 Tomato 的 preview API（信息更完整），
        失败则回退到直接从番茄网站解析。
        """
        # 优先走 Tomato
        info = self._get_book_info_from_tomato(book_id)
        if info and info.title:
            return info

        # 回退：直接从番茄网站获取
        return self._get_book_info_from_web(book_id)

    def _get_book_info_from_tomato(self, book_id: str) -> Optional[BookInfo]:
        """通过 Tomato preview API 获取书信息"""
        try:
            resp = requests.get(
                f"{self.tomato_url}/api/preview/{book_id}",
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return BookInfo(
                book_id=str(data.get("book_id", book_id)),
                title=data.get("book_name", "") or data.get("title", ""),
                author=data.get("author", ""),
                description=data.get("description", ""),
                tags=data.get("tags", []) or [],
                chapter_count=data.get("chapter_count", 0),
                word_count=data.get("word_count", 0),
                finished=data.get("finished"),
                cover_url=data.get("cover_url", ""),
                score=data.get("score", 0.0),
                read_count=data.get("read_count_text", ""),
                category=data.get("category", ""),
            )
        except Exception:
            return None

    def _get_book_info_from_web(self, book_id: str) -> Optional[BookInfo]:
        """直接从番茄网站页面获取书信息（兜底方案）"""
        url = f"{self.BASE_URL}/page/{book_id}"
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,*/*",
            }
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except Exception:
            return None

        html = resp.text
        info = BookInfo(book_id=book_id)

        # 解析 __NEXT_DATA__
        m = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL,
        )
        if m:
            try:
                data = json.loads(m.group(1))
                info = self._extract_info_from_json(data, book_id)
            except json.JSONDecodeError:
                pass

        # 回退正则
        if not info.title:
            title_m = re.search(r'"bookName"\s*:\s*"(.*?)"', html)
            author_m = re.search(r'"author"\s*:\s*"(.*?)"', html)
            if title_m:
                info.title = title_m.group(1)
            if author_m:
                info.author = author_m.group(1)

        return info if info.title else None

    def _extract_info_from_json(self, data: dict, book_id: str) -> BookInfo:
        """从 JSON 数据中递归查找书籍信息"""
        info = BookInfo(book_id=book_id)

        def find(obj, keys, t=str):
            if isinstance(obj, dict):
                for k in keys:
                    if k in obj and isinstance(obj[k], t):
                        return obj[k]
                for v in obj.values():
                    r = find(v, keys, t)
                    if r is not None:
                        return r
            elif isinstance(obj, list):
                for item in obj:
                    r = find(item, keys, t)
                    if r is not None:
                        return r
            return None

        info.title = find(data, ["bookName", "book_name", "title"]) or ""
        info.author = find(data, ["author", "authorName"]) or ""
        info.description = find(data, ["abstract", "description"]) or ""
        info.cover_url = find(data, ["coverUrl", "cover_url"]) or ""

        return info

    # ── 章节目录（直接从番茄 API）─────────────────────

    def get_chapter_list(self, book_id: str) -> list:
        """获取书籍章节列表"""
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
            resp = requests.get(
                self.DIRECTORY_API,
                params={"bookId": book_id},
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        return self._parse_chapter_list(data)

    def _parse_chapter_list(self, data: dict) -> list:
        """从 API 响应中提取章节列表"""
        chapters = []
        root = data.get("data", data)

        # 查找章节数组
        chapter_array = None
        for key in ["chapterList", "chapter_list", "chapters",
                     "item_list", "items", "list"]:
            if key in root and isinstance(root[key], list):
                chapter_array = root[key]
                break

        if not chapter_array:
            return []

        for item in chapter_array:
            if not isinstance(item, dict):
                continue

            volume_name = ""
            for vk in ["volume_name", "volumeName", "title"]:
                if vk in item and isinstance(item[vk], str):
                    volume_name = item[vk]
                    break

            sub_chapters = None
            for sk in ["chapters", "chapterList", "chapter_list"]:
                if sk in item and isinstance(item[sk], list):
                    sub_chapters = item[sk]
                    break

            if sub_chapters:
                for ch in sub_chapters:
                    parsed = self._parse_chapter(ch, volume_name)
                    if parsed:
                        chapters.append(parsed)
            else:
                parsed = self._parse_chapter(item, volume_name)
                if parsed:
                    chapters.append(parsed)

        return chapters

    def _parse_chapter(self, item: dict, volume: str = "") -> Optional[ChapterInfo]:
        """解析单个章节"""
        chapter_id = None
        for k in ["item_id", "itemId", "chapter_id", "chapterId", "id"]:
            if k in item:
                chapter_id = str(item[k])
                break
        if not chapter_id:
            return None

        title = ""
        for k in ["title", "chapter_title", "chapterTitle", "name"]:
            if k in item and isinstance(item[k], str):
                title = item[k].strip()
                break

        return ChapterInfo(
            chapter_id=chapter_id,
            title=title or f"第{chapter_id}章",
            volume=volume,
        )

    # ── 下载功能（通过 Tomato API）────────────────────

    def start_download(self, book_id: str) -> dict:
        """
        提交下载任务到 Tomato 服务

        Returns:
            {"success": True, "job_id": 1, "state": "queued"}
            {"success": False, "error": "..."}
        """
        try:
            resp = requests.post(
                f"{self.tomato_url}/api/jobs",
                json={"book_id": book_id},
                timeout=self.timeout,
            )
            data = resp.json()

            if resp.status_code == 200 and "id" in data:
                return {
                    "success": True,
                    "job_id": data["id"],
                    "book_id": data.get("book_id", book_id),
                    "state": data.get("state", "queued"),
                }
            else:
                return {
                    "success": False,
                    "error": data.get("error", data.get("message", "未知错误")),
                }
        except requests.ConnectionError:
            return {
                "success": False,
                "error": f"无法连接 Tomato 服务 ({self.tomato_url})，请确认服务已启动",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_download_status(self, book_id: str = None) -> list:
        """
        获取下载任务状态

        Args:
            book_id: 可选，指定只查某本书的状态

        Returns:
            DownloadProgress 列表
        """
        try:
            resp = requests.get(
                f"{self.tomato_url}/api/jobs",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results = []
        for item in data.get("items", []):
            bid = item.get("book_id", "")
            if book_id and bid != book_id:
                continue

            progress = item.get("progress", {})
            total = progress.get("chapter_total", 0)
            group_done = progress.get("group_done", 0)
            group_total = progress.get("group_total", 1)

            # 估算已完成章节数
            done = int(total * group_done / group_total) if group_total > 0 else 0

            state = item.get("state", "unknown")

            results.append(DownloadProgress(
                book_id=bid,
                title=item.get("title", ""),
                job_id=item.get("id", 0),
                total=total,
                done=done,
                status=state,
                message=item.get("message") or "",
            ))

        return results

    def cancel_download(self, job_id: int) -> bool:
        """取消下载任务"""
        try:
            resp = requests.post(
                f"{self.tomato_url}/api/jobs/{job_id}/cancel",
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_library(self) -> list:
        """获取已下载的书库列表"""
        try:
            resp = requests.get(
                f"{self.tomato_url}/api/library",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception:
            return []

    def search_books(self, keyword: str) -> list:
        """通过 Tomato 搜索小说"""
        try:
            resp = requests.get(
                f"{self.tomato_url}/api/search",
                params={"q": keyword},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("items", resp.json().get("data", []))
        except Exception:
            return []


# ── CLI 入口 ────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="番茄小说下载器")
    parser.add_argument("book_id", nargs="?", help="书籍 ID")
    parser.add_argument("--info-only", action="store_true",
                        help="只显示书籍信息")
    parser.add_argument("--chapters-only", action="store_true",
                        help="只显示章节列表")
    parser.add_argument("--status", action="store_true",
                        help="查看所有下载状态")
    parser.add_argument("--check", action="store_true",
                        help="检查 Tomato 服务连接")
    parser.add_argument("--tomato-url", type=str,
                        default="http://127.0.0.1:18423",
                        help="Tomato 服务地址")
    args = parser.parse_args()

    dl = FanqieDownloader({"tomato_url": args.tomato_url})

    if args.check:
        st = dl.check_tomato()
        if st.get("connected"):
            print(f"✅ Tomato 服务正常")
            print(f"   版本: {st.get('version', '?')}")
            cfg = st.get("config", {})
            print(f"   官方API: {'✅' if cfg.get('use_official_api') else '❌'}")
        else:
            print(f"❌ 无法连接: {st.get('error', '')}")

    elif args.status:
        jobs = dl.get_download_status()
        if not jobs:
            print("暂无下载任务")
        else:
            for j in jobs:
                pct = f"{j.done}/{j.total}" if j.total else "?"
                print(f"  [{j.status}] {j.title} ({pct})")

    elif args.book_id:
        if args.info_only:
            info = dl.get_book_info(args.book_id)
            if info:
                print(f"书名: {info.title}")
                print(f"作者: {info.author}")
                print(f"分类: {info.category}")
                print(f"评分: {info.score}")
                print(f"字数: {info.word_count}")
                print(f"章节: {info.chapter_count}")
                print(f"在读: {info.read_count}")
                print(f"完结: {info.finished}")
                print(f"标签: {', '.join(info.tags)}")
                print(f"简介: {info.description[:200]}")
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
            # 提交下载
            result = dl.start_download(args.book_id)
            if result["success"]:
                print(f"✅ 下载任务已提交 (job_id: {result['job_id']})")
                print(f"   状态: {result['state']}")
                print(f"   用 --status 查看进度")
            else:
                print(f"❌ {result['error']}")
    else:
        parser.print_help()
