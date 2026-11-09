"""Vector database: Qdrant.

Every chunk is stored as a Qdrant point = ID + Vector + Payload. The payload carries the chunk
text and its metadata (paper_id, paper_name, page, section, chunk_index) so results can be
filtered by paper and cited back to the source.

Tables extracted by the dual-stream parser live in a second collection (QDRANT_TABLE_COLLECTION).
Each table point embeds a caption + columns summary and carries the Markdown and JSON grid.
"""
import uuid
import warnings
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import settings
from app.logger import logger
from app.rag.chunker import Chunk
from app.rag.table_extractor import ExtractedTable

UPSERT_BATCH = 64


def point_id(paper_id: str, chunk_index: int) -> str:
    """Deterministic ID, so re-indexing a paper overwrites (upserts) its points."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{paper_id}:{chunk_index}"))


def table_point_id(paper_id: str, table_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{paper_id}:table:{table_index}"))


def paper_filter(paper_ids: list[str] | None) -> models.Filter | None:
    if not paper_ids:
        return None
    return models.Filter(must=[models.FieldCondition(key="paper_id", match=models.MatchAny(any=paper_ids))])


class VectorStore:
    def __init__(
        self,
        client: QdrantClient,
        collection: str = settings.QDRANT_COLLECTION,
        table_collection: str = settings.QDRANT_TABLE_COLLECTION,
    ):
        self.client = client
        self.collection = collection
        self.table_collection = table_collection
        self._ready: set[str] = set()

    def ensure_collection(self) -> None:
        self._ensure(self.collection)
        self._ensure(self.table_collection)

    def _ensure(self, name: str) -> None:
        """create_collection(): called once; vector size must match the embedding dimension."""
        if name in self._ready:
            return
        if not self.client.collection_exists(name):
            logger.info(f"Creating Qdrant collection '{name}' (size={settings.EMBEDDING_DIM}, cosine)")
            self.client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(size=settings.EMBEDDING_DIM, distance=models.Distance.COSINE),
            )
            # Payload index enables fast metadata filtering by paper (no-op in in-memory mode).
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                self.client.create_payload_index(
                    collection_name=name,
                    field_name="paper_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        else:
            size = self.client.get_collection(name).config.params.vectors.size
            if size != settings.EMBEDDING_DIM:
                raise RuntimeError(
                    f"Qdrant collection '{name}' stores {size}-dim vectors but EMBEDDING_DIM is "
                    f"{settings.EMBEDDING_DIM}. Use a new collection name or re-create the collection."
                )
        self._ready.add(name)

    def upsert_chunks(self, paper_id: str, paper_name: str, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """upsert(): insert new points, or update points whose ID already exists."""
        self.ensure_collection()
        points = [
            models.PointStruct(
                id=point_id(paper_id, chunk.chunk_index),
                vector=vector,
                payload={
                    "paper_id": paper_id,
                    "paper_name": paper_name,
                    "chunk_index": chunk.chunk_index,
                    "page": chunk.page,
                    "section": chunk.section,
                    "text": chunk.text,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        for start in range(0, len(points), UPSERT_BATCH):
            self.client.upsert(collection_name=self.collection, points=points[start:start + UPSERT_BATCH], wait=True)
        return len(points)

    def search(
        self,
        query_vector: list[float],
        paper_ids: list[str] | None = None,
        limit: int = settings.TOP_K,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """query_points(): top-k most similar chunks, optionally filtered to some papers."""
        self.ensure_collection()
        result = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=paper_filter(paper_ids),
            limit=limit,
            score_threshold=score_threshold or None,
            with_payload=True,
        )
        return [{"id": str(p.id), "score": p.score, **p.payload} for p in result.points]

    def get_paper_chunks(self, paper_id: str) -> list[dict[str, Any]]:
        """All chunks of one paper in reading order (payload only)."""
        self.ensure_collection()
        chunks, offset = [], None
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=paper_filter([paper_id]),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(r.payload for r in records)
            if offset is None:
                break
        return sorted(chunks, key=lambda c: c["chunk_index"])

    def delete_paper(self, paper_id: str) -> None:
        """delete(): remove every point (chunks and tables) that belongs to a paper."""
        self.ensure_collection()
        for name in (self.collection, self.table_collection):
            self.client.delete(
                collection_name=name,
                points_selector=models.FilterSelector(filter=paper_filter([paper_id])),
                wait=True,
            )

    # --- tables (Stream B) ---
    def upsert_tables(
        self, paper_id: str, paper_name: str, tables: list[ExtractedTable], vectors: list[list[float]]
    ) -> int:
        self._ensure(self.table_collection)
        points = [
            models.PointStruct(
                id=table_point_id(paper_id, t.table_index),
                vector=vector,
                payload={
                    "paper_id": paper_id,
                    "paper_name": paper_name,
                    "table_index": t.table_index,
                    "page": t.page,
                    "caption": t.caption,
                    "headers": t.headers,
                    "markdown": t.markdown,
                    "json_data": t.json_data,
                },
            )
            for t, vector in zip(tables, vectors, strict=True)
        ]
        for start in range(0, len(points), UPSERT_BATCH):
            self.client.upsert(
                collection_name=self.table_collection, points=points[start:start + UPSERT_BATCH], wait=True
            )
        return len(points)

    def search_tables(
        self,
        query_vector: list[float],
        paper_ids: list[str] | None = None,
        limit: int = settings.TOP_K_TABLES,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Top-k tables whose caption/column summary is closest to the query."""
        self._ensure(self.table_collection)
        result = self.client.query_points(
            collection_name=self.table_collection,
            query=query_vector,
            query_filter=paper_filter(paper_ids),
            limit=limit,
            score_threshold=score_threshold or None,
            with_payload=True,
        )
        return [{"id": str(p.id), "score": p.score, **p.payload} for p in result.points]

    def count_tables(self) -> int:
        self._ensure(self.table_collection)
        return self.client.count(collection_name=self.table_collection, exact=True).count

    def info(self) -> dict[str, Any]:
        """get_collection(): vector count, dimension, distance metric and status."""
        self.ensure_collection()
        info = self.client.get_collection(self.collection)
        params = info.config.params.vectors
        return {
            "collection": self.collection,
            "points_count": info.points_count or 0,
            "vector_size": params.size,
            "distance": str(params.distance.value if hasattr(params.distance, "value") else params.distance),
            "status": str(info.status.value if hasattr(info.status, "value") else info.status),
        }


@lru_cache
def get_vector_store() -> VectorStore:
    if settings.QDRANT_URL == ":memory:":
        client = QdrantClient(":memory:")
    elif settings.QDRANT_URL in ("local", ":local:", "embedded") or (
        not settings.QDRANT_URL.startswith("http://") and not settings.QDRANT_URL.startswith("https://")
    ):
        qdrant_dir = settings.DATA_DIR / "qdrant" if settings.QDRANT_URL in ("local", ":local:", "embedded") else settings.QDRANT_URL
        client = QdrantClient(path=str(qdrant_dir))
    else:
        try:
            client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=3)
            # Fast health check to ensure connection is actually alive
            client.get_collections()
        except Exception as e:
            logger.warning(
                f"Qdrant server at {settings.QDRANT_URL} is unreachable ({e}). "
                f"Using local embedded vector database at 'data/qdrant'."
            )
            qdrant_dir = settings.DATA_DIR / "qdrant"
            qdrant_dir.mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=str(qdrant_dir))
    return VectorStore(client)
