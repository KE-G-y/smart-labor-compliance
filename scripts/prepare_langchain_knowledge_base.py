#!/usr/bin/env python3
"""Prepare source materials for LangChain/Milvus vector indexing.

The script reads the provided knowledge package, deduplicates equivalent
artifacts, and writes normalized Markdown files plus manifests. It intentionally
stores source paths relative to the package root so generated files are portable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


DEFAULT_OUTPUT_DIR = Path("knowledge_base/langchain_vector_import")
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk", "big5")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MOJIBAKE_MARKERS_RE = re.compile(r"[\u0080-\u009fÃÂÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ]")
CHINESE_TEXT_RE = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")
WEB_BOILERPLATE_LINES = {
    "中国政府网",
    "人力资源和社会保障部",
    "陕西省人民政府",
    "陕西省人力资源和社会保障厅",
    "陕西省医疗保障局",
    "西安市人力资源和社会保障局",
    "新媒体分享",
    "登录",
    "注册",
    "搜索",
    "首页",
    "正文",
    ">",
    "简体",
    "繁体",
    "网站首页",
    "新闻中心",
    "政府信息公开",
    "政策法规",
    "办事服务",
    "互动交流",
    "全部",
    "标题",
    "全文",
    "当前位置",
    "简",
    "繁",
    "无障碍",
    "适老版",
    "微信矩阵",
    "机构概况",
    "政务公开",
    "政民互动",
    "机关党建",
    "廉政纪检",
    "专题专栏",
    "医保要闻",
    "省医保动态",
    "政策法规数据库",
    "规范性文件",
    "通知公告",
    "分享：",
    "扫一扫：分享至微信",
    "扫一扫在手机打开当前页",
    "关闭",
    "X",
}
WEB_FOOTER_START_LINES = {
    "相关新闻",
    "附件下载",
    "相关稿件",
    "国家部委网站",
    "省直部门网站",
    "省级人社部门网站",
    "地市人社局网站",
    "中央人民政府门户网站",
    "陕西省人民政府门户网站",
    "国家医疗保障局",
    "省级医疗保障局",
    "市级医疗保障局",
    "联系我们",
    "网站地图",
}
WEB_FOOTER_PREFIXES = (
    "版权所有：",
    "主办单位:",
    "主办单位：",
    "联系电话:",
    "联系电话：",
    "联系方式：",
    "网站标识码",
    "陕ICP备",
    "陕公网安备",
    "网站支持IPV6",
)
MARKDOWN_BLOCK_LINE_RE = re.compile(r"^\s*(#{1,6}\s+|[-*]\s+|\d+[.、]\s+|\|)")
SENTENCE_END_RE = re.compile(r"[。！？!?；;：:]$")
WRAPPED_LINE_CONTINUATION_PREFIX_RE = re.compile(r"^[，。、；：！？）】》%％/]|^(元|月|日|年|个|名|人|厅|局|APP|小程序)")
GENERATED_BODY_SECTION_HEADINGS = {
    "来源元数据",
    "元数据",
    "入库提示",
    "文档元数据",
    "入库说明",
    "入库建议",
    "本地资料位置",
}
GENERATED_BODY_LINE_PREFIXES = ("来源URL", "抓取日期", "页面标题")


@dataclass
class PreparedDocument:
    document_id: str
    title: str
    kb_category: str
    doc_type: str
    region: str
    issuer: str
    publish_date: str
    effective_date: str
    validity_status: str
    review_status: str
    source_ids: str
    url: str
    prepared_file: str
    source_relative_path: str
    sha256: str
    characters: int
    vector_priority: int
    notes: str


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return normalize_text(" ".join(self._parts))


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return repair_latin1_mojibake(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return repair_latin1_mojibake(raw.decode("utf-8", errors="ignore"))


def repair_latin1_mojibake(text: str) -> str:
    """修复 UTF-8 中文被当成 Latin-1 读出来后的乱码。

    例如“西安”会变成“è¥¿å®”。这里按片段尝试还原，避免影响已经正常
    的中文标题、元数据和人工整理摘要。
    """

    parts: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        segment = "".join(buffer)
        parts.append(repair_latin1_segment(segment))
        buffer.clear()

    for char in text:
        if ord(char) <= 255:
            buffer.append(char)
        else:
            flush()
            parts.append(char)
    flush()
    return "".join(parts)


def repair_latin1_segment(segment: str) -> str:
    if not MOJIBAKE_MARKERS_RE.search(segment):
        return segment
    try:
        repaired = segment.encode("latin1").decode("utf-8")
    except UnicodeError:
        return segment
    if len(CHINESE_TEXT_RE.findall(repaired)) <= len(CHINESE_TEXT_RE.findall(segment)):
        return segment
    return repaired


def mojibake_marker_count(text: str) -> int:
    return len(MOJIBAKE_MARKERS_RE.findall(text))


def looks_like_mojibake(text: str) -> bool:
    """判断文本是否仍保留大量乱码标记。"""

    if not text:
        return False
    marker_count = mojibake_marker_count(text)
    return marker_count >= 20 and marker_count / len(text) >= 0.02


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_web_boilerplate(text: str) -> str:
    lines = []
    previous = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            previous = ""
            continue
        if line in WEB_FOOTER_START_LINES or any(line.startswith(prefix) for prefix in WEB_FOOTER_PREFIXES):
            break
        if line in WEB_BOILERPLATE_LINES:
            continue
        if line == previous:
            continue
        lines.append(line)
        previous = line
    return normalize_text("\n".join(lines))


def should_join_wrapped_lines(current: str, next_line: str) -> bool:
    if not current or not next_line:
        return False
    if MARKDOWN_BLOCK_LINE_RE.match(current) or MARKDOWN_BLOCK_LINE_RE.match(next_line):
        return False
    if SENTENCE_END_RE.search(current):
        return False
    if WRAPPED_LINE_CONTINUATION_PREFIX_RE.match(next_line):
        return True
    if len(current) <= 2 and CHINESE_TEXT_RE.search(current) and CHINESE_TEXT_RE.search(next_line):
        return True
    if len(next_line) <= 3 and CHINESE_TEXT_RE.search(current) and CHINESE_TEXT_RE.search(next_line):
        return True
    if re.search(r"[A-Za-z0-9]$", current) and re.match(r"^[A-Za-z0-9%％/]", next_line):
        return True
    if current.endswith(("、", "，", ",", "（", "(", "和", "与", "及", "为", "按", "由", "在", "从", "每")):
        return True
    return False


def repair_wrapped_lines(text: str) -> str:
    repaired: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if repaired and should_join_wrapped_lines(repaired[-1], line):
            repaired[-1] = repaired[-1] + line
        else:
            repaired.append(raw_line)
    return "\n".join(repaired)


def slugify(value: str, fallback: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value.strip())
    value = re.sub(r"\s+", "_", value)
    value = value.strip("._")
    return value or fallback


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def yaml_quote(value: object) -> str:
    text = "" if value is None else str(value)
    return json.dumps(text, ensure_ascii=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def package_relative(path: Path, source_root: Path) -> str:
    return path.relative_to(source_root).as_posix()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def resolve_package_path(source_root: Path, raw_path: str) -> Path:
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("资料/"):
        normalized = normalized[len("资料/") :]
    return source_root / normalized


def parse_docx(path: Path) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)
    body = root.find("w:body", namespace)
    if body is None:
        return ""

    parts: list[str] = []
    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = paragraph_text(child, namespace)
            if text:
                parts.append(text)
        elif tag == "tbl":
            table = table_markdown(child, namespace)
            if table:
                parts.append(table)
    return normalize_text("\n\n".join(parts))


def paragraph_text(node, namespace: dict[str, str]) -> str:
    texts: list[str] = []
    for item in node.findall(".//w:t", namespace):
        if item.text:
            texts.append(item.text)
    return normalize_text("".join(texts))


def table_markdown(node, namespace: dict[str, str]) -> str:
    rows: list[list[str]] = []
    for row in node.findall(".//w:tr", namespace):
        cells: list[str] = []
        for cell in row.findall("./w:tc", namespace):
            text = normalize_text(" ".join(paragraph_text(p, namespace) for p in cell.findall(".//w:p", namespace)))
            cells.append(text.replace("\n", " "))
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def parse_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt", ".csv", ".sql"}:
        return read_text(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix in {".html", ".htm"}:
        parser = HTMLTextExtractor()
        parser.feed(read_text(path))
        return parser.text()
    raise ValueError(f"Unsupported source format: {path.suffix}")


def find_text_alternative(source_root: Path, source_id: str) -> Path | None:
    matches = sorted(source_root.glob(f"**/TXT文本/{source_id}_*.txt"))
    return matches[0] if matches else None


def choose_source_path(preferred_path: Path, text_path: Path | None) -> Path:
    """选择更适合入库的来源文件。

    TXT 通常更干净；但个别抓取 TXT 已经乱码时，回退到 sources.csv
    指向的原始 HTML/DOCX，避免把坏文本写进向量库。
    """

    if text_path is None:
        return preferred_path
    if not preferred_path.exists() or text_path == preferred_path:
        return text_path
    if looks_like_mojibake(read_text(text_path)):
        return preferred_path
    return text_path


def build_summary_map(source_root: Path) -> dict[str, list[tuple[Path, str]]]:
    summary_map: dict[str, list[tuple[Path, str]]] = {}
    for path in sorted(source_root.glob("**/*.md")):
        if ".DS_Store" in path.name:
            continue
        normalized_path = path.as_posix()
        if "知识卡/Markdown文档" not in normalized_path and "办事指南/Markdown文档" not in normalized_path:
            continue
        text = read_text(path)
        match = re.search(r"来源编号[：:]\s*([A-Z]+\d+)", text)
        if not match:
            continue
        source_id = match.group(1)
        summary_map.setdefault(source_id, []).append((path, text))
    return summary_map


def shift_markdown_headings(text: str, levels: int = 2) -> str:
    lines = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            count = min(6, len(match.group(1)) + levels)
            lines.append("#" * count + " " + match.group(2))
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def category_for_source(source_type: str, source_id: str) -> str:
    if source_id.startswith("LAW"):
        return "national_law"
    if source_id.startswith("SX"):
        return "shaanxi_policy"
    if source_id.startswith("XA"):
        return "xian_service_rule"
    if "企业" in source_type:
        return "company_policy"
    return "reference"


def metadata_table(items: Iterable[tuple[str, str]]) -> str:
    lines = ["| 字段 | 内容 |", "| --- | --- |"]
    for key, value in items:
        lines.append(f"| {key} | {value or '-'} |")
    return "\n".join(lines)


def frontmatter(items: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in items.items():
        lines.append(f"{key}: {yaml_quote(value)}")
    lines.append("---")
    return "\n".join(lines)


def split_source_ids(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;，；]+", value or "") if item.strip()]


def build_source_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = row.get("source_id", "").strip()
        if source_id:
            lookup[source_id] = row
    return lookup


def format_external_source_links(source_ids: str, source_lookup: dict[str, dict[str, str]]) -> tuple[str, str, str]:
    lines: list[str] = []
    references: list[str] = []
    first_url = ""
    for source_id in split_source_ids(source_ids):
        source = source_lookup.get(source_id)
        if not source:
            continue
        url = source.get("url", "").strip()
        if not url:
            continue
        if not first_url:
            first_url = url
        title = source.get("title", source_id).strip() or source_id
        lines.append(f"- {source_id}：{title}（官方来源）{url}")
        references.append(f"{source_id}: {url}")
    if not lines:
        return "", "", ""
    return "\n".join(lines), "; ".join(references), first_url


def clean_business_markdown_text(text: str) -> str:
    if not text:
        return ""
    lines: list[str] = []
    skip_until_heading_level: int | None = None
    for raw_line in text.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw_line)
        if heading_match:
            heading_level = len(heading_match.group(1))
            heading = heading_match.group(2).strip().strip(":：")
            if skip_until_heading_level is not None and heading_level <= skip_until_heading_level:
                skip_until_heading_level = None
            if heading_level >= 2 and heading in GENERATED_BODY_SECTION_HEADINGS:
                skip_until_heading_level = heading_level
                continue
        if skip_until_heading_level is not None:
            continue
        stripped = raw_line.strip()
        if any(stripped.startswith(f"{prefix}:") or stripped.startswith(f"{prefix}：") for prefix in GENERATED_BODY_LINE_PREFIXES):
            continue
        lines.append(raw_line)
    cleaned = repair_wrapped_lines("\n".join(lines))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def make_source_document(
    row: dict[str, str],
    source_root: Path,
    output_root: Path,
    summary_map: dict[str, list[tuple[Path, str]]],
) -> PreparedDocument:
    source_id = row["source_id"].strip()
    title = row["title"].strip()
    source_type = row.get("source_type", "").strip()
    preferred_path = resolve_package_path(source_root, row.get("local_file", ""))
    text_path = find_text_alternative(source_root, source_id)
    source_path = choose_source_path(preferred_path, text_path)
    body = parse_source_text(source_path)
    if source_path.suffix.lower() in {".txt", ".html", ".htm"}:
        body = clean_web_boilerplate(body)
    body = clean_business_markdown_text(body)
    summaries = summary_map.get(source_id, [])

    output_file = output_root / "documents" / "official_sources" / f"{source_id}_{slugify(title, source_id)}.md"
    source_relative = package_relative(source_path, source_root)
    summary_blocks = []
    for summary_path, summary_text in summaries:
        summary_blocks.append(
            f"### 摘要来源：{package_relative(summary_path, source_root)}\n\n"
            + shift_markdown_headings(summary_text, levels=2)
        )
    summary_text = "\n\n".join(summary_blocks).strip()
    summary_text = clean_business_markdown_text(summary_text)

    content = "\n\n".join(
        part
        for part in [
            frontmatter(
                {
                    "document_id": source_id,
                    "kb_category": category_for_source(source_type, source_id),
                    "doc_type": source_type,
                    "title": title,
                    "source_ids": source_id,
                    "region": row.get("region", ""),
                    "issuer": row.get("issuer", ""),
                    "publish_date": row.get("publish_date", ""),
                    "effective_date": row.get("effective_date", ""),
                    "validity_status": row.get("validity_status", ""),
                    "review_status": row.get("review_status", ""),
                    "url": row.get("url", ""),
                    "source_relative_path": source_relative,
                    "chunk_size": CHUNK_SIZE,
                    "chunk_overlap": CHUNK_OVERLAP,
                }
            ),
            f"# {title}",
            "## 知识摘要\n\n" + summary_text if summary_text else "",
            "## 正文\n\n" + body,
        ]
        if part
    )
    write_text(output_file, content)
    rel_output = output_file.relative_to(output_root).as_posix()
    return PreparedDocument(
        document_id=source_id,
        title=title,
        kb_category=category_for_source(source_type, source_id),
        doc_type=source_type,
        region=row.get("region", ""),
        issuer=row.get("issuer", ""),
        publish_date=row.get("publish_date", ""),
        effective_date=row.get("effective_date", ""),
        validity_status=row.get("validity_status", ""),
        review_status=row.get("review_status", ""),
        source_ids=source_id,
        url=row.get("url", ""),
        prepared_file=rel_output,
        source_relative_path=source_relative,
        sha256=sha256_text(content),
        characters=len(content),
        vector_priority=100,
        notes="official_source_deduplicated",
    )


def make_faq_documents(
    source_root: Path,
    output_root: Path,
    source_lookup: dict[str, dict[str, str]],
) -> list[PreparedDocument]:
    faq_path = source_root / "05_FAQ标准问答" / "CSV数据" / "faq_seed.csv"
    if not faq_path.exists():
        return []
    documents: list[PreparedDocument] = []
    for row in csv_rows(faq_path):
        faq_id = row["faq_id"].strip()
        title = row["question"].strip()
        source_ids = row.get("source_ids", "").replace(";", ",")
        source_links, source_urls, first_url = format_external_source_links(source_ids, source_lookup)
        frontmatter_items = {
            "document_id": faq_id,
            "kb_category": "standard_faq",
            "doc_type": "FAQ标准问答",
            "title": title,
            "source_ids": source_ids,
            "category": row.get("category", ""),
            "region": row.get("region", ""),
            "risk_level": row.get("risk_level", ""),
            "updated_at": row.get("updated_at", ""),
            "source_relative_path": package_relative(faq_path, source_root),
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
        }
        if source_urls:
            frontmatter_items["source_urls"] = source_urls
        if first_url:
            frontmatter_items["url"] = first_url
        output_file = output_root / "documents" / "faqs" / f"{faq_id}_{slugify(title, faq_id)}.md"
        content = "\n\n".join(
            [
                frontmatter(frontmatter_items),
                f"# {faq_id} {title}",
                "## 问题\n\n" + title,
                "## 相似问法\n\n" + (row.get("aliases", "").replace("|", "\n\n") or "-"),
                "## 标准答案\n\n" + row.get("answer", "").strip(),
                "## 外部来源链接\n\n" + source_links if source_links else "",
            ]
        )
        write_text(output_file, content)
        documents.append(
            PreparedDocument(
                document_id=faq_id,
                title=title,
                kb_category="standard_faq",
                doc_type="FAQ标准问答",
                region=row.get("region", ""),
                issuer="AI资料整理",
                publish_date="",
                effective_date="",
                validity_status="有效",
                review_status="待人工复核",
                source_ids=source_ids,
                url=first_url,
                prepared_file=output_file.relative_to(output_root).as_posix(),
                source_relative_path=package_relative(faq_path, source_root),
                sha256=sha256_text(content),
                characters=len(content),
                vector_priority=80,
                notes="faq_retrieval_boost",
            )
        )
    return documents


def parse_simple_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_meta = text[3:end].strip()
    body = text[end + len("\n---") :].strip()
    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body


def make_company_policy_documents(source_root: Path, output_root: Path) -> list[PreparedDocument]:
    policy_dir = source_root / "04_企业内部制度资料" / "制度资料文件_按文件类型整理输出" / "Markdown入库版"
    if not policy_dir.exists():
        return []
    documents: list[PreparedDocument] = []
    for index, source_path in enumerate(sorted(policy_dir.glob("*.md")), start=1):
        raw_text = read_text(source_path)
        meta, body = parse_simple_frontmatter(raw_text)
        body = clean_business_markdown_text(body)
        document_id = f"COMPANY{index:03d}"
        title = meta.get("制度名称") or source_path.stem.replace("_入库版", "")
        source_relative = package_relative(source_path, source_root)
        output_file = output_root / "documents" / "company_policies" / f"{document_id}_{slugify(title, document_id)}.md"
        content = "\n\n".join(
            [
                frontmatter(
                    {
                        "document_id": document_id,
                        "kb_category": "company_policy",
                        "doc_type": meta.get("资料类型", "企业内部制度"),
                        "title": title,
                        "source_ids": "",
                        "region": "陕西",
                        "issuer": meta.get("企业名称", "企业内部制度"),
                        "publish_date": "",
                        "effective_date": meta.get("制度版本", ""),
                        "validity_status": meta.get("资料状态", "已脱敏入库版"),
                        "review_status": "待企业HR/法务复核",
                        "url": "",
                        "source_relative_path": source_relative,
                        "chunk_size": CHUNK_SIZE,
                        "chunk_overlap": CHUNK_OVERLAP,
                    }
                ),
                f"# {title}",
                "## 正文\n\n" + body,
            ]
        )
        write_text(output_file, content)
        documents.append(
            PreparedDocument(
                document_id=document_id,
                title=title,
                kb_category="company_policy",
                doc_type=meta.get("资料类型", "企业内部制度"),
                region="陕西",
                issuer=meta.get("企业名称", "企业内部制度"),
                publish_date="",
                effective_date=meta.get("制度版本", ""),
                validity_status=meta.get("资料状态", "已脱敏入库版"),
                review_status="待企业HR/法务复核",
                source_ids="",
                url="",
                prepared_file=output_file.relative_to(output_root).as_posix(),
                source_relative_path=source_relative,
                sha256=sha256_text(content),
                characters=len(content),
                vector_priority=90,
                notes="company_policy_sanitized_markdown",
            )
        )
    return documents


def write_manifest(output_root: Path, documents: list[PreparedDocument], source_root: Path) -> None:
    fieldnames = list(asdict(documents[0]).keys()) if documents else [field.name for field in PreparedDocument.__dataclass_fields__.values()]
    manifest_csv = output_root / "manifest.csv"
    with manifest_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in documents:
            writer.writerow(asdict(item))

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_root_name": source_root.name,
        "document_count": len(documents),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "categories": category_counts(documents),
        "documents": [asdict(item) for item in documents],
    }
    write_text(output_root / "manifest.json", json.dumps(payload, ensure_ascii=False, indent=2))

    upload_plan = sorted(documents, key=lambda item: (-item.vector_priority, item.document_id))
    with (output_root / "upload_plan.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["order", "document_id", "title", "kb_category", "prepared_file", "source_ids", "notes"],
            lineterminator="\n",
        )
        writer.writeheader()
        for index, item in enumerate(upload_plan, start=1):
            writer.writerow(
                {
                    "order": index,
                    "document_id": item.document_id,
                    "title": item.title,
                    "kb_category": item.kb_category,
                    "prepared_file": item.prepared_file,
                    "source_ids": item.source_ids,
                    "notes": item.notes,
                }
            )


def category_counts(documents: list[PreparedDocument]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in documents:
        counts[item.kb_category] = counts.get(item.kb_category, 0) + 1
    return dict(sorted(counts.items()))


def write_readme(output_root: Path, documents: list[PreparedDocument]) -> None:
    counts = category_counts(documents)
    lines = [
        "# LangChain/Milvus 知识库转换资料",
        "",
        "本目录由 `scripts/prepare_langchain_knowledge_base.py` 生成，用于将原始政策法规、陕西区域资料、西安办事规则、企业内部制度和 FAQ 整理成可入 Milvus 的标准 Markdown 文档。",
        "",
        "## 内容统计",
        "",
    ]
    for category, count in counts.items():
        lines.append(f"- `{category}`：{count} 份")
    lines.extend(
        [
            "",
            "## 目录结构",
            "",
            "- `documents/official_sources/`：去重后的官方政策、法规和办事规则全文，已合并知识卡或办事指南摘要",
            "- `documents/company_policies/`：企业内部制度脱敏入库版",
            "- `documents/faqs/`：标准问答，主要用于提升常见问法召回率",
            "- `manifest.csv` / `manifest.json`：入库清单和元数据",
            "- `upload_plan.csv`：建议上传顺序",
            "- `excluded_files.md`：未纳入向量库的资料类型说明",
            "",
            "## 推荐入库方式",
            "",
            "1. 启动项目并配置 `LANGCHAIN_API_KEY`、`LANGCHAIN_EMBEDDING_MODEL`、`MILVUS_URI`、`MILVUS_COLLECTION`。",
            "2. 登录管理端，进入「来源管理」的「文档解析入库」。",
            "3. 按 `upload_plan.csv` 上传 `prepared_file` 对应的 Markdown 文件。",
            "4. 官方来源资料优先入库；企业制度和 FAQ 可按业务需要补充入库。",
            "",
            "## 推荐切分参数",
            "",
            f"- `VECTOR_CHUNK_SIZE={CHUNK_SIZE}`",
            f"- `VECTOR_CHUNK_OVERLAP={CHUNK_OVERLAP}`",
            "- 分隔符沿用项目后端 `RecursiveCharacterTextSplitter`：段落、换行、中文句号、分号、英文标点、空格。",
            "",
            "## 注意事项",
            "",
            "- 产物只保留相对来源路径，不写入本机绝对路径。",
            "- `review_status=待人工复核` 的资料在正式上线前应由 HR/法务或政策负责人复核。",
            "- FAQ 与官方来源冲突时，以最新官方来源和人工复核结果为准。",
        ]
    )
    write_text(output_root / "README.md", "\n".join(lines))


def write_excluded_files(output_root: Path) -> None:
    content = """# 未纳入向量库的资料说明

