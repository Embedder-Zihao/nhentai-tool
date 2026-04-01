"""
下载脚本：根据 gallery ID 下载所有页面图片到 output/<作品名>/ 目录
"""

import re
import sys
import time
from pathlib import Path

from nhentai_tool.client import NhentaiClient


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


def download_gallery(client: NhentaiClient, gallery_id: int, output_base: Path) -> None:
    print(f"正在获取 gallery #{gallery_id} 的详情...")
    gallery = client.get_gallery(gallery_id)

    title = gallery.title_english or gallery.title_japanese or f"gallery_{gallery_id}"
    dirname = sanitize_dirname(title)
    dest_dir = output_base / dirname
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"作品: {title}")
    print(f"页数: {gallery.num_pages}")
    print(f"保存到: {dest_dir}")
    print()

    session = client.session
    total = len(gallery.images)
    failed = []

    for img in gallery.images:
        page_num = img.page_num
        filename = f"{page_num:04d}.{img.extension}"
        filepath = dest_dir / filename

        if filepath.exists() and filepath.stat().st_size > 0:
            print(f"  [{page_num}/{total}] 已存在，跳过")
            continue

        for attempt in range(3):
            try:
                client._throttle()
                client._last_request_time = time.monotonic()
                resp = session.get(img.url, timeout=30, verify=client.verify_ssl)
                resp.raise_for_status()

                filepath.write_bytes(resp.content)
                size_kb = len(resp.content) / 1024
                print(f"  [{page_num}/{total}] {filename} ({size_kb:.0f} KB)")
                break
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    print(f"  [{page_num}/{total}] 下载失败: {e}，{wait}秒后重试...")
                    time.sleep(wait)
                else:
                    print(f"  [{page_num}/{total}] 下载失败: {e}，已跳过")
                    failed.append(page_num)

    print(f"\n下载完成: {total - len(failed)}/{total} 页")
    if failed:
        print(f"失败的页面: {failed}")
    print(f"保存位置: {dest_dir}")


def main():
    gallery_id = int(sys.argv[1]) if len(sys.argv) > 1 else 428809
    output_base = Path("output")
    output_base.mkdir(exist_ok=True)

    client = NhentaiClient(rate_limit=0.5, verify_ssl=False)
    download_gallery(client, gallery_id, output_base)


if __name__ == "__main__":
    main()
