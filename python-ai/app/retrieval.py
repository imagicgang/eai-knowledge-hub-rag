import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeRecord:
    text: str
    source: str
    keywords: frozenset[str]


DEMO_RECORDS = [
    KnowledgeRecord("Payment Service calls Fraud Service for risk checks.", "architecture/payment.drawio", frozenset({"payment", "fraud", "depend", "calls"})),
    KnowledgeRecord("Payment Service writes transactions to Payment PostgreSQL.", "catalog/services.yaml", frozenset({"payment", "database", "postgresql", "writes"})),
    KnowledgeRecord("Order API is owned by the Commerce Platform team.", "catalog/services.yaml", frozenset({"order", "api", "owner", "team"})),
    KnowledgeRecord("Order Service publishes order.created events to Kafka.", "architecture/order.drawio", frozenset({"order", "kafka", "publish", "downstream"})),
    KnowledgeRecord("Checkout Web calls Order API, which calls Payment Service.", "architecture/checkout.drawio", frozenset({"checkout", "order", "payment", "upstream", "downstream"})),
]

INDEX_PATH = Path(os.getenv("KNOWLEDGE_INDEX_PATH", "/data/knowledge-index.json"))


def keywords_for(value: str) -> frozenset[str]:
    return frozenset(word.lower() for word in re.findall(r"[^\W_]{2,}", value, re.UNICODE))


def _load_index() -> list[KnowledgeRecord]:
    if not INDEX_PATH.exists():
        return []
    try:
        items = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return [KnowledgeRecord(item["text"], item["source"], frozenset(item["keywords"])) for item in items]
    except (OSError, ValueError, KeyError, TypeError):
        return []


INDEXED_RECORDS = _load_index()


def add_records(source: str, chunks: list[str], metadata: str = "") -> int:
    records = [KnowledgeRecord(f"{metadata} {chunk}".strip(), source, keywords_for(f"{metadata} {chunk}")) for chunk in chunks if chunk.strip()]
    INDEXED_RECORDS[:] = [record for record in INDEXED_RECORDS if record.source != source]
    INDEXED_RECORDS.extend(records)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [{**asdict(record), "keywords": sorted(record.keywords)} for record in INDEXED_RECORDS]
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(records)


def retrieve(question: str, limit: int = 3) -> list[KnowledgeRecord]:
    words = keywords_for(question)
    records = DEMO_RECORDS + INDEXED_RECORDS
    ranked = sorted(records, key=lambda item: len(words & item.keywords), reverse=True)
    return [item for item in ranked if words & item.keywords][:limit]
