"""控制台输出导出器"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from models.novel import NovelRank
from sorter import group_by_category


def print_novels(novels: list[NovelRank], group_by: str = "none"):
    """
    在控制台输出小说排行数据

    Args:
        novels: 排行榜数据
        group_by: 分组方式 "none", "category", "gender"
    """
    console = Console()

    if not novels:
        console.print("[yellow]没有抓取到任何数据[/yellow]")
        return

    if group_by == "category":
        _print_grouped_by_category(console, novels)
    elif group_by == "gender":
        _print_grouped_by_gender(console, novels)
    else:
        _print_flat(console, novels)


def _print_flat(console: Console, novels: list[NovelRank]):
    """平铺输出"""
    table = _create_table(f"📚 小说排行榜 (共{len(novels)}本)")

    for novel in novels:
        table.add_row(
            str(novel.rank),
            novel.title,
            novel.author,
            novel.category,
            novel.gender,
            novel.period,
            novel.latest_chapter[:30] + "..." if len(novel.latest_chapter) > 30 else novel.latest_chapter,
            novel.source,
        )

    console.print(table)


def _print_grouped_by_category(console: Console, novels: list[NovelRank]):
    """按分类分组输出"""
    groups = group_by_category(novels)

    for category, group_novels in groups.items():
        table = _create_table(f"📚 {category} (共{len(group_novels)}本)")

        for novel in group_novels:
            table.add_row(
                str(novel.rank),
                novel.title,
                novel.author,
                novel.category,
                novel.gender,
                novel.period,
                novel.latest_chapter[:30] + "..." if len(novel.latest_chapter) > 30 else novel.latest_chapter,
                novel.source,
            )

        console.print(table)
        console.print()


def _print_grouped_by_gender(console: Console, novels: list[NovelRank]):
    """按频道分组输出"""
    from sorter import group_by_gender
    groups = group_by_gender(novels)

    for gender, group_novels in groups.items():
        table = _create_table(f"📚 {gender} (共{len(group_novels)}本)")

        for novel in group_novels:
            table.add_row(
                str(novel.rank),
                novel.title,
                novel.author,
                novel.category,
                novel.gender,
                novel.period,
                novel.latest_chapter[:30] + "..." if len(novel.latest_chapter) > 30 else novel.latest_chapter,
                novel.source,
            )

        console.print(table)
        console.print()


def _create_table(title: str) -> Table:
    """创建格式化表格"""
    table = Table(title=title, show_lines=True, title_style="bold magenta")
    table.add_column("排名", style="bold cyan", justify="center", width=4)
    table.add_column("书名", style="bold white", min_width=10)
    table.add_column("作者", style="green", min_width=6)
    table.add_column("分类", style="yellow", min_width=6)
    table.add_column("频道", style="blue", width=4)
    table.add_column("榜单", style="magenta", width=6)
    table.add_column("最新章节", style="dim", min_width=10)
    table.add_column("来源", style="dim cyan", width=6)
    return table


class ConsoleExporter:
    """控制台导出器"""

    def export(self, novels: list[NovelRank], group_by: str = "none"):
        """导出到控制台"""
        print_novels(novels, group_by)
