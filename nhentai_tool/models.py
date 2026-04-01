# 模块2: models.py — 数据模型与解析
# 将 nhentai API 返回的原始 JSON 解析为结构化 Python dataclass 对象

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# nhentai 图片类型单字符 → 文件扩展名映射（v1 兼容）
EXT_MAP: dict[str, str] = {
    "j": "jpg",
    "p": "png",
    "g": "gif",
    "w": "webp",
    "a": "avif",
}

# CDN 域名
_IMAGE_CDN = "https://i1.nhentai.net"
_THUMB_CDN = "https://t1.nhentai.net"


@dataclass
class NhentaiImage:
    """单张图片的元数据"""

    page_num: int       # 页码（从 1 开始）
    url: str            # 完整图片 URL
    thumbnail_url: str  # 缩略图 URL
    width: int
    height: int
    extension: str      # jpg / png / gif / webp / avif


@dataclass
class NhentaiGallery:
    """一个 nhentai gallery 的完整元数据"""

    id: int
    media_id: str
    title_english: str
    title_japanese: str
    title_pretty: str
    artists: list[str]
    groups: list[str]
    parodies: list[str]
    characters: list[str]
    tags: list[str]
    languages: list[str]
    categories: list[str]
    num_pages: int
    num_favorites: int
    upload_date: datetime
    cover_url: str
    images: list[NhentaiImage]
    url: str


def parse_gallery(data: dict) -> NhentaiGallery:
    """将 nhentai API v2 返回的单个 gallery JSON dict 解析为 NhentaiGallery 对象"""

    gallery_id: int = data["id"]
    media_id: str = str(data["media_id"])

    # 标题
    title_block = data.get("title", {})
    title_english = title_block.get("english", "") or ""
    title_japanese = title_block.get("japanese", "") or ""
    title_pretty = title_block.get("pretty", "") or ""

    # 按 type 字段分组 tags
    artists: list[str] = []
    groups: list[str] = []
    parodies: list[str] = []
    characters: list[str] = []
    tags: list[str] = []
    languages: list[str] = []
    categories: list[str] = []

    for tag in data.get("tags", []):
        name: str = tag.get("name", "")
        tag_type: str = tag.get("type", "")
        if tag_type == "artist":
            artists.append(name)
        elif tag_type == "group":
            groups.append(name)
        elif tag_type == "parody":
            parodies.append(name)
        elif tag_type == "character":
            characters.append(name)
        elif tag_type == "tag":
            tags.append(name)
        elif tag_type == "language":
            languages.append(name)
        elif tag_type == "category":
            categories.append(name)

    # 页数 / 收藏数
    num_pages: int = data.get("num_pages", 0)
    num_favorites: int = data.get("num_favorites", 0)

    # 上传时间戳 → datetime
    upload_ts: int = data.get("upload_date", 0)
    upload_date: datetime = datetime.fromtimestamp(upload_ts, tz=timezone.utc)

    # 封面 URL（v2 格式：path 字段包含相对路径）
    cover_data = data.get("cover", {})
    cover_path = cover_data.get("path", "")
    if cover_path:
        cover_url = f"{_THUMB_CDN}/{cover_path}"
    else:
        cover_url = ""

    # 逐页图片（v2 格式：pages 为列表，每项有 path/width/height/thumbnail）
    pages_data = data.get("pages", [])
    images: list[NhentaiImage] = []
    for page in pages_data:
        page_num = page.get("number", 0)
        img_path = page.get("path", "")
        thumb_path = page.get("thumbnail", "")
        ext = img_path.rsplit(".", 1)[-1] if "." in img_path else "jpg"
        images.append(
            NhentaiImage(
                page_num=page_num,
                url=f"{_IMAGE_CDN}/{img_path}" if img_path else "",
                thumbnail_url=f"{_THUMB_CDN}/{thumb_path}" if thumb_path else "",
                width=page.get("width", 0),
                height=page.get("height", 0),
                extension=ext,
            )
        )

    gallery_url = f"https://nhentai.net/g/{gallery_id}/"

    return NhentaiGallery(
        id=gallery_id,
        media_id=media_id,
        title_english=title_english,
        title_japanese=title_japanese,
        title_pretty=title_pretty,
        artists=artists,
        groups=groups,
        parodies=parodies,
        characters=characters,
        tags=tags,
        languages=languages,
        categories=categories,
        num_pages=num_pages,
        num_favorites=num_favorites,
        upload_date=upload_date,
        cover_url=cover_url,
        images=images,
        url=gallery_url,
    )


def parse_search_item(data: dict) -> NhentaiGallery:
    """将 v2 搜索结果中的精简 item 解析为 NhentaiGallery（部分字段为空）"""

    gallery_id: int = data["id"]
    media_id: str = str(data.get("media_id", ""))
    title_english = data.get("english_title", "") or ""
    title_japanese = data.get("japanese_title", "") or ""
    num_pages: int = data.get("num_pages", 0)

    thumb_path = data.get("thumbnail", "")
    cover_url = f"{_THUMB_CDN}/{thumb_path}" if thumb_path else ""

    gallery_url = f"https://nhentai.net/g/{gallery_id}/"

    return NhentaiGallery(
        id=gallery_id,
        media_id=media_id,
        title_english=title_english,
        title_japanese=title_japanese,
        title_pretty="",
        artists=[],
        groups=[],
        parodies=[],
        characters=[],
        tags=[],
        languages=[],
        categories=[],
        num_pages=num_pages,
        num_favorites=0,
        upload_date=datetime.fromtimestamp(0, tz=timezone.utc),
        cover_url=cover_url,
        images=[],
        url=gallery_url,
    )


def gallery_to_dict(gallery: NhentaiGallery) -> dict:
    """将 NhentaiGallery 对象序列化为可 JSON 导出的 dict"""
    return {
        "id": gallery.id,
        "media_id": gallery.media_id,
        "url": gallery.url,
        "title_english": gallery.title_english,
        "title_japanese": gallery.title_japanese,
        "title_pretty": gallery.title_pretty,
        "artists": gallery.artists,
        "groups": gallery.groups,
        "parodies": gallery.parodies,
        "characters": gallery.characters,
        "tags": gallery.tags,
        "languages": gallery.languages,
        "categories": gallery.categories,
        "num_pages": gallery.num_pages,
        "num_favorites": gallery.num_favorites,
        "upload_date": gallery.upload_date.isoformat(),
        "cover_url": gallery.cover_url,
        "images": [
            {
                "page_num": img.page_num,
                "url": img.url,
                "thumbnail_url": img.thumbnail_url,
                "width": img.width,
                "height": img.height,
                "extension": img.extension,
            }
            for img in gallery.images
        ],
    }
