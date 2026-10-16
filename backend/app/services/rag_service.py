"""
轻量级 RAG 服务（v2 — 从老项目 student-behavior-analysis 移植升级）

设计原则：
- 不强依赖 chromadb / FAISS / sentence-transformers，缺包时自动降级
- 三级检索后端：
    1) 优先：jieba 分词 + char-bigram + 持久化 TF-IDF JSON 索引（移植自老项目）
    2) 次选：sklearn TfidfVectorizer (char_wb 2-3 gram)
    3) 兜底：关键词重叠 + 子串匹配
- 启动时一次性加载 knowledge_base/**/*.md，按 Markdown 标题 + 1200 字硬切分块
- 索引持久化到 data/ads/rag/knowledge_index.json，冷启动秒级
- 对外暴露 retrieve(query, top_k, course_filter) 同步接口

后续可平滑替换为 ChromaDB（接口已抽象）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 检索结果
# ---------------------------------------------------------------------------
@dataclass
class RetrievedChunk:
    """检索结果统一结构"""
    content: str
    source: str
    course: str
    score: float = 0.0
    chunk_id: str = ""
    title_hint: str = ""                                # 移植自老项目：分块所属标题
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tokenizer（移植自老项目 services/reports/rag_service.py）
# - 优先 jieba 分词
# - 自动 char-bigram 补强
# - 字母数字单独 token
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> List[str]:
    """jieba 分词 + char-bigram + 英文数字 token"""
    content = str(text or "").lower()

    tokens: List[str] = []
    try:
        import jieba  # type: ignore

        seg_list = jieba.cut(content)
        for word in seg_list:
            word = word.strip()
            if len(word) >= 1:
                tokens.append(word)
    except ImportError:
        # 兜底：n-gram tokenizer
        zh_words = re.findall(r"[一-鿿]{1,8}", content)
        tokens.extend(zh_words)

    # char-bigram 补强（即使 jieba 在也加，提升部分匹配命中）
    zh_chars = "".join(re.findall(r"[一-鿿]+", content))
    for i in range(len(zh_chars) - 1):
        tokens.append(zh_chars[i:i + 2])

    # 英文数字 token
    en_tokens = re.findall(r"[a-z0-9_]{2,24}", content)
    tokens.extend(en_tokens)

    # 去重保序
    seen: set = set()
    out: List[str] = []
    for t in tokens:
        if t.strip() and t not in seen:
            seen.add(t)
            out.append(t.strip())
    return out


def _dot(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def _norm(v: Dict[str, float]) -> float:
    return math.sqrt(sum(x * x for x in v.values()))


# ---------------------------------------------------------------------------
# 文档分块（移植自老项目：按 Markdown 标题切 + 1200 字硬切）
# ---------------------------------------------------------------------------
def _chunk_markdown(text: str, source_name: str, course: str, max_chars: int = 1200) -> List[Dict[str, Any]]:
    """
    按 Markdown 标题（##/###/####）切块；超长块按 1200 字硬切。
    每个 chunk 自带 title_hint（首行标题）。

    返回字段：chunk_id / source / course / text / title_hint
    """
    lines = [line.rstrip() for line in str(text).splitlines()]
    blocks: List[str] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if (stripped.startswith("## ") or stripped.startswith("### ") or stripped.startswith("#### ")) and current:
            blocks.append("\n".join(current).strip())
            current = [line]
            continue
        current.append(line)
        if len("\n".join(current)) >= max_chars:
            blocks.append("\n".join(current).strip())
            current = []
    if current:
        blocks.append("\n".join(current).strip())

    chunks: List[Dict[str, Any]] = []
    for idx, block in enumerate(blocks):
        clean = block.strip()
        if len(clean) < 40:
            continue
        title_hint = ""
        for line in clean.splitlines():
            s = line.strip()
            if s.startswith("#"):
                title_hint = s.lstrip("#").strip()[:80]
                break
        chunks.append({
            "chunk_id": f"{source_name}::chunk-{idx + 1}",
            "source": source_name,
            "course": course,
            "text": clean,
            "title_hint": title_hint,
        })
    return chunks


# ---------------------------------------------------------------------------
# 后端 1：jieba TF-IDF + 持久化 JSON 索引（移植自老项目，主推）
# ---------------------------------------------------------------------------
class _JiebaTfidfBackend:
    """jieba 分词 + char-bigram + TF-IDF + cosine 相似度 + JSON 持久化索引"""

    def __init__(self, persist_path: Path):
        self.persist_path = Path(persist_path)
        self._payload: Optional[Dict[str, Any]] = None

    def _corpus_hash(self, chunks: List[Dict[str, Any]]) -> str:
        basis = [
            {
                "chunk_id": item.get("chunk_id", ""),
                "source": item.get("source", ""),
                "text": item.get("text", ""),
            }
            for item in chunks
        ]
        raw = json.dumps(
            basis,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _build_payload(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        vector_chunks: List[Dict[str, Any]] = []
        vocabulary_df: Dict[str, int] = {}

        for item in chunks:
            tokens = _tokenize(item["text"])
            unique = set(tokens)
            for token in unique:
                vocabulary_df[token] = vocabulary_df.get(token, 0) + 1
            tf: Dict[str, float] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0.0) + 1.0
            total = sum(tf.values()) or 1.0
            for token in list(tf.keys()):
                tf[token] = tf[token] / total
            vector_chunks.append({**item, "tf": tf})

        doc_n = max(1, len(vector_chunks))
        for item in vector_chunks:
            vec: Dict[str, float] = {}
            for token, tf_val in item["tf"].items():
                df = vocabulary_df.get(token, 1)
                idf = math.log((doc_n + 1) / (df + 1)) + 1.0
                vec[token] = float(tf_val * idf)
            item["vector"] = vec
            item["norm"] = _norm(vec)
            item.pop("tf", None)

        return {
            "status": "ready" if vector_chunks else "empty",
            "document_count": len({item["source"] for item in vector_chunks}),
            "chunk_count": len(vector_chunks),
            "corpus_hash": self._corpus_hash(chunks),
            "indexed_at": datetime.now().isoformat(timespec="seconds"),
            "chunks": vector_chunks,
        }

    def build(self, chunks: List[Dict[str, Any]], force_rebuild: bool = False) -> None:
        expected_hash = self._corpus_hash(chunks)
        if not force_rebuild and self.persist_path.exists():
            try:
                payload = json.loads(self.persist_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("chunks"), list):
                    cache_is_current = (
                        int(payload.get("chunk_count", 0)) == len(chunks)
                        and payload.get("corpus_hash") == expected_hash
                    )
                    if cache_is_current:
                        self._payload = payload
                        logger.info(f"[RAG] 已从磁盘加载索引: {self.persist_path}（{payload.get('chunk_count')} 块）")
                        return
            except Exception as exc:
                logger.warning(f"[RAG] 索引文件读取失败，将重建：{exc}")

        self._payload = self._build_payload(chunks)
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self.persist_path.write_text(
                json.dumps(self._payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"[RAG] 已写入索引: {self.persist_path}（{self._payload.get('chunk_count')} 块）")
        except Exception as exc:
            logger.warning(f"[RAG] 索引落盘失败（仅内存）：{exc}")

    def search(self, query: str, top_k: int, course_filter: Optional[str] = None) -> List[RetrievedChunk]:
        if not self._payload:
            return []
        chunks = self._payload.get("chunks", [])
        if not chunks:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []
        tf: Dict[str, float] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0.0) + 1.0
        total = sum(tf.values()) or 1.0
        query_vec = {k: v / total for k, v in tf.items()}
        query_norm = _norm(query_vec)
        if query_norm <= 0:
            return []

        query_token_set = set(tokens)
        scored: List[tuple[float, Dict[str, Any]]] = []

        for chunk in chunks:
            if course_filter and chunk.get("course") != course_filter:
                continue
            vector = chunk.get("vector", {})
            chunk_norm = float(chunk.get("norm", 0.0) or 0.0)
            if not isinstance(vector, dict) or chunk_norm <= 0:
                continue

            score = _dot(query_vec, vector) / (query_norm * chunk_norm)

            # 标题命中加分
            title = str(chunk.get("title_hint", ""))
            if title:
                title_tokens = set(_tokenize(title))
                overlap = len(query_token_set & title_tokens)
                score += 0.05 * float(overlap)

            scored.append((float(score), chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[RetrievedChunk] = []
        for score, chunk in scored[:max(1, top_k)]:
            out.append(RetrievedChunk(
                content=str(chunk.get("text", "")),
                source=str(chunk.get("source", "")),
                course=str(chunk.get("course", "")),
                score=round(float(score), 6),
                chunk_id=str(chunk.get("chunk_id", "")),
                title_hint=str(chunk.get("title_hint", "")),
            ))
        return out


# ---------------------------------------------------------------------------
# 后端 1.5：SQLite DB 持久化（v6 B-P1-2，主推 —— 替代 JSON 索引文件）
# ---------------------------------------------------------------------------
class _DbTfidfBackend:
    """DB-backed TF-IDF — delegates to IndexManager.

    Same ranking as _JiebaTfidfBackend but persists chunks + vectors to
    SQLite (`knowledge_chunks` + `chunk_vectors`) instead of a JSON file.
    Supports incremental updates via content_hash.
    """

    def __init__(self):
        from backend.app.services.rag.index_manager import IndexManager
        self._mgr = IndexManager()

    def build(self, chunks: List[Dict[str, Any]], force_rebuild: bool = False) -> None:
        self._mgr.build(chunks, force_rebuild=force_rebuild)

    def search(self, query: str, top_k: int, course_filter: Optional[str] = None) -> List[RetrievedChunk]:
        return self._mgr.search(query, top_k=top_k, course_filter=course_filter)


# ---------------------------------------------------------------------------
# 后端 2：sklearn TfidfVectorizer（无 jieba 时的次选，保持向前兼容）
# ---------------------------------------------------------------------------
class _SklearnTfidfBackend:
    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), max_features=20000)
        self._cosine = cosine_similarity
        self._matrix = None
        self._chunks: List[Dict[str, Any]] = []

    def build(self, chunks: List[Dict[str, Any]], **_kw) -> None:
        self._chunks = chunks
        if not chunks:
            self._matrix = None
            return
        texts = [c["text"] for c in chunks]
        self._matrix = self._vectorizer.fit_transform(texts)

    def search(self, query: str, top_k: int, course_filter: Optional[str] = None) -> List[RetrievedChunk]:
        if self._matrix is None or not self._chunks:
            return []
        q_vec = self._vectorizer.transform([query])
        sims = self._cosine(q_vec, self._matrix).ravel()
        order = sims.argsort()[::-1]
        results: List[RetrievedChunk] = []
        for idx in order:
            if len(results) >= top_k:
                break
            score = float(sims[int(idx)])
            if score <= 0.0:
                continue
            chunk = self._chunks[int(idx)]
            if course_filter and chunk.get("course") != course_filter:
                continue
            results.append(RetrievedChunk(
                content=chunk["text"],
                source=chunk["source"],
                course=chunk["course"],
                score=round(score, 6),
                chunk_id=chunk["chunk_id"],
                title_hint=chunk.get("title_hint", ""),
            ))
        return results


# ---------------------------------------------------------------------------
# 后端 3：关键词重叠（最终兜底，零依赖）
# ---------------------------------------------------------------------------
class _KeywordBackend:
    _CN_TOKEN = re.compile(r"[一-鿿]{1}|[A-Za-z0-9]+")

    def __init__(self):
        self._chunks: List[Dict[str, Any]] = []
        self._token_index: List[set] = []

    def _tk(self, text: str) -> set:
        return set(self._CN_TOKEN.findall(text.lower()))

    def build(self, chunks: List[Dict[str, Any]], **_kw) -> None:
        self._chunks = chunks
        self._token_index = [self._tk(c["text"]) for c in chunks]

    def search(self, query: str, top_k: int, course_filter: Optional[str] = None) -> List[RetrievedChunk]:
        if not self._chunks:
            return []
        q_tokens = self._tk(query)
        if not q_tokens:
            return []
        scored: List[tuple[float, Dict[str, Any]]] = []
        for idx, tokens in enumerate(self._token_index):
            if not tokens:
                continue
            chunk = self._chunks[idx]
            if course_filter and chunk.get("course") != course_filter:
                continue
            overlap = len(q_tokens & tokens)
            if overlap == 0:
                continue
            score = overlap / (len(q_tokens) + 1)
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[RetrievedChunk] = []
        for score, chunk in scored[:top_k]:
            out.append(RetrievedChunk(
                content=chunk["text"],
                source=chunk["source"],
                course=chunk["course"],
                score=round(float(score), 6),
                chunk_id=chunk["chunk_id"],
                title_hint=chunk.get("title_hint", ""),
            ))
        return out


# ---------------------------------------------------------------------------
# 主服务
# ---------------------------------------------------------------------------
class RAGService:
    """统一 RAG 入口 —— 启动时索引整个 knowledge_base 目录"""

    def __init__(self, knowledge_root: Path, persist_path: Optional[Path] = None):
        self.knowledge_root = Path(knowledge_root)
        self.persist_path = Path(persist_path) if persist_path else Path("data/ads/rag/knowledge_index.json")
        self._raw_chunks: List[Dict[str, Any]] = []
        self._backend = None
        self._backend_name = "none"
        self._loaded = False
        self._lock = Lock()

    # ----------------------------- 加载与索引 -----------------------------
    def load(self, force_rebuild: bool = False) -> None:
        """加载 + 索引（线程安全）"""
        with self._lock:
            if self._loaded and not force_rebuild:
                return
            self._raw_chunks = self._collect_chunks()
            self._init_backend(force_rebuild=force_rebuild)
            self._loaded = True
            logger.info(
                f"[RAG] 已索引 {len(self._raw_chunks)} 个知识块，后端={self._backend_name}"
            )

    def refresh(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """重新扫描 knowledge_base 并增量更新索引。

        教师上传/删除知识库文档后调用；DB 后端按 content_hash 增量 upsert
        并自动清理孤儿 chunk，成本远低于全量重建。
        """
        with self._lock:
            self._raw_chunks = self._collect_chunks()
            if self._backend is None:
                self._init_backend(force_rebuild=force_rebuild)
            else:
                try:
                    self._backend.build(self._raw_chunks, force_rebuild=force_rebuild)
                except TypeError:
                    # sklearn/keyword 兜底后端不接受 force_rebuild 参数
                    self._backend.build(self._raw_chunks)
            self._loaded = True
            logger.info(
                f"[RAG] refresh 完成: {len(self._raw_chunks)} chunks, 后端={self._backend_name}"
            )
        return self.stats()

    def _collect_chunks(self) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        if not self.knowledge_root.is_dir():
            logger.warning(f"[RAG] 知识库路径不存在: {self.knowledge_root}")
            return chunks
        for md_path in sorted(self.knowledge_root.glob("**/*.md")):
            try:
                text = md_path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning(f"[RAG] 读取 {md_path} 失败: {exc}")
                continue
            rel = md_path.relative_to(self.knowledge_root)
            course = rel.parts[0] if len(rel.parts) > 1 else "general"
            source = str(rel).replace("\\", "/")
            chunks.extend(_chunk_markdown(text, source_name=source, course=course))
        return chunks

    def _init_backend(self, force_rebuild: bool = False) -> None:
        # 优先 SQLite DB 持久化后端（v6 B-P1-2）—— 增量更新、crash-safe
        try:
            backend = _DbTfidfBackend()
            backend.build(self._raw_chunks, force_rebuild=force_rebuild)
            self._backend = backend
            self._backend_name = "sqlite_db"
            return
        except Exception as exc:
            logger.warning(f"[RAG] DB 后端初始化失败，降级到 jieba JSON：{exc}")

        # 次选：jieba TF-IDF + 持久化 JSON
        try:
            backend = _JiebaTfidfBackend(self.persist_path)
            backend.build(self._raw_chunks, force_rebuild=force_rebuild)
            self._backend = backend
            self._backend_name = "jieba_tfidf"
            return
        except Exception as exc:
            logger.warning(f"[RAG] jieba 后端初始化失败：{exc}")

        # 次选 sklearn TF-IDF
        try:
            backend = _SklearnTfidfBackend()
            backend.build(self._raw_chunks)
            self._backend = backend
            self._backend_name = "sklearn_tfidf"
            return
        except Exception as exc:
            logger.warning(f"[RAG] sklearn 后端初始化失败：{exc}")

        # 兜底 keyword
        backend = _KeywordBackend()
        backend.build(self._raw_chunks)
        self._backend = backend
        self._backend_name = "keyword"

    # ----------------------------- 查询接口 -----------------------------
    def is_ready(self) -> bool:
        return self._loaded and bool(self._raw_chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        course_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """返回 LLM/Agent 友好的 list[dict]，字段：content/source/course/score/title_hint"""
        if not self._loaded:
            self.load()
        if not query.strip() or not self._backend:
            return []

        results = self._backend.search(query, top_k=max(top_k, 1), course_filter=course_filter)
        enriched = []
        for c in results:
            # FIX-04（2026-07-17）：补齐知识点字段契约 —— PersistStage 依赖
            # metadata.kp_id / hit.kp_id 做 RealDINA/BKT 回写，此前 RAG 输出
            # 没有该字段导致普通聊天无法更新知识点状态。
            kp_ids = _kp_ids_for_source(c.course, c.source)
            enriched.append({
                "content": c.content,
                "source": c.source,
                "course": c.course,
                "score": c.score,
                "chunk_id": c.chunk_id,
                "title_hint": c.title_hint,
                "kp_id": kp_ids[0] if kp_ids else "",
                "kp_ids": kp_ids,
                "metadata": {"kp_id": kp_ids[0]} if kp_ids else {},
            })
        return enriched

    def stats(self) -> Dict[str, Any]:
        if not self._loaded:
            self.load()
        courses: Dict[str, int] = {}
        for c in self._raw_chunks:
            courses[c.get("course", "general")] = courses.get(c.get("course", "general"), 0) + 1
        return {
            "loaded": self._loaded,
            "backend": self._backend_name,
            "total_chunks": len(self._raw_chunks),
            "by_course": courses,
            "index_path": str(self.persist_path),
        }

    def count_source_chunks(self, source: str) -> int:
        """Count scanned chunks regardless of the selected retrieval backend."""
        if not self._loaded:
            self.load()
        with self._lock:
            return sum(chunk.get("source") == source for chunk in self._raw_chunks)


# ---------------------------------------------------------------------------
# FIX-04：chunk 来源 → 图谱知识点 ID 解析（进程内缓存）
# 章节 frontmatter（kp_ids）是唯一权威来源；uploads/ 等无 frontmatter 的
# 文档解析不到时返回空列表，调用方不得写入错误知识点。
# ---------------------------------------------------------------------------
_KP_SOURCE_CACHE: Dict[str, List[str]] = {}


def _kp_ids_for_source(course: str, source: str) -> List[str]:
    cache_key = f"{course}::{source}"
    if cache_key in _KP_SOURCE_CACHE:
        return list(_KP_SOURCE_CACHE[cache_key])

    kp_ids: List[str] = []
    try:
        filename = Path(str(source).replace("\\", "/")).name
        from backend.app.services.knowledge_index import get_knowledge_index

        index = get_knowledge_index(course)
        for chapter in index.chapters:
            if chapter.filename == filename:
                kp_ids = [str(kp) for kp in chapter.kp_ids]
                break
    except Exception as exc:  # noqa: BLE001 — 无章节目录的课程（纯上传课）正常走空映射
        logger.debug(f"[RAG] kp 解析跳过 {source}: {exc}")

    _KP_SOURCE_CACHE[cache_key] = list(kp_ids)
    return kp_ids


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        from backend.app.core.config import get_config
        cfg = get_config()
        kb_path = Path(cfg.rag.knowledge_base_path)
        # 持久化索引落盘到 data/ads/rag/
        try:
            persist = Path(getattr(cfg.rag, "vector_db_path", "")).parent / "rag" / "knowledge_index.json"
        except Exception:
            persist = Path("data/ads/rag/knowledge_index.json")
        _rag_service = RAGService(kb_path, persist_path=persist)
        _rag_service.load()
    return _rag_service
