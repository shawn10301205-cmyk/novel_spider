"""小说排行榜数据模型"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class NovelRank:
    """小说排行数据"""
    rank: int                          # 排名
    title: str                         # 书名
    author: str                        # 作者
    category: str                      # 分类（如都市日常、玄幻等）
    gender: str                        # 频道（男频/女频）
    period: str                        # 榜单类型（阅读榜/新书榜）
    latest_chapter: str = ""           # 最近更新章节
    book_url: str = ""                 # 书籍链接
    author_url: str = ""               # 作者主页链接
    source: str = ""                   # 来源网站
    extra: dict = field(default_factory=dict)  # 扩展字段（不同网站的额外数据）

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def __str__(self) -> str:
        return f"[{self.rank}] {self.title} - {self.author} ({self.category})"
