# nhentai-tool

nhentai v2 API 的 Python 封装工具，提供搜索、过滤、排序、去重、导出和批量下载功能。

## 功能特性

- **v2 API 客户端**：基于 nhentai v2 API，内置请求限速、自动重试（429/5xx 指数退避）、Session 复用
- **结构化数据模型**：将 API 返回的 JSON 解析为 Python dataclass 对象
- **多 CDN 支持**：轮询 i1-i4 CDN 服务器，分散请求压力
- **多线程并发下载**：基于 ThreadPoolExecutor 的并发下载，支持断点续传
- **丰富的过滤引擎**：支持按语言、标签、页数、收藏数、日期、艺术家、类型等维度过滤
- **智能去重**：按 ID/标题相似度去重，支持合订本（Ch. X-Y）识别与合并
- **排序**：按收藏数、页数、日期、ID 排序
- **多种输出方式**：控制台摘要、JSON 导出、URL 列表导出、图片批量下载
- **独立脚本**：提供开箱即用的下载脚本和去重脚本

## 项目结构

```
nhentai_tool/
├── __init__.py      # 包入口，导出所有公开 API
├── client.py        # v2 API 客户端（HTTP 请求、限速、重试）
├── models.py        # 数据模型（NhentaiGallery, NhentaiImage）与 JSON 解析、多 CDN 轮询
├── filters.py       # 过滤引擎（去重、语言、标签、页数、收藏、日期、排序、管道）
└── main.py          # 主程序入口（搜索→过滤→输出 完整流程示例）

run_download.py      # 独立下载脚本（支持单个 ID / JSON 批量下载）
run_dedup.py         # 独立去重脚本（合订本识别、标题归一化、相似度去重）
```

## 安装

### 环境要求

- Python 3.10+（使用了 `X | Y` 类型联合语法）

### 安装依赖

```bash
pip install -r requirements.txt
```

唯一的第三方依赖是 `requests`。

## 快速开始

### 作为脚本直接运行

编辑 `nhentai_tool/main.py` 中的 `main()` 函数，修改关键词和过滤配置后运行：

```bash
python -m nhentai_tool.main
```

### 使用独立下载脚本

```bash
# 下载单个作品
python run_download.py 428809

# 下载单个作品到指定目录，使用 8 线程
python run_download.py 428809 -o output/downloads -w 8

# 从 JSON 文件批量下载（JSON 格式: [{"id": 123456}, {"id": 789012}, ...]）
python run_download.py output/search_results.json -o output/作者名 -w 4
```

### 使用独立去重脚本

```bash
# 对搜索结果进行智能去重（合订本识别、标题归一化）
python run_dedup.py
# 输入: output/search_results.json
# 输出: output/deduped_results.json + output/dedup_log.txt
```

### 作为库导入使用

```python
from nhentai_tool import NhentaiClient, FilterPipeline, gallery_to_dict

# 1. 创建客户端
client = NhentaiClient(
    rate_limit=1.5,      # 请求间隔（秒）
    max_retries=3,       # 最大重试次数
    cookies=None,        # 可选：{"cf_clearance": "..."} 用于绕过 Cloudflare
    verify_ssl=False,    # nhentai 当前需要禁用 SSL 验证
)

# 2. 搜索
galleries, total_pages = client.search("sole female english", page=1)

# 3. 自动翻页搜索（获取多页结果）
all_results = client.search_all("sole female english", max_pages=3)

# 4. 获取单个作品详情
gallery = client.get_gallery(123456)
```

## 过滤系统

### 使用 FilterPipeline（推荐）

通过配置字典构建过滤管道，一次性执行所有过滤步骤：

```python
from nhentai_tool import FilterPipeline

config = {
    "dedupe": "both",                                # "id" / "title" / "both"
    "languages": {"include": ["english", "chinese"]},
    "tags_exclude": ["guro", "yaoi", "scat"],        # 排除含这些标签的作品
    "tags_include_any": [],                           # 包含任一标签即保留
    "tags_include_all": [],                           # 必须包含所有标签
    "pages": {"min": 10, "max": 200},                # 页数范围
    "favorites": {"min": 100},                        # 最低收藏数
    "date": {"after": "2020-01-01"},                  # 上传日期范围
    "categories": {"include": ["doujinshi", "manga"]},
    "sort": {"key": "favorites", "reverse": True},    # 排序
}

pipeline = FilterPipeline.from_config(config)
filtered = pipeline.apply(all_results)
```

### 手动链式调用

也可以手动组装过滤管道：

```python
from nhentai_tool import (
    FilterPipeline, dedupe_by_id, filter_languages,
    filter_tags_exclude, filter_pages, sort_by,
)

pipeline = FilterPipeline()
pipeline.add(dedupe_by_id)
pipeline.add(filter_languages, include={"english"})
pipeline.add(filter_tags_exclude, tags={"guro", "yaoi"})
pipeline.add(filter_pages, min_pages=10, max_pages=200)
pipeline.add(sort_by, key="favorites", reverse=True)

filtered = pipeline.apply(all_results)
```

### 单独使用过滤函数

每个过滤函数都可以独立调用：

```python
from nhentai_tool import filter_languages, filter_favorites, sort_by

results = filter_languages(galleries, include={"english"})
results = filter_favorites(results, min_favs=100)
results = sort_by(results, key="date", reverse=True)
```

### 可用过滤函数一览

| 函数 | 说明 |
|------|------|
| `dedupe_by_id` | 按 ID 去重 |
| `dedupe_by_title` | 按标题相似度去重（保留收藏最高的） |
| `filter_languages` | 只保留包含指定语言的作品 |
| `exclude_languages` | 排除包含指定语言的作品 |
| `filter_tags_include_all` | 必须包含所有指定标签 |
| `filter_tags_include_any` | 包含任一指定标签即保留 |
| `filter_tags_exclude` | 排除包含任一指定标签的作品 |
| `filter_pages` | 按页数范围过滤 |
| `filter_favorites` | 按最低收藏数过滤 |
| `filter_date` | 按上传日期范围过滤 |
| `filter_artists` | 只保留指定艺术家的作品 |
| `filter_categories` | 只保留指定类型的作品 |
| `sort_by` | 排序（支持 `favorites` / `pages` / `date` / `id`） |

## 输出方式

```python
from nhentai_tool.main import print_summary, export_json, export_urls, download_galleries

# 控制台打印摘要
print_summary(filtered)

# 导出元数据为 JSON
export_json(filtered, "output/results.json")

# 导出所有图片 URL 列表
export_urls(filtered, "output/urls.txt")

# 批量下载图片到本地（多线程并发 + CDN 轮询）
download_galleries(client, filtered, "output/downloads", max_workers=4)
```

### 下载特性

- **多线程并发**：默认 4 线程，通过 `max_workers` 参数调整
- **多 CDN 轮询**：自动轮询 i1-i4.nhentai.net 服务器，分散请求压力
- **断点续传**：自动跳过已存在的文件
- **自动重试**：每张图片失败后自动重试 3 次（指数退避）
- **文件名安全**：Windows 非法字符自动替换为 `_`

### 下载目录结构

```
output/downloads/
├── [Artist] Title of the Work/
│   ├── 0001.jpg
│   ├── 0002.jpg
│   └── ...
└── [Artist] Another Work/
    └── ...
```

## 数据模型

### NhentaiGallery

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 作品 ID |
| `media_id` | `str` | 媒体 ID |
| `title_english` | `str` | 英文标题 |
| `title_japanese` | `str` | 日文标题 |
| `title_pretty` | `str` | 简短标题 |
| `artists` | `list[str]` | 艺术家列表 |
| `groups` | `list[str]` | 社团列表 |
| `parodies` | `list[str]` | 原作列表 |
| `characters` | `list[str]` | 角色列表 |
| `tags` | `list[str]` | 标签列表 |
| `languages` | `list[str]` | 语言列表 |
| `categories` | `list[str]` | 类型列表 |
| `num_pages` | `int` | 页数 |
| `num_favorites` | `int` | 收藏数 |
| `upload_date` | `datetime` | 上传时间（UTC） |
| `cover_url` | `str` | 封面 URL |
| `images` | `list[NhentaiImage]` | 各页图片列表 |
| `url` | `str` | 作品页面 URL |

### NhentaiImage

| 字段 | 类型 | 说明 |
|------|------|------|
| `page_num` | `int` | 页码（从 1 开始） |
| `url` | `str` | 完整图片 URL |
| `thumbnail_url` | `str` | 缩略图 URL |
| `width` | `int` | 宽度 |
| `height` | `int` | 高度 |
| `extension` | `str` | 文件扩展名 |

## 客户端配置

### SSL 验证

nhentai 当前存在 SSL 证书问题，建议创建客户端时禁用 SSL 验证：

```python
client = NhentaiClient(verify_ssl=False)
```

### Cloudflare 绕过

如果遇到 Cloudflare 防护，可以从浏览器中提取 `cf_clearance` cookie 后传入：

```python
client = NhentaiClient(cookies={"cf_clearance": "你的cookie值"})
```

### 限速设置

- `rate_limit`：API 请求间隔，默认 1.5 秒

## 去重脚本 (run_dedup.py)

`run_dedup.py` 针对同一作者的搜索结果进行智能去重，支持以下规则：

1. **合订本识别**：识别标题中的 `Ch. X` / `Ch. X-Y` 章节标记
2. **标题归一化**：去除作者名、翻译组名、版本标记等，提取基础作品名
3. **分组去重**：按 (基础作品名, 语言) 分组
   - 存在完整版时，移除所有单章节条目
   - 仅有单章节时，保留章节范围最大的版本
   - 页数相近（≥85%）的多个版本保留待人工确认
4. **输出**：去重后的 JSON + 详细决策日志

## API 说明

本工具使用 nhentai v2 API：

| 端点 | 说明 |
|------|------|
| `GET /api/v2/search?query=...&sort=...&page=...` | 搜索作品 |
| `GET /api/v2/galleries/{id}` | 获取作品详情 |

## 许可证

MIT