"""排序和筛选模块"""

from typing import Optional
from models.novel import NovelRank


def sort_by_rank(novels: list[NovelRank], reverse: bool = False) -> list[NovelRank]:
    """按排名排序"""
    return sorted(novels, key=lambda n: n.rank, reverse=reverse)


def sort_by_category(novels: list[NovelRank]) -> list[NovelRank]:
    """按分类分组排序（分类名 -> 排名）"""
    return sorted(novels, key=lambda n: (n.category, n.rank))


def sort_by_gender_then_rank(novels: list[NovelRank]) -> list[NovelRank]:
    """按频道 -> 排名排序"""
    return sorted(novels, key=lambda n: (n.gender, n.rank))


def sort_by_period_then_rank(novels: list[NovelRank]) -> list[NovelRank]:
    """按榜单类型 -> 排名排序"""
    return sorted(novels, key=lambda n: (n.period, n.rank))


def group_by_category(novels: list[NovelRank]) -> dict[str, list[NovelRank]]:
    """按分类分组"""
    groups: dict[str, list[NovelRank]] = {}
    for n in novels:
        key = n.category
        if key not in groups:
            groups[key] = []
        groups[key].append(n)
    return groups


def group_by_gender(novels: list[NovelRank]) -> dict[str, list[NovelRank]]:
    """按频道分组"""
    groups: dict[str, list[NovelRank]] = {}
    for n in novels:
        key = n.gender
        if key not in groups:
            groups[key] = []
        groups[key].append(n)
    return groups


def filter_by_gender(novels: list[NovelRank], gender: str) -> list[NovelRank]:
    """
    按频道筛选

    Args:
        gender: "男频" 或 "女频" 或 "male" 或 "female"
    """
    gender_map = {"male": "男频", "female": "女频"}
    target = gender_map.get(gender, gender)
    return [n for n in novels if n.gender == target]


def filter_by_category(novels: list[NovelRank], categories: list[str]) -> list[NovelRank]:
    """按分类名称筛选"""
    return [n for n in novels if n.category in categories]


def filter_by_period(novels: list[NovelRank], period: str) -> list[NovelRank]:
    """
    按榜单类型筛选

    Args:
        period: "阅读榜" 或 "新书榜" 或 "read" 或 "new"
    """
    period_map = {"read": "阅读榜", "new": "新书榜"}
    target = period_map.get(period, period)
    return [n for n in novels if n.period == target]


def apply_sort(novels: list[NovelRank], sort_key: str) -> list[NovelRank]:
    """
    根据排序键应用排序

    Args:
        sort_key: "rank", "category", "gender", "period"
    """
    sort_funcs = {
        "rank": sort_by_rank,
        "category": sort_by_category,
        "gender": sort_by_gender_then_rank,
        "period": sort_by_period_then_rank,
    }
    func = sort_funcs.get(sort_key)
    if func:
        return func(novels)
    return novels
