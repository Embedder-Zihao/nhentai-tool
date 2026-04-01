# nhentai-tool

nhentai API 的 Python 封装工具，提供搜索、过滤、排序、导出和下载功能。

## 功能特性

- **API 客户端**：内置请求限速、自动重试（429/5xx 指数退避）、Session 复用
- **结构化数据模型**：将 API 返回的 JSON 解析为 Python dataclass 对象
- **丰富的过滤引擎**：支持按语言、标签、页数、收藏数、日期、艺术家、类型等维度过滤
- **去重**：按 ID 去重或按标题相似度去重
- **排序**：按收藏数、页数、日期、ID 排序
- **多种输出方式**：控制台摘要、JSON 导出、URL 列表导出、图片批量下载

## 项目结构

```
nhentai_tool/
├── __init__.py    # 包入口，导出所有公开 API
├── client.py      # API 客户端（HTTP 请求、限速、重试）
├── models.py      # 数据模型（NhentaiGallery, NhentaiImage）与 JSON 解析
├── filters.py     # 过滤引擎（去重、语言、标签、页数、收藏、日期、排序、管道）
└── main.py        # 主程序入口（搜索→过滤→输出 完整流程示例）
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

### 作为库导入使用

```python
from nhentai_tool import NhentaiClient, FilterPipeline, gallery_to_dict

# 1. 创建客户端
client = NhentaiClient(
    rate_limit=1.5,      # 请求间隔（秒）
    max_retries=3,       # 最大重试次数
    cookies=None,        # 可选：{"cf_clearance": "..."} 用于绕过 Cloudflare
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

# 批量下载图片到本地
download_galleries(client, filtered, "output/downloads", image_rate_limit=0.5)
```

### 下载目录结构

```
output/downloads/
├── 123456_作品标题/
│   ├── 001.jpg
│   ├── 002.jpg
│   └── ...
└── 789012_另一个作品/
    └── ...
```

- 自动跳过已存在的文件（支持断点续传）
- 文件名中的 Windows 非法字符会被替换为 `_`
- 目录名格式：`{id}_{标题前80字符}`

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

### Cloudflare 绕过

如果遇到 Cloudflare 防护，可以从浏览器中提取 `cf_clearance` cookie 后传入：

```python
client = NhentaiClient(cookies={"cf_clearance": "你的cookie值"})
```

### 限速设置

- `rate_limit`：API 请求间隔，默认 1.5 秒
- `image_rate_limit`（下载时）：图片下载间隔，默认 0.5 秒

## 许可证

MIT