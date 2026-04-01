# 模块1: client.py — API 客户端
# 封装 nhentai API 的 HTTP 请求，内置请求限速、自动重试、Session 复用

from __future__ import annotations

import time
import logging
from typing import Optional

import urllib3

import requests

from .models import NhentaiGallery, parse_gallery, parse_search_item

logger = logging.getLogger(__name__)

_BASE_URL = "https://nhentai.net"
_SEARCH_URL = f"{_BASE_URL}/api/v2/search"
_GALLERY_URL = f"{_BASE_URL}/api/v2/galleries"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0"
    ),
    "Accept": "application/json",
    "Referer": "https://nhentai.net/",
}


class NhentaiClient:
    """nhentai API 客户端，支持请求限速、自动重试和 Session 复用"""

    def __init__(
        self,
        rate_limit: float = 1.5,
        max_retries: int = 3,
        cookies: Optional[dict] = None,
        verify_ssl: bool = True,
    ) -> None:
        """
        参数:
            rate_limit:  每次请求之间的最小间隔（秒），默认 1.5 秒
            max_retries: 遇到 429/5xx 时的最大重试次数，默认 3 次
            cookies:     可选的 cookies dict，用于绕过 Cloudflare 等防护
            verify_ssl:  是否验证 SSL 证书，默认 True；如遇 SSL 错误可设为 False
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl

        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._session = requests.Session()
        self._session.headers.update(_DEFAULT_HEADERS)
        if cookies:
            self._session.cookies.update(cookies)

        self._last_request_time: float = 0.0

    @property
    def session(self) -> requests.Session:
        """返回内部的 requests.Session，供外部复用（如下载图片时）"""
        return self._session

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """在相邻请求之间强制等待，实现限速"""
        elapsed = time.monotonic() - self._last_request_time
        wait = self.rate_limit - elapsed
        if wait > 0:
            time.sleep(wait)

    def _request(self, url: str, params: Optional[dict] = None) -> dict:
        """发送 GET 请求并返回 JSON 结果，遇到 429/5xx 时指数退避重试"""
        self._throttle()

        for attempt in range(self.max_retries + 1):
            try:
                self._last_request_time = time.monotonic()
                resp = self._session.get(url, params=params, timeout=30, verify=self.verify_ssl)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 429 or resp.status_code >= 500:
                    backoff = 2 ** attempt
                    logger.warning(
                        "HTTP %d for %s — 第 %d 次重试，等待 %d 秒",
                        resp.status_code,
                        url,
                        attempt + 1,
                        backoff,
                    )
                    if attempt < self.max_retries:
                        time.sleep(backoff)
                        continue

                resp.raise_for_status()

            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    logger.warning(
                        "请求异常 %s — 第 %d 次重试，等待 %d 秒",
                        exc,
                        attempt + 1,
                        backoff,
                    )
                    time.sleep(backoff)
                else:
                    raise

        raise RuntimeError(f"超过最大重试次数，URL: {url}")

    # ------------------------------------------------------------------
    # 公开 API 方法
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        page: int = 1,
        sort: str = "",
    ) -> tuple[list[NhentaiGallery], int]:
        """
        搜索单页。

        返回:
            (galleries, total_pages) 元组
        """
        params: dict = {"query": query, "page": page}
        if sort:
            params["sort"] = sort

        data = self._request(_SEARCH_URL, params=params)

        galleries = [parse_search_item(item) for item in data.get("result", [])]
        total_pages: int = int(data.get("num_pages", 1))
        return galleries, total_pages

    def search_all(
        self,
        query: str,
        max_pages: Optional[int] = None,
        sort: str = "",
    ) -> list[NhentaiGallery]:
        """
        自动翻页搜索，返回所有结果。

        参数:
            query:     搜索关键词
            max_pages: 最多抓取页数，None 表示全部
            sort:      排序方式（空字符串表示默认）
        """
        all_galleries: list[NhentaiGallery] = []
        page = 1

        while True:
            logger.info("搜索第 %d 页，关键词: %s", page, query)
            galleries, total_pages = self.search(query, page=page, sort=sort)
            all_galleries.extend(galleries)

            if page >= total_pages:
                break
            if max_pages is not None and page >= max_pages:
                break
            page += 1

        logger.info(
            "关键词 '%s' 共获取 %d 个结果（%d 页）",
            query,
            len(all_galleries),
            page,
        )
        return all_galleries

    def get_gallery(self, gallery_id: int) -> NhentaiGallery:
        """获取单个 gallery 的详情"""
        url = f"{_GALLERY_URL}/{gallery_id}"
        data = self._request(url)
        return parse_gallery(data)
