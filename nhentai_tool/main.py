# 模块4: main.py — 主程序入口
# 将 client、models、filters 三个模块组装起来，提供完整的搜索→过滤→输出流程

from __future__ import annotations

import json
import logging
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

from .client import NhentaiClient
from .filters import FilterPipeline
from .models import NhentaiGallery, NhentaiImage, gallery_to_dict, get_image_cdn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# 输出函数
# ---------------------------------------------------------------------------

def print_summary(galleries: list[NhentaiGallery]) -> None:
    """控制台打印格式化摘要信息"""
    print(f"\n{'=' * 60}")
    print(f"共 {len(galleries)} 个结果")
    print(f"{'=' * 60}")
    for i, g in enumerate(galleries, start=1):
        artists_str = ", ".join(g.artists) if g.artists else "未知"
        langs_str = ", ".join(g.languages) if g.languages else "未知"
        print(
            f"[{i:>3}] ID={g.id}  页数={g.num_pages}  收藏={g.num_favorites}\n"
            f"      标题: {g.title_english or g.title_pretty or g.title_japanese}\n"
            f"      艺术家: {artists_str}  语言: {langs_str}\n"
            f"      URL: {g.url}"
        )
    print(f"{'=' * 60}\n")


def export_json(galleries: list[NhentaiGallery], filepath: str | os.PathLike) -> None:
    """将过滤后的元数据导出为 .json 文件"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    data = [gallery_to_dict(g) for g in galleries]
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[导出] JSON 已保存至: {filepath}  ({len(data)} 条)")


def export_urls(galleries: list[NhentaiGallery], filepath: str | os.PathLike) -> None:
    """将所有图片 URL 导出为 .txt 文件（每行一个 URL）"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with filepath.open("w", encoding="utf-8") as f:
        for g in galleries:
            for img in g.images:
                f.write(img.url + "\n")
                total += 1
    print(f"[导出] URL 列表已保存至: {filepath}  ({total} 条)")


def _download_one_image(
    session: requests.Session,
    img: NhentaiImage,
    filepath: Path,
    verify_ssl: bool,
) -> tuple[int, bool, str]:
    """下载单张图片，返回 (page_num, success, message)"""
    cdn = get_image_cdn(img.page_num)
    url = re.sub(r'https://i\d\.nhentai\.net', cdn, img.url)

    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30, verify=verify_ssl)
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            size_kb = len(resp.content) / 1024
            return img.page_num, True, f"{size_kb:.0f} KB"
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                return img.page_num, False, str(e)
    return img.page_num, False, "unknown error"


def download_galleries(
    client: NhentaiClient,
    galleries: list[NhentaiGallery],
    output_dir: str | os.PathLike,
    max_workers: int = 4,
) -> None:
    """
    将过滤后的作品图片并发下载到本地。

    目录结构: output_dir/{id}_{safe_title}/{page_num:03d}.{ext}
    自动跳过已存在的文件，支持多线程并发和多 CDN 轮询。
    """
    output_dir = Path(output_dir)
    session = client.session

    for g in galleries:
        safe_title = "".join(
            c if c not in r'\/:*?"<>|' else "_"
            for c in (g.title_pretty or g.title_english or str(g.id))
        )[:80]
        gallery_dir = output_dir / f"{g.id}_{safe_title}"
        gallery_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[下载] ID={g.id}  标题: {g.title_pretty or g.title_english}")

        tasks: list[tuple[NhentaiImage, Path]] = []
        for img in g.images:
            filename = f"{img.page_num:03d}.{img.extension}"
            dest = gallery_dir / filename
            if not dest.exists():
                tasks.append((img, dest))

        if not tasks:
            print(f"  所有 {g.num_pages} 页已存在，跳过")
            continue

        completed = 0
        failed = []
        lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _download_one_image, session, img, filepath, client.verify_ssl
                ): img.page_num
                for img, filepath in tasks
            }
            for future in as_completed(futures):
                page_num, success, msg = future.result()
                with lock:
                    if success:
                        completed += 1
                        print(f"  [{completed}/{len(tasks)}] p{page_num:03d} ({msg})")
                    else:
                        failed.append(page_num)
                        print(f"  [错误] p{page_num:03d}: {msg}")

        status = f"{completed}/{len(tasks)}"
        if failed:
            status += f" (失败: {sorted(failed)})"
        print(f"  完成: {status}")

    print("\n[下载] 全部完成")


# ---------------------------------------------------------------------------
# main() — 完整使用示例
# ---------------------------------------------------------------------------

def main() -> None:
    """演示完整的搜索 → 过滤 → 输出流程"""

    # ----------------------------------------------------------------
    # 1. 配置搜索关键词（支持多个）
    # ----------------------------------------------------------------
    keywords = ["sole female english"]

    # ----------------------------------------------------------------
    # 2. 配置过滤规则
    # ----------------------------------------------------------------
    filter_config = {
        "dedupe": "both",                             # 先按 ID 去重，再按标题去重
        "languages": {"include": ["english", "chinese"]},
        "tags_exclude": ["guro", "yaoi", "scat"],
        "tags_include_any": [],
        "tags_include_all": [],
        "pages": {"min": 10, "max": 200},
        "favorites": {"min": 100},
        "date": {"after": "2020-01-01"},
        "categories": {"include": ["doujinshi", "manga"]},
        "sort": {"key": "favorites", "reverse": True},
    }

    # ----------------------------------------------------------------
    # 3. 初始化客户端
    #    如果需要绕过 Cloudflare，在此传入 cookies={"cf_clearance": "..."}
    # ----------------------------------------------------------------
    client = NhentaiClient(rate_limit=1.5, max_retries=3)

    # ----------------------------------------------------------------
    # 4. 搜索所有关键词并合并结果
    # ----------------------------------------------------------------
    all_galleries: list[NhentaiGallery] = []
    for kw in keywords:
        print(f"\n[搜索] 关键词: {kw!r}")
        results = client.search_all(kw, max_pages=3)
        print(f"[搜索] 获取 {len(results)} 条原始结果")
        all_galleries.extend(results)

    print(f"\n[合并] 所有关键词共 {len(all_galleries)} 条原始结果（含重复）")

    # ----------------------------------------------------------------
    # 5. 构建过滤管道并执行过滤
    # ----------------------------------------------------------------
    pipeline = FilterPipeline.from_config(filter_config)
    filtered = pipeline.apply(all_galleries)

    # ----------------------------------------------------------------
    # 6. 输出结果
    # ----------------------------------------------------------------
    print_summary(filtered)
    export_json(filtered, "output/results.json")
    # export_urls(filtered, "output/urls.txt")
    # download_galleries(client, filtered, "output/downloads")


if __name__ == "__main__":
    main()
