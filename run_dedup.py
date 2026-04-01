"""
去重脚本：对 search_results.json 按合订本规则去重

规则：
1. 按 (基础作品名, 语言) 分组
2. 对于同组内的 "Ch. X" / "Ch. X-Y" 合订本条目：
   - 如果存在完整版（无 Ch. 标记且页数最多），保留完整版，移除所有 Ch. 条目
   - 如果只有 Ch. 条目，保留章节范围最大的那个（验证页数一致性）
3. 同组内标题几乎相同的（仅翻译组/版本不同），保留页数最多的
4. 不确定是否应该去重的，保留
"""

import json
import re
import sys
from pathlib import Path


class TeeOutput:
    """同时写入 stdout 和文件"""
    def __init__(self, filepath):
        self.file = open(filepath, "w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, text):
        self.stdout.write(text)
        self.file.write(text)

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()
        sys.stdout = self.stdout


def extract_language(title: str) -> str:
    """从标题中提取语言标签"""
    t = title.lower()
    if "[english]" in t:
        return "english"
    if "[chinese]" in t or "[chinese]" in t:
        return "chinese"
    return "unknown"


def extract_chapter_info(title: str) -> tuple[str, int | None, int | None]:
    """
    提取章节信息。返回 (去掉Ch.部分的标题, start_ch, end_ch)
    - 无章节标记 → (title, None, None) — 完整版
    - "Ch. 4"    → (base, 4, 4) — 单章
    - "Ch. 1-4"  → (base, 1, 4) — 合订本
    - "Ch.1-2"   → (base, 1, 2) — 合订本（无空格变体）
    """
    # 匹配 "Ch. X-Y" 或 "Ch.X-Y"（带范围）
    m = re.search(r'\bCh\.?\s*(\d+)\s*-\s*(\d+)\b', title, re.IGNORECASE)
    if m:
        stripped = title[:m.start()].rstrip() + title[m.end():]
        return stripped, int(m.group(1)), int(m.group(2))

    # 匹配 "Ch. X"（单章）
    m = re.search(r'\bCh\.?\s*(\d+)\b', title, re.IGNORECASE)
    if m:
        stripped = title[:m.start()].rstrip() + title[m.end():]
        return stripped, int(m.group(1)), int(m.group(1))

    return title, None, None


def normalize_base_name(title: str) -> str:
    """归一化基础作品名，用于分组比较"""
    t = title

    # 去掉作者前缀 [Tsubaki Jushiro] / [Tsubaki Jushirou] / [椿十四郎]
    t = re.sub(r'^\[.*?\]\s*', '', t)
    # 去掉 | 后的英文副标题
    t = re.sub(r'\s*\|.*?(?=\[|\(|$)', '', t)
    # 去掉 (...) 来源信息，如 (Aimai Diary), (Imouto Manual)
    t = re.sub(r'\s*\(.*?\)', '', t)
    # 去掉 [...] 方括号标签（包括未闭合的 [ ）
    t = re.sub(r'\s*\[.*?\]', '', t)
    t = re.sub(r'\s*\[[^\]]*$', '', t)  # 处理未闭合的 [xxx
    # 去掉 {...} 花括号标签
    t = re.sub(r'\s*\{.*?\}', '', t)
    # 去掉 Ch. X / Ch. X-Y
    t = re.sub(r'\bCh\.?\s*\d+(?:\s*-\s*\d+)?\b', '', t, flags=re.IGNORECASE)
    # 去掉 " - subtitle" 副标题（如 "Ane Megane - spectacled sister"）
    t = re.sub(r'\s+-\s+.*', '', t)
    # 去掉尾部标点和空格
    t = re.sub(r'[\s\-–—]+$', '', t)
    t = t.strip().lower()
    return t


def deduplicate(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    执行去重，返回 (保留列表, 被移除列表及原因)
    """
    # 第一步：按 (归一化名, 语言) 分组
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        title = item["title"]
        lang = extract_language(title)
        ch_stripped, start_ch, end_ch = extract_chapter_info(title)
        base = normalize_base_name(ch_stripped)

        item["_lang"] = lang
        item["_base"] = base
        item["_ch_start"] = start_ch
        item["_ch_end"] = end_ch
        item["_is_full"] = (start_ch is None)  # 无 Ch. 标记 = 完整版候选

        key = (base, lang)
        groups.setdefault(key, []).append(item)

    kept = []
    removed = []

    for (base, lang), group in sorted(groups.items()):
        if len(group) == 1:
            kept.append(group[0])
            continue

        # 分类：完整版 vs 合订/单章
        fulls = [g for g in group if g["_is_full"]]
        chapters = [g for g in group if not g["_is_full"]]

        print(f"\n{'='*80}")
        print(f"分组: base={base!r}  lang={lang}  共{len(group)}条")
        for g in group:
            ch_info = ""
            if g["_ch_start"] is not None:
                if g["_ch_start"] == g["_ch_end"]:
                    ch_info = f"  [Ch.{g['_ch_start']}]"
                else:
                    ch_info = f"  [Ch.{g['_ch_start']}-{g['_ch_end']}]"
            flag = " (完整版)" if g["_is_full"] else ""
            print(f"  ID={g['id']:>6}  页数={g['num_pages']:>3}{ch_info}{flag}  {g['title']}")

        # ---- 去重逻辑 ----

        # 情况1：有完整版存在
        if fulls:
            best_full = max(fulls, key=lambda g: g["num_pages"])
            max_ch_pages = max((g["num_pages"] for g in chapters), default=0)

            # 完整版应该页数 >= 所有合订本
            if best_full["num_pages"] >= max_ch_pages:
                # 移除所有 Ch. 条目（被完整版覆盖）
                for c in chapters:
                    removed.append({**c, "_reason": f"被完整版 ID={best_full['id']} ({best_full['num_pages']}p) 覆盖"})

                # 对于多个完整版：页数相近的全部保留待人工确认
                SIMILAR_THRESHOLD = 0.85  # 页数差距在 15% 以内视为相近
                min_similar_pages = best_full["num_pages"] * SIMILAR_THRESHOLD
                similar_fulls = [f for f in fulls if f["num_pages"] >= min_similar_pages]
                lesser_fulls = [f for f in fulls if f["num_pages"] < min_similar_pages]

                for f in lesser_fulls:
                    removed.append({**f, "_reason": f"页数明显少于同组最佳完整版 ID={best_full['id']} ({best_full['num_pages']}p)"})

                if len(similar_fulls) > 1:
                    kept.extend(similar_fulls)
                    print(f"  → 保留 {len(similar_fulls)} 个页数相近的完整版（待人工确认），移除 {len(chapters) + len(lesser_fulls)} 条")
                else:
                    kept.append(best_full)
                    print(f"  → 保留完整版 ID={best_full['id']} ({best_full['num_pages']}p)，移除 {len(group)-1} 条")
            else:
                # 异常：某个合订本页数比完整版还多 → 全部保留，标记警告
                print(f"  ⚠ 警告: 合订本页数({max_ch_pages}p) > 完整版({best_full['num_pages']}p)，全部保留")
                kept.extend(group)
            continue

        # 情况2：没有完整版，只有 Ch. 条目
        if chapters:
            # 找出章节范围最大的（end_ch 最大）
            best_ch = max(chapters, key=lambda g: (g["_ch_end"] or 0, g["num_pages"]))

            # 验证：最大范围的应该也是页数最多的
            max_pages_item = max(chapters, key=lambda g: g["num_pages"])

            if best_ch["num_pages"] >= max_pages_item["num_pages"] * 0.9:
                # 正常：range 最大的页数也最多（允许 10% 容差）
                kept.append(best_ch)
                for c in chapters:
                    if c is not best_ch:
                        removed.append({**c, "_reason": f"被更完整的合订本 ID={best_ch['id']} (Ch.{best_ch['_ch_start']}-{best_ch['_ch_end']}, {best_ch['num_pages']}p) 覆盖"})
                print(f"  → 保留合订本 ID={best_ch['id']} (Ch.{best_ch['_ch_start']}-{best_ch['_ch_end']}, {best_ch['num_pages']}p)，移除 {len(chapters)-1} 条")
            else:
                # 异常情况 → 保留范围最大的和页数最多的
                print(f"  ⚠ 警告: 范围最大的 Ch.{best_ch['_ch_start']}-{best_ch['_ch_end']} ({best_ch['num_pages']}p) 页数少于 ID={max_pages_item['id']} ({max_pages_item['num_pages']}p)")
                to_keep = {best_ch["id"], max_pages_item["id"]}
                for c in chapters:
                    if c["id"] in to_keep:
                        kept.append(c)
                    else:
                        removed.append({**c, "_reason": f"被 ID={best_ch['id']} 和 ID={max_pages_item['id']} 覆盖"})
                print(f"  → 保留 {len(to_keep)} 条，移除 {len(chapters)-len(to_keep)} 条")
            continue

        # 不应到达这里
        kept.extend(group)

    return kept, removed


def main():
    log_path = Path("output/dedup_log.txt")
    tee = TeeOutput(log_path)
    sys.stdout = tee

    data = json.loads(Path("output/search_results.json").read_text(encoding="utf-8"))
    print(f"输入: {len(data)} 条\n")

    kept, removed = deduplicate(data)

    # 清理内部字段
    for item in kept:
        for key in list(item.keys()):
            if key.startswith("_"):
                del item[key]

    kept.sort(key=lambda x: (x.get("title") or "").lower())

    print(f"\n{'='*80}")
    print(f"去重结果: {len(data)} → {len(kept)} 条 (移除 {len(removed)} 条)")
    print(f"{'='*80}")
    print(f"\n保留的作品:")
    print(f"{'序号':>4}  {'ID':>7}  {'页数':>4}  标题")
    print("-" * 120)
    for i, r in enumerate(kept, 1):
        print(f"{i:>4}  {r['id']:>7}  {r['num_pages']:>4}  {r['title']}")

    print(f"\n\n被移除的作品:")
    print(f"{'ID':>7}  {'页数':>4}  标题")
    print(f"{'':>7}  {'':>4}  原因")
    print("-" * 120)
    for r in removed:
        print(f"{r['id']:>7}  {r['num_pages']:>4}  {r['title']}")
        print(f"{'':>7}  {'':>4}  → {r['_reason']}")

    # 保存结果
    Path("output/deduped_results.json").write_text(
        json.dumps(kept, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n去重结果已保存到: output/deduped_results.json")
    print(f"去重日志已保存到: {log_path}")

    tee.close()


if __name__ == "__main__":
    main()