以下资料不建议直接进入 LangChain/Milvus 业务知识库：

- `00_资料包索引/`：资料包说明和校验报告，属于交付管理信息。
- `07_数据库设计/`：数据库建表和演示数据脚本，不属于问答知识。
- `08_Dify配置与Prompt/`：Prompt 和 Dify 导入说明，属于系统配置资料。
- `09_接口文档/`：API 文档，容易污染业务问答语料。
- `10_测试验收资料/`：测试问题可用于验收，不作为正式知识来源。
- `11_商业化汇报资料/`：演示和交付说明，不属于政策依据。
- `12_下载日志/`：下载报告和源 URL 元数据，仅用于追溯。
- 重复格式文件：同一来源的 `PDF`、`HTML`、`JSON`、`DOCX` 不重复入库，优先选择可解析文本更干净的 `DOCX/TXT/Markdown`。

如需调试或审计，可以通过 `manifest.csv` 的 `source_relative_path` 回到原始资料包查验。
"""
    write_text(output_root / "excluded_files.md", content)


def prepare(source_root: Path, output_root: Path) -> None:
    source_root = source_root.expanduser().resolve()
    output_root = output_root.resolve()
    if not source_root.exists():
        raise SystemExit(f"source root not found: {source_root}")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    sources_csv = source_root / "06_官方来源目录" / "CSV数据" / "sources.csv"
    if not sources_csv.exists():
        raise SystemExit(f"sources.csv not found: {sources_csv}")

    summary_map = build_summary_map(source_root)
    source_rows = csv_rows(sources_csv)
    source_lookup = build_source_lookup(source_rows)
    documents = [make_source_document(row, source_root, output_root, summary_map) for row in source_rows]
    documents.extend(make_company_policy_documents(source_root, output_root))
    documents.extend(make_faq_documents(source_root, output_root, source_lookup))
    documents.sort(key=lambda item: (item.kb_category, item.document_id))

    write_manifest(output_root, documents, source_root)
    write_readme(output_root, documents)
    write_excluded_files(output_root)

    print(f"Prepared {len(documents)} documents in {output_root}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare LangChain/Milvus knowledge-base import files.")
    parser.add_argument("--source-root", required=True, help="资料 package root directory")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()
    prepare(Path(args.source_root), Path(args.output_dir))


if __name__ == "__main__":
    main()
