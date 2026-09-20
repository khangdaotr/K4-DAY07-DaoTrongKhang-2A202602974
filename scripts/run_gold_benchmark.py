"""Run the shared Shopee gold queries through the student's src package."""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import Document, EmbeddingStore, RecursiveChunker  # noqa: E402


CORPUS_DIR = ROOT / "data" / "shopee-ecommerce"
GOLD_PATH = CORPUS_DIR / "gold.json"
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def parse_document(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    body = text
    if text.startswith("---\n"):
        _, frontmatter, body = text.split("---", 2)
        for line in frontmatter.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"')
    return metadata, body.strip()


def terms(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]


class TfidfEmbedder:
    def __init__(self, texts: list[str]) -> None:
        documents = [set(terms(text)) for text in texts]
        document_frequency = Counter(term for doc in documents for term in doc)
        self.vocabulary = {
            term: index for index, term in enumerate(sorted(document_frequency))
        }
        count = len(documents)
        self.idf = {
            term: math.log((1 + count) / (1 + frequency)) + 1
            for term, frequency in document_frequency.items()
        }

    def __call__(self, text: str) -> list[float]:
        counts = Counter(terms(text))
        vector = [0.0] * len(self.vocabulary)
        for term, frequency in counts.items():
            index = self.vocabulary.get(term)
            if index is not None:
                vector[index] = (1 + math.log(frequency)) * self.idf[term]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    chunker = RecursiveChunker(chunk_size=1800)
    documents: list[Document] = []

    for path in sorted(CORPUS_DIR.glob("*.md")):
        metadata, body = parse_document(path)
        doc_id = metadata.get("doc_id", path.stem)
        for index, chunk in enumerate(chunker.chunk(body)):
            documents.append(
                Document(
                    id=f"{doc_id}#{index}",
                    content=chunk,
                    metadata={**metadata, "doc_id": doc_id, "chunk_index": index},
                )
            )

    queries = [item["query"] for item in gold["queries"]]
    embedder = TfidfEmbedder([doc.content for doc in documents] + queries)
    store = EmbeddingStore("gold_benchmark", embedding_fn=embedder)
    store.add_documents(documents)

    output = []
    for item in gold["queries"]:
        results = store.search_with_filter(
            item["query"],
            top_k=3,
            metadata_filter=item.get("metadata_filter"),
        )
        top = results[0] if results else None
        gold_ids = {span["doc_id"] for span in item["gold_spans"]}
        anchor = item["anchor"].casefold()
        output.append(
            {
                "id": item["id"],
                "query": item["query"],
                "top_1": {
                    "doc_id": top["metadata"]["doc_id"] if top else None,
                    "chunk_index": top["metadata"].get("chunk_index") if top else None,
                    "score": round(top["score"], 6) if top else None,
                    "relevant": bool(
                        top
                        and top["metadata"]["doc_id"] in gold_ids
                        and anchor in top["content"].casefold()
                    ),
                    "preview": re.sub(r"\s+", " ", top["content"])[:1200] if top else "",
                },
                "top_3": [
                    {
                        "doc_id": result["metadata"]["doc_id"],
                        "chunk_index": result["metadata"].get("chunk_index"),
                        "score": round(result["score"], 6),
                        "has_anchor": anchor in result["content"].casefold(),
                    }
                    for result in results
                ],
            }
        )

    print(json.dumps({"chunks": len(documents), "results": output}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
