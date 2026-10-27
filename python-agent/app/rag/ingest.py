"""把 Markdown 知识文档切成带标题层级的切片，并可写入 JSON 目录。

本模块不调用模型，也不创建向量。
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class KnowledgeChunk(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    section: str
    source: str
    content: str


def load_knowledge_chunks(directory: Path) -> list[KnowledgeChunk]:
    """读取目录中的 Markdown，按文件名排序后切分。重复调用返回同一组切片。"""
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    chunks: list[KnowledgeChunk] = []
    for path in sorted(path for path in directory.glob("*.md") if path.is_file()):
        chunks.extend(
            split_markdown(
                path.read_text(encoding="utf-8"),
                document_id=path.stem,
                source=path.name,
            )
        )
    return chunks


def split_markdown(text: str, *, document_id: str, source: str) -> list[KnowledgeChunk]:
    """按 ATX 标题切分，并用标题栈保留层级。

    一个标题只拥有它自己的正文。子标题另起切片，兄弟标题也不会并入当前切片。
    没有正文的标题不产生切片。
    """
    stack: list[tuple[int, str]] = []
    document_title = ""
    body: list[str] = []
    sections: list[tuple[str, str, str]] = []

    def flush() -> None:
        content = "\n".join(body).strip()
        body.clear()
        if not content:
            return
        if stack:
            title = document_title or stack[0][1]
            section = " / ".join(heading for _, heading in stack)
        else:
            title = document_title or document_id
            section = title
        sections.append((title, section, content))

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match is None:
            body.append(line)
            continue
        flush()
        level = len(match.group(1))
        heading = match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading))
        if level == 1 and not document_title:
            document_title = heading

    flush()
    return _with_chunk_ids(document_id, source, sections)


def write_chunk_catalog(chunks: list[KnowledgeChunk], catalog_path: Path) -> list[KnowledgeChunk]:
    """按 chunk_id 合并进 JSON。同一个切片再次写入时覆盖原记录，不新增一行。"""
    current = read_chunk_catalog(catalog_path)
    merged = {chunk.chunk_id: chunk for chunk in current}
    order = [chunk.chunk_id for chunk in current]
    for chunk in chunks:
        if chunk.chunk_id not in merged:
            order.append(chunk.chunk_id)
        merged[chunk.chunk_id] = chunk
    result = [merged[chunk_id] for chunk_id in order]
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"chunks": [chunk.model_dump() for chunk in result]}
    catalog_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def read_chunk_catalog(catalog_path: Path) -> list[KnowledgeChunk]:
    if not catalog_path.is_file():
        return []
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [KnowledgeChunk.model_validate(item) for item in payload["chunks"]]


def _with_chunk_ids(
    document_id: str,
    source: str,
    sections: list[tuple[str, str, str]],
) -> list[KnowledgeChunk]:
    totals: dict[str, int] = {}
    for _, section, _ in sections:
        key = f"{document_id}:{section}"
        totals[key] = totals.get(key, 0) + 1

    seen: dict[str, int] = {}
    chunks: list[KnowledgeChunk] = []
    for title, section, content in sections:
        key = f"{document_id}:{section}"
        seen[key] = seen.get(key, 0) + 1
        chunk_id = key if totals[key] == 1 else f"{key}#{seen[key]}"
        chunks.append(
            KnowledgeChunk(
                document_id=document_id,
                chunk_id=chunk_id,
                title=title,
                section=section,
                source=source,
                content=content,
            )
        )
    return chunks
