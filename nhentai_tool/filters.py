# 模块3: filters.py — 过滤引擎
# 对 list[NhentaiGallery] 进行各种过滤、去重和排序，支持链式调用

from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Optional

from .models import NhentaiGallery

# ---------------------------------------------------------------------------
# 3.1 去重过滤
# ---------------------------------------------------------------------------

def dedupe_by_id(galleries: list[NhentaiGallery]) -> list[NhentaiGallery]:
    """按 gallery.id 去重，保留首次出现的"""
    seen: set[int] = set()
    result: list[NhentaiGallery] = []
    for g in galleries:
        if g.id not in seen:
            seen.add(g.id)
            result.append(g)
    return result


def _normalize_title(title: str) -> str:
    """去除方括号/圆括号内容，转小写，去首尾空白"""
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"\(.*?\)", "", title)
    return title.lower().strip()


def dedupe_by_title(galleries: list[NhentaiGallery]) -> list[NhentaiGallery]:
    """
    按标题相似度去重：先归一化标题（去除 [...] / (...) 内容，转小写），
    相同归一化标题的只保留 num_favorites 最高的一个。
    """
    # 预先计算每个 gallery 的归一化标题，避免重复计算
    norm_titles: dict[int, str] = {
        g.id: _normalize_title(g.title_english or g.title_pretty or g.title_japanese)
        for g in galleries
    }

    groups: dict[str, NhentaiGallery] = {}
    for g in galleries:
        key = norm_titles[g.id]
        if key not in groups or g.num_favorites > groups[key].num_favorites:
            groups[key] = g

    # 按原始顺序重建列表（保留原始先后次序中的"优胜者"）
    winner_ids: set[int] = {g.id for g in groups.values()}
    return [g for g in galleries if g.id in winner_ids and groups[norm_titles[g.id]].id == g.id]


# ---------------------------------------------------------------------------
# 3.2 语言过滤
# ---------------------------------------------------------------------------

def filter_languages(
    galleries: list[NhentaiGallery],
    include: set[str],
) -> list[NhentaiGallery]:
    """只保留 languages 字段中包含 include 集合中任一语言的作品（大小写不敏感）"""
    include_lower = {lang.lower() for lang in include}
    return [
        g for g in galleries
        if any(lang.lower() in include_lower for lang in g.languages)
    ]


def exclude_languages(
    galleries: list[NhentaiGallery],
    exclude: set[str],
) -> list[NhentaiGallery]:
    """排除 languages 字段中包含 exclude 集合中任一语言的作品（大小写不敏感）"""
    exclude_lower = {lang.lower() for lang in exclude}
    return [
        g for g in galleries
        if not any(lang.lower() in exclude_lower for lang in g.languages)
    ]


# ---------------------------------------------------------------------------
# 3.3 标签过滤
# ---------------------------------------------------------------------------

def filter_tags_include_all(
    galleries: list[NhentaiGallery],
    tags: set[str],
) -> list[NhentaiGallery]:
    """必须包含所有指定标签（大小写不敏感）"""
    tags_lower = {t.lower() for t in tags}
    return [
        g for g in galleries
        if tags_lower.issubset({t.lower() for t in g.tags})
    ]


def filter_tags_include_any(
    galleries: list[NhentaiGallery],
    tags: set[str],
) -> list[NhentaiGallery]:
    """包含任一指定标签即保留（大小写不敏感）"""
    tags_lower = {t.lower() for t in tags}
    return [
        g for g in galleries
        if any(t.lower() in tags_lower for t in g.tags)
    ]


def filter_tags_exclude(
    galleries: list[NhentaiGallery],
    tags: set[str],
) -> list[NhentaiGallery]:
    """排除包含任一指定标签的作品（大小写不敏感）"""
    tags_lower = {t.lower() for t in tags}
    return [
        g for g in galleries
        if not any(t.lower() in tags_lower for t in g.tags)
    ]


# ---------------------------------------------------------------------------
# 3.4 数值/日期过滤
# ---------------------------------------------------------------------------

def filter_pages(
    galleries: list[NhentaiGallery],
    min_pages: Optional[int] = None,
    max_pages: Optional[int] = None,
) -> list[NhentaiGallery]:
    """按页数范围过滤"""
    result = galleries
    if min_pages is not None:
        result = [g for g in result if g.num_pages >= min_pages]
    if max_pages is not None:
        result = [g for g in result if g.num_pages <= max_pages]
    return result


def filter_favorites(
    galleries: list[NhentaiGallery],
    min_favs: Optional[int] = None,
) -> list[NhentaiGallery]:
    """按最低收藏数过滤"""
    if min_favs is None:
        return galleries
    return [g for g in galleries if g.num_favorites >= min_favs]


def filter_date(
    galleries: list[NhentaiGallery],
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
) -> list[NhentaiGallery]:
    """按上传日期范围过滤，参数为 datetime 对象（支持 aware/naive）"""
    result = galleries
    if after is not None:
        # 统一处理 aware 与 naive 的比较
        if after.tzinfo is None:
            result = [
                g for g in result
                if g.upload_date.replace(tzinfo=None) >= after
            ]
        else:
            result = [g for g in result if g.upload_date >= after]
    if before is not None:
        if before.tzinfo is None:
            result = [
                g for g in result
                if g.upload_date.replace(tzinfo=None) <= before
            ]
        else:
            result = [g for g in result if g.upload_date <= before]
    return result


# ---------------------------------------------------------------------------
# 3.5 其他过滤
# ---------------------------------------------------------------------------

def filter_artists(
    galleries: list[NhentaiGallery],
    include: set[str],
) -> list[NhentaiGallery]:
    """只保留指定艺术家的作品（大小写不敏感）"""
    include_lower = {a.lower() for a in include}
    return [
        g for g in galleries
        if any(a.lower() in include_lower for a in g.artists)
    ]


