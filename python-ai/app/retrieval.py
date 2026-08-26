from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeRecord:
    text: str
    source: str
    keywords: frozenset[str]


RECORDS = [
    KnowledgeRecord("Payment Service calls Fraud Service for risk checks.", "architecture/payment.drawio", frozenset({"payment", "fraud", "depend", "calls"})),
    KnowledgeRecord("Payment Service writes transactions to Payment PostgreSQL.", "catalog/services.yaml", frozenset({"payment", "database", "postgresql", "writes"})),
    KnowledgeRecord("Order API is owned by the Commerce Platform team.", "catalog/services.yaml", frozenset({"order", "api", "owner", "team"})),
    KnowledgeRecord("Order Service publishes order.created events to Kafka.", "architecture/order.drawio", frozenset({"order", "kafka", "publish", "downstream"})),
    KnowledgeRecord("Checkout Web calls Order API, which calls Payment Service.", "architecture/checkout.drawio", frozenset({"checkout", "order", "payment", "upstream", "downstream"})),
]


def retrieve(question: str, limit: int = 3) -> list[KnowledgeRecord]:
    words = {word.strip("?.,!").lower() for word in question.split()}
    ranked = sorted(RECORDS, key=lambda item: len(words & item.keywords), reverse=True)
    return [item for item in ranked if words & item.keywords][:limit]
