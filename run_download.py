"""
下载脚本：根据 gallery ID 下载所有页面图片到 output/<作品名>/ 目录
支持多线程并发下载、多 CDN 轮询、断点续传
"""

import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from nhentai_tool.client import NhentaiClient
from nhentai_tool.models import get_image_cdn, NhentaiImage


def sanitize_dirname(title: str) -> str:
    """将标题转为合法的目录名"""
    # 替换 Windows 不允许的文件名字符
    name = re.sub(r'[<>:"/\\|?*]', '_', title)
    # 去掉首尾空格和点
    name = name.strip(' .')
    # 限制长度（Windows 路径限制）
    if len(name) > 200:
        name = name[:200].rstrip(' .')
    return name


def _download_one_image(
    session, img: NhentaiImage, filepath: Path, verify_ssl: bool
) -> tuple[int, bool, str]:
    """
    下载单张图片，返回 (page_num, success, message)。
    自动使用按页码轮询的 CDN 服务器。
    """
    # 替换 CDN 域名实现轮询
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


def download_gallery(
    client: NhentaiClient,
    gallery_id: int,
    output_base: Path,
    max_workers: int = 4,
) -> None:
    print(f"正在获取 gallery #{gallery_id} 的详情...")
    gallery = client.get_gallery(gallery_id)

    title = gallery.title_english or gallery.title_japanese or f"gallery_{gallery_id}"
    dirname = sanitize_dirname(title)
    dest_dir = output_base / dirname
    dest_dir.mkdir(parents=True, exist_ok=True)

    total = len(gallery.images)
    print(f"作品: {title}")
    print(f"页数: {total}")
    print(f"并发: {max_workers} 线程，CDN: i1-i4 轮询")
    print(f"保存到: {dest_dir}")
    print()

    # 筛选需要下载的图片（跳过已存在）
    tasks: list[tuple[NhentaiImage, Path]] = []
    skipped = 0
    for img in gallery.images:
        filename = f"{img.page_num:04d}.{img.extension}"
        filepath = dest_dir / filename
        if filepath.exists() and filepath.stat().st_size > 0:
            skipped += 1
        else:
            tasks.append((img, filepath))

    if skipped > 0:
        print(f"已跳过 {skipped} 个已存在文件")

    if not tasks:
        print("所有文件已存在，无需下载")
        return

    # 并发下载
    session = client.session
    completed = 0
    failed = []
    lock = threading.Lock()
    start_time = time.monotonic()

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
                    print(f"  [{completed + skipped}/{total}] {page_num:04d} ({msg})")
                else:
                    failed.append(page_num)
                    print(f"  [{completed + skipped}/{total}] {page_num:04d} 失败: {msg}")

    elapsed = time.monotonic() - start_time
    print(f"\n下载完成: {completed}/{len(tasks)} 页 ({elapsed:.1f}s)")
    if failed:
        failed.sort()
        print(f"失败的页面: {failed}")
    print(f"保存位置: {dest_dir}")


def download_batch(
    client: NhentaiClient,
    gallery_ids: list[int],
    output_base: Path,
    max_workers: int = 4,
) -> None:
    """批量下载多个 gallery"""
    total_galleries = len(gallery_ids)
    all_start = time.monotonic()

    for idx, gid in enumerate(gallery_ids, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{total_galleries}] Gallery #{gid}")
        print(f"{'='*60}")
        try:
            download_gallery(client, gid, output_base, max_workers=max_workers)
        except Exception as e:
            print(f"  下载失败: {e}，跳过")

    elapsed = time.monotonic() - all_start
    print(f"\n{'='*60}")
    print(f"全部完成: {total_galleries} 个作品，总耗时 {elapsed:.1f}s")
    print(f"{'='*60}")


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="nhentai gallery 下载器")
    parser.add_argument("source", help="gallery ID 或 JSON 文件路径")
    parser.add_argument("-o", "--output", default="output", help="输出目录 (默认: output)")
    parser.add_argument("-w", "--workers", type=int, default=4, help="并发线程数 (默认: 4)")
    args = parser.parse_args()

    output_base = Path(args.output)
    output_base.mkdir(parents=True, exist_ok=True)

    client = NhentaiClient(rate_limit=0.5, verify_ssl=False)

    # 判断输入是 JSON 文件还是 gallery ID
    source_path = Path(args.source)
    if source_path.exists() and source_path.suffix == ".json":
        data = json.loads(source_path.read_text(encoding="utf-8"))
        gallery_ids = [item["id"] for item in data]
        print(f"从 {args.source} 加载 {len(gallery_ids)} 个作品")
        download_batch(client, gallery_ids, output_base, max_workers=args.workers)
    else:
        gallery_id = int(args.source)
        download_gallery(client, gallery_id, output_base, max_workers=args.workers)


if __name__ == "__main__":
    main()