def filter_categories(
    galleries: list[NhentaiGallery],
    include: set[str],
) -> list[NhentaiGallery]:
    """只保留指定类型（doujinshi / manga / artist cg / game cg 等）（大小写不敏感）"""
    include_lower = {c.lower() for c in include}
    return [
        g for g in galleries
        if any(c.lower() in include_lower for c in g.categories)
    ]


# ---------------------------------------------------------------------------
# 3.6 排序
# ---------------------------------------------------------------------------

_SORT_KEY_MAP: dict[str, Callable[[NhentaiGallery], object]] = {
    "favorites": lambda g: g.num_favorites,
    "pages":     lambda g: g.num_pages,
    "date":      lambda g: g.upload_date,
    "id":        lambda g: g.id,
}


def sort_by(
    galleries: list[NhentaiGallery],
    key: str = "favorites",
    reverse: bool = True,
) -> list[NhentaiGallery]:
    """
    对结果排序。

    key 支持: "favorites" / "pages" / "date" / "id"
    """
    key_func = _SORT_KEY_MAP.get(key)
    if key_func is None:
        raise ValueError(
            f"不支持的排序 key: {key!r}，可选值: {list(_SORT_KEY_MAP)}"
        )
    return sorted(galleries, key=key_func, reverse=reverse)


# ---------------------------------------------------------------------------
# 3.7 FilterPipeline
# ---------------------------------------------------------------------------

class FilterPipeline:
    """链式过滤管道：按顺序依次执行多个过滤步骤，每步打印数量变化"""

    def __init__(self) -> None:
        # 每个元素为 (filter_func, kwargs)
        self._steps: list[tuple[Callable, dict]] = []

    def add(self, filter_func: Callable, **kwargs) -> "FilterPipeline":
        """添加一个过滤步骤，返回 self 以支持链式调用"""
        self._steps.append((filter_func, kwargs))
        return self

    def apply(self, galleries: list[NhentaiGallery]) -> list[NhentaiGallery]:
        """按顺序执行所有过滤步骤，每步打印过滤前后的数量变化"""
        current = list(galleries)
        for func, kwargs in self._steps:
            before = len(current)
            current = func(current, **kwargs) if kwargs else func(current)
            after = len(current)
            print(
                f"[Filter] {func.__name__}: {before} → {after} "
                f"(过滤掉 {before - after} 条)"
            )
        return current

    @classmethod
    def from_config(cls, config: dict) -> "FilterPipeline":
        """
        从 dict 配置构建 FilterPipeline。

        配置格式示例::

            {
                "dedupe": "id",                          # "id" / "title" / "both"
                "languages": {"include": ["english"]},
                "tags_exclude": ["guro", "yaoi"],
                "tags_include_any": [],
                "tags_include_all": [],
                "pages": {"min": 10, "max": 200},
                "favorites": {"min": 100},
                "date": {"after": "2023-01-01"},
                "artists": {"include": []},
                "categories": {"include": ["doujinshi"]},
                "sort": {"key": "favorites", "reverse": True},
            }
        """
        pipeline = cls()

        # 去重
        dedupe = config.get("dedupe")
        if dedupe == "id":
            pipeline.add(dedupe_by_id)
        elif dedupe == "title":
            pipeline.add(dedupe_by_title)
        elif dedupe == "both":
            pipeline.add(dedupe_by_id)
            pipeline.add(dedupe_by_title)

        # 语言过滤
        lang_cfg = config.get("languages", {})
        if lang_cfg.get("include"):
            pipeline.add(filter_languages, include=set(lang_cfg["include"]))

        # 标签排除
        tags_excl = config.get("tags_exclude", [])
        if tags_excl:
            pipeline.add(filter_tags_exclude, tags=set(tags_excl))

        # 标签包含（任一）
        tags_any = config.get("tags_include_any", [])
        if tags_any:
            pipeline.add(filter_tags_include_any, tags=set(tags_any))

        # 标签包含（全部）
        tags_all = config.get("tags_include_all", [])
        if tags_all:
            pipeline.add(filter_tags_include_all, tags=set(tags_all))

        # 页数范围
        pages_cfg = config.get("pages", {})
        if pages_cfg:
            pipeline.add(
                filter_pages,
                min_pages=pages_cfg.get("min"),
                max_pages=pages_cfg.get("max"),
            )

        # 最低收藏数
        fav_cfg = config.get("favorites", {})
        if fav_cfg.get("min") is not None:
            pipeline.add(filter_favorites, min_favs=fav_cfg["min"])

        # 日期范围
        date_cfg = config.get("date", {})
        if date_cfg:
            after_dt: Optional[datetime] = None
            before_dt: Optional[datetime] = None
            if date_cfg.get("after"):
                after_dt = datetime.fromisoformat(date_cfg["after"])
            if date_cfg.get("before"):
                before_dt = datetime.fromisoformat(date_cfg["before"])
            if after_dt is not None or before_dt is not None:
                pipeline.add(filter_date, after=after_dt, before=before_dt)

        # 艺术家过滤
        artist_cfg = config.get("artists", {})
        if artist_cfg.get("include"):
            pipeline.add(filter_artists, include=set(artist_cfg["include"]))

        # 类型过滤
        cat_cfg = config.get("categories", {})
        if cat_cfg.get("include"):
            pipeline.add(filter_categories, include=set(cat_cfg["include"]))

        # 排序（放最后）
        sort_cfg = config.get("sort", {})
        if sort_cfg:
            pipeline.add(
                sort_by,
                key=sort_cfg.get("key", "favorites"),
                reverse=sort_cfg.get("reverse", True),
            )

        return pipeline
