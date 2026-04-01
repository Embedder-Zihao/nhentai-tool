# 模块2: models.py — 数据模型与解析
# 将 nhentai API 返回的原始 JSON 解析为结构化 Python dataclass 对象

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# nhentai 图片类型单字符 → 文件扩展名映射
EXT_MAP: dict[str, str] = {
    "j": "jpg",
    "p": "png",
    "g": "gif",
    "w": "webp",
    "a": "avif",
}


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
    """将 nhentai API 返回的单个 gallery JSON dict 解析为 NhentaiGallery 对象"""

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

    # 封面 URL（使用 cover 图的扩展名）
    images_block = data.get("images", {})
    cover_data = images_block.get("cover", {})
    cover_ext = EXT_MAP.get(cover_data.get("t", "j"), "jpg")
    cover_url = f"https://t.nhentai.net/galleries/{media_id}/cover.{cover_ext}"

    # 逐页图片
    pages_data = images_block.get("pages", [])
    images: list[NhentaiImage] = []
    for i, page in enumerate(pages_data, start=1):
        ext = EXT_MAP.get(page.get("t", "j"), "jpg")
        img_url = f"https://i.nhentai.net/galleries/{media_id}/{i}.{ext}"
        thumb_url = f"https://t.nhentai.net/galleries/{media_id}/{i}t.{ext}"
        images.append(
            NhentaiImage(
                page_num=i,
                url=img_url,
                thumbnail_url=thumb_url,
                width=page.get("w", 0),
                height=page.get("h", 0),
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
