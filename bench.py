"""Benchmark retrieval trên corpus Shopee bằng 5 câu hỏi trong gold.json.

Chạy mặc định:
    python bench.py

Mặc định dùng LocalEmbedder. Có thể đổi backend qua EMBEDDING_PROVIDER:
    EMBEDDING_PROVIDER=local | openai | gemini | mock
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from src import (
    Document,
    EmbeddingStore,
    FixedSizeChunker,
    GeminiEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    RecursiveChunker,
    SentenceChunker,
    _mock_embed,
)


CORPUS_DIR = Path("data/shopee-ecommerce")
GOLD_PATH = CORPUS_DIR / "gold.json"
CHUNK_SIZE = 1800
TOP_K = 3


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """Tách YAML frontmatter đơn giản và phần thân của một file Markdown."""
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}

    if not text.startswith("---"):
        return metadata, text.strip()

    parts = text.split("---", 2)
    if len(parts) != 3:
        return metadata, text.strip()

    _, frontmatter, content = parts
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata, content.strip()


def load_and_chunk_documents(
    corpus_dir: Path,
    chunker,
) -> list[Document]:
    """Đọc corpus, bỏ frontmatter và chuyển từng chunk thành Document."""
    documents: list[Document] = []

    for path in sorted(corpus_dir.glob("*.md")):
        frontmatter, content = parse_frontmatter(path)

        for index, chunk in enumerate(chunker.chunk(content)):
            documents.append(
                Document(
                    id=f"{path.stem}#{index}",
                    content=chunk,
                    metadata={
                        **frontmatter,
                        "doc_id": path.stem,
                        "chunk_index": index,
                        "source": str(path),
                    },
                )
            )

    return documents


class CachedEmbedder:
    """Cache embeddings; batch-precompute when the backend is LocalEmbedder."""

    def __init__(self, backend, texts: list[str]) -> None:
        self.backend = backend
        self._backend_name = getattr(backend, "_backend_name", backend.__class__.__name__)
        self.cache: dict[str, list[float]] = {}

        unique_texts = list(dict.fromkeys(texts))
        if isinstance(backend, LocalEmbedder):
            vectors = backend.model.encode(
                unique_texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=True,
            )
            self.cache.update(
                (text, vector.tolist() if hasattr(vector, "tolist") else list(vector))
                for text, vector in zip(unique_texts, vectors)
            )

    def __call__(self, text: str) -> list[float]:
        if text not in self.cache:
            self.cache[text] = self.backend(text)
        return self.cache[text]


def select_embedder() -> Callable[[str], list[float]]:
    """Khởi tạo embedding backend; mặc định dùng mock để luôn chạy được."""
    load_dotenv(override=False)
    provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()

    try:
        if provider == "local":
            return LocalEmbedder(
                model_name=os.getenv(
                    "LOCAL_EMBEDDING_MODEL",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                )
            )
        if provider == "openai":
            return OpenAIEmbedder(
                model_name=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            )
        if provider == "gemini":
            return GeminiEmbedder(
                model_name=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
            )
        if provider != "mock":
            print(f"Không nhận ra EMBEDDING_PROVIDER={provider!r}; chuyển sang mock.")
    except Exception as error:
        print(f"Không khởi tạo được backend {provider!r}: {error}")
        print("Chuyển sang MockEmbedder để benchmark vẫn có thể chạy.")

    return _mock_embed


def preview(text: str, limit: int = 180) -> str:
    """Rút gọn nội dung chunk để output dễ đọc."""
    clean = re.sub(r"\s+", " ", text).strip()
    return clean if len(clean) <= limit else clean[:limit].rstrip() + "..."


def evaluate_results(item: dict, results: list[dict]) -> tuple[int, int | None]:
    """Return rubric score (2/1/0) and one-based rank of the first gold hit."""
    anchor = item.get("anchor", "").casefold()
    gold_doc_ids = {span["doc_id"] for span in item.get("gold_spans", [])}
    for rank, result in enumerate(results, start=1):
        doc_id = str(result["metadata"].get("doc_id", ""))
        if doc_id in gold_doc_ids and anchor in result["content"].casefold():
            return (2 if rank == 1 else 1), rank
    return 0, None


def print_top_three(item: dict, results: list[dict]) -> None:
    anchor = item.get("anchor", "").casefold()
    gold_doc_ids = {span["doc_id"] for span in item.get("gold_spans", [])}
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]
        doc_id = str(metadata.get("doc_id", "unknown"))
        is_gold = doc_id in gold_doc_ids and anchor in result["content"].casefold()
        print(
            f"  {rank}. score={result['score']:.6f} "
            f"doc_id={doc_id} chunk={metadata.get('chunk_index')} "
            f"gold_hit={'YES' if is_gold else 'NO'}"
        )
        print(f"     {preview(result['content'])}")


def main() -> int:
    if not CORPUS_DIR.is_dir():
        print(f"Không tìm thấy corpus: {CORPUS_DIR}")
        return 1
    if not GOLD_PATH.is_file():
        print(f"Không tìm thấy bộ câu hỏi: {GOLD_PATH}")
        return 1

    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    queries = gold.get("queries", [])
    if len(queries) != 5:
        print(f"Cảnh báo: gold.json hiện có {len(queries)} câu hỏi, không phải 5.")

    strategies = {
        "fixed_size": FixedSizeChunker(chunk_size=CHUNK_SIZE, overlap=200),
        "by_sentences": SentenceChunker(max_sentences_per_chunk=8),
        "recursive": RecursiveChunker(chunk_size=CHUNK_SIZE),
    }
    document_sets = {
        name: load_and_chunk_documents(CORPUS_DIR, chunker)
        for name, chunker in strategies.items()
    }
    if not all(document_sets.values()):
        print("Corpus không tạo được chunk nào.")
        return 1

    raw_embedder = select_embedder()
    all_texts = [
        document.content
        for documents in document_sets.values()
        for document in documents
    ] + [item["query"] for item in queries]
    embedder = CachedEmbedder(raw_embedder, all_texts)
    backend_name = getattr(embedder, "_backend_name", embedder.__class__.__name__)
    stores: dict[str, EmbeddingStore] = {}
    for name, documents in document_sets.items():
        store = EmbeddingStore(f"shopee_benchmark_{name}", embedding_fn=embedder)
        store.add_documents(documents)
        stores[name] = store

    print(f"Embedding backend : {backend_name}")
    print(f"Số file Markdown  : {len(list(CORPUS_DIR.glob('*.md')))}")
    for name, documents in document_sets.items():
        average = sum(len(doc.content) for doc in documents) / len(documents)
        print(f"{name:14}: count={len(documents):3d}, avg_length={average:.1f}")

    totals: dict[str, int] = {}
    for strategy_name, store in stores.items():
        print("\n" + "#" * 88)
        print(f"CHIẾN LƯỢC: {strategy_name}")
        total = 0
        for number, item in enumerate(queries, start=1):
            results = store.search_with_filter(
                item["query"],
                top_k=TOP_K,
                metadata_filter=item.get("metadata_filter"),
            )
            score, hit_rank = evaluate_results(item, results)
            total += score
            print("=" * 88)
            print(f"Q{number}: {item['query']}")
            print(
                f"Filter={item.get('metadata_filter') or 'Không có'} | "
                f"gold_rank={hit_rank or '-'} | rubric_score={score}"
            )
            print_top_three(item, results)
        totals[strategy_name] = total
        print(f"TỔNG ĐIỂM {strategy_name}: {total}/10")

    filter_item = next(
        (item for item in queries if item.get("metadata_filter")),
        None,
    )
    if filter_item:
        print("\n" + "#" * 88)
        print("A/B METADATA FILTER")
        print(f"Query: {filter_item['query']}")
        for strategy_name, store in stores.items():
            print(f"\n[{strategy_name}] A — không filter")
            unfiltered = store.search_with_filter(
                filter_item["query"], top_k=TOP_K, metadata_filter=None
            )
            print_top_three(filter_item, unfiltered)
            print(f"[{strategy_name}] B — có filter {filter_item['metadata_filter']}")
            filtered = store.search_with_filter(
                filter_item["query"],
                top_k=TOP_K,
                metadata_filter=filter_item["metadata_filter"],
            )
            print_top_three(filter_item, filtered)

    print("\n" + "#" * 88)
    print("TỔNG KẾT ĐIỂM (doc_id + anchor, thang 2/1/0)")
    for strategy_name, total in totals.items():
        print(f"- {strategy_name}: {total}/10")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
