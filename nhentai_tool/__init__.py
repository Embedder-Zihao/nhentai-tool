# nhentai_tool 包初始化
# 导出核心类和函数，方便外部直接使用

from .models import NhentaiGallery, NhentaiImage, parse_gallery, parse_search_item, gallery_to_dict
from .client import NhentaiClient
from .filters import (
    FilterPipeline,
    dedupe_by_id,
    dedupe_by_title,
    filter_languages,
    exclude_languages,
    filter_tags_include_all,
    filter_tags_include_any,
    filter_tags_exclude,
    filter_pages,
    filter_favorites,
    filter_date,
    filter_artists,
    filter_categories,
    sort_by,
)

__all__ = [
    "NhentaiGallery",
    "NhentaiImage",
    "parse_gallery",
    "gallery_to_dict",
    "NhentaiClient",
    "FilterPipeline",
    "dedupe_by_id",
    "dedupe_by_title",
    "filter_languages",
    "exclude_languages",
    "filter_tags_include_all",
    "filter_tags_include_any",
    "filter_tags_exclude",
    "filter_pages",
    "filter_favorites",
    "filter_date",
    "filter_artists",
    "filter_categories",
    "sort_by",
]
