"""RAG subpackage — index lifecycle + HyDE + RRF fusion."""
from backend.app.services.rag.hyde import HydeResult, HydeRetriever
from backend.app.services.rag.index_manager import IndexManager, get_index_manager
from backend.app.services.rag.rrf import (
    DEFAULT_RRF_K,
    fuse_with_metadata,
    reciprocal_rank_fusion,
)

__all__ = [
    "IndexManager",
    "get_index_manager",
    "HydeRetriever",
    "HydeResult",
    "reciprocal_rank_fusion",
    "fuse_with_metadata",
    "DEFAULT_RRF_K",
]
