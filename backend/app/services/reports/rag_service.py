from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Jieba-based tokenizer with fallback: word segmentation + character bigrams for semantic matching."""
    content = str(text or "").lower()

    tokens: list[str] = []
    try:
        import jieba

        # Use jieba for Chinese word segmentation
        seg_list = jieba.cut(content)
        for word in seg_list:
            word = word.strip()
            if len(word) >= 1:
                tokens.append(word)
    except ImportError:
        # Fallback: n-gram based tokenization
        zh_words = re.findall(r"[一-鿿]{1,8}", content)
        tokens.extend(zh_words)

    # Add character bigrams for extra semantic coverage (helps with partial matches)
    zh_chars = "".join(re.findall(r"[一-鿿]+", content))
    for i in range(len(zh_chars) - 1):
        tokens.append(zh_chars[i : i + 2])

    # Alphanumeric tokens
    en_tokens = re.findall(r"[a-z0-9_]{2,24}", content)
    tokens.extend(en_tokens)

    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t.strip() and t not in seen:
            seen.add(t)
            out.append(t.strip())
    return out


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def _norm(v: dict[str, float]) -> float:
    return math.sqrt(sum(x * x for x in v.values()))


@dataclass
class RagService:
    project_root: Path
    _cache: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def _index_path(self) -> Path:
        return self.project_root / "data" / "ads" / "reports" / "knowledge_index.json"

    def _knowledge_path(self) -> Path:
        return self.project_root / "知识库.md"

    def _expert_kb_path(self) -> Path:
        return (
            self.project_root
            / "backend"
            / "app"
            / "services"
            / "reports"
            / "prompts"
            / "expert_knowledge_base.md"
        )

    def _source_files(self) -> list[Path]:
        files: list[Path] = [
            self._knowledge_path(),
            self.project_root / "赛题.md",
            self.project_root / "时间说明.md",
            self.project_root / "data" / "ads" / "risk_warnings" / "risk_methodology.json",
        ]
        # Include expert knowledge base if it exists (for prediction-oriented queries)
        expert_path = self._expert_kb_path()
        if expert_path.exists():
            files.append(expert_path)
        return files

    def _chunk_text(self, text: str, source_name: str) -> list[dict[str, Any]]:
        lines = [line.rstrip() for line in str(text).splitlines()]
        blocks: list[str] = []
        current: list[str] = []

        for line in lines:
            stripped = line.strip()
            # Split on ## / ### / #### headers
            if stripped.startswith("## ") and current:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            if stripped.startswith("### ") and current:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            if stripped.startswith("#### ") and current:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            current.append(line)
            # Hard split at 1200 chars (was 900) to avoid cutting reasoning chains
            if len("\n".join(current)) >= 1200:
                blocks.append("\n".join(current).strip())
                current = []

        if current:
            blocks.append("\n".join(current).strip())

        chunks: list[dict[str, Any]] = []
        for idx, block in enumerate(blocks):
            clean = block.strip()
            if len(clean) < 40:
                continue
            # Generate a title hint from the first heading line
            title_hint = ""
            for line in clean.splitlines():
                s = line.strip()
                if s.startswith("#"):
                    title_hint = s.lstrip("#").strip()[:80]
                    break
            chunks.append(
                {
                    "chunk_id": f"{source_name}::chunk-{idx + 1}",
                    "source": source_name,
                    "text": clean,
                    "title_hint": title_hint,
                }
            )
        return chunks

    def _role_score_boost(self, text: str, role_view: str) -> float:
        content = str(text or "")
        role = str(role_view or "student").lower()
        if role in {"counselor", "teacher"}:
            keywords = [
                "辅导员",
                "干预",
                "约谈",
                "回访",
                "执行",
                "复盘",
                "班级",
                "预警",
                "谈话话术",
                "开场白",
                "共情",
                "倾听",
                "引导",
                "家访",
                "家长沟通",
                "学业预警",
                "学习困难",
                "挂科",
                "心理",
                "情绪",
                "融入",
                "微计划",
                "目标设定",
                "任务拆解",
                "自我管理",
                "学习习惯",
                "生活节律",
                "干预建议",
                "干预导向",
                "话术示例",
                "SOP",
                "风险等级",
                "红色预警",
                "黄色预警",
            ]
        elif role in {"leader", "principal", "school"}:
            keywords = [
                "学校",
                "学院",
                "专业",
                "群体",
                "治理",
                "看板",
                "分布",
                "资源配置",
                "去向分布",
                "就业率",
                "升学率",
                "整体",
                "趋势",
            ]
        else:
            keywords = [
                "学生",
                "学习",
                "建议",
                "微计划",
                "自我管理",
                "节律",
                "任务",
                "去向",
                "发展建议",
            ]
        hit = sum(1 for kw in keywords if kw in content)
        return 0.03 * float(hit)  # Increased from 0.02 for stronger signal

    def _build_index_payload(self) -> dict[str, Any]:
        chunks: list[dict[str, Any]] = []
        vocabulary_df: dict[str, int] = {}
        for file in self._source_files():
            if not file.exists():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except Exception:
                continue
            source_name = str(file.relative_to(self.project_root)).replace("\\", "/")
            chunks.extend(self._chunk_text(content, source_name))

        vector_chunks: list[dict[str, Any]] = []
        for item in chunks:
            tokens = _tokenize(item["text"])
            unique = set(tokens)
            for token in unique:
                vocabulary_df[token] = vocabulary_df.get(token, 0) + 1
            tf: dict[str, float] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0.0) + 1.0
            total = sum(tf.values()) or 1.0
            for token in list(tf.keys()):
                tf[token] = tf[token] / total
            vector_chunks.append({**item, "tf": tf})

        doc_n = max(1, len(vector_chunks))
        for item in vector_chunks:
            vec: dict[str, float] = {}
            for token, tf_val in item["tf"].items():
                df = vocabulary_df.get(token, 1)
                idf = math.log((doc_n + 1) / (df + 1)) + 1.0
                vec[token] = float(tf_val * idf)
            item["vector"] = vec
            item["norm"] = _norm(vec)
            item.pop("tf", None)

        payload = {
            "status": "ready" if vector_chunks else "empty",
            "document_count": len({item["source"] for item in vector_chunks}),
            "chunk_count": len(vector_chunks),
            "indexed_at": datetime.now().isoformat(timespec="seconds"),
            "chunks": vector_chunks,
        }
        return payload

    def build_or_load_index(self, force_reindex: bool = False) -> dict[str, Any]:
        if self._cache is not None and not force_reindex:
            return self._cache
        index_path = self._index_path()
        if not force_reindex and index_path.exists():
            try:
                payload = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("chunks"), list):
                    self._cache = payload
                    return payload
            except Exception:
                pass
        payload = self._build_index_payload()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._cache = payload
        return payload

    def search(
        self,
        query: str,
        top_k: int = 3,
        force_reindex: bool = False,
        role_view: str = "student",
        allowed_sources: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.build_or_load_index(force_reindex=force_reindex)
        chunks = payload.get("chunks", [])
        if not isinstance(chunks, list) or not chunks:
            return []

        # Build source filter: match by filename or full relative path
        source_allow: set[str] = set()
        if allowed_sources:
            for x in allowed_sources:
                s = str(x).strip()
                if s:
                    source_allow.add(s)
                    source_allow.add(Path(s).name)

        # Tokenize query
        tokens = _tokenize(query)
        tf: dict[str, float] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0.0) + 1.0
        total = sum(tf.values()) or 1.0
        query_vec = {k: v / total for k, v in tf.items()}
        query_norm = _norm(query_vec)

        # Boost: if query tokens appear in chunk title, add bonus
        query_token_set = set(tokens)

        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in chunks:
            source = str(chunk.get("source", ""))
            source_filename = Path(source).name

            # Source filter
            if source_allow:
                if source not in source_allow and source_filename not in source_allow:
                    continue

            vector = chunk.get("vector", {})
            if not isinstance(vector, dict):
                continue

            score = 0.0
            if query_norm > 0 and float(chunk.get("norm", 0.0) or 0.0) > 0:
                score = _dot(query_vec, vector) / (
                    query_norm * float(chunk.get("norm", 1.0))
                )

            # Role boost
            score += self._role_score_boost(
                text=str(chunk.get("text", "")), role_view=role_view
            )

            # Title match bonus: if query words appear in chunk title, boost
            title = str(chunk.get("title_hint", ""))
            if title:
                title_tokens = set(_tokenize(title))
                overlap = len(query_token_set & title_tokens)
                score += 0.05 * float(overlap)

            scored.append((float(score), chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        out: list[dict[str, Any]] = []
        for score, chunk in scored[: max(1, top_k)]:
            out.append(
                {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "source": chunk.get("source", ""),
                    "score": round(float(score), 6),
                    "excerpt": str(chunk.get("text", "")),
                    "text": str(chunk.get("text", "")),
                    "title_hint": str(chunk.get("title_hint", "")),
                }
            )
        return out

    def status(self) -> dict[str, Any]:
        payload = self.build_or_load_index(force_reindex=False)
        return {
            "status": payload.get("status", "empty"),
            "document_count": int(payload.get("document_count", 0) or 0),
            "chunk_count": int(payload.get("chunk_count", 0) or 0),
            "last_index_time": str(payload.get("indexed_at", "")),
            "index_path": str(self._index_path()),
            "documents": sorted(
                {
                    str(item.get("source", ""))
                    for item in payload.get("chunks", [])
                    if str(item.get("source", ""))
                }
            ),
        }
