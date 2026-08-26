from app import retrieval
from app.ingestion import parse_file
from app.retrieval import INDEXED_RECORDS, add_records, retrieve


def test_retrieve_payment_dependencies() -> None:
    results = retrieve("What depends on Payment Service?")
    assert results
    assert any("Payment Service" in result.text for result in results)


def test_unknown_question_returns_no_context() -> None:
    assert retrieve("Tell me about vacations") == []


def test_csv_can_be_ingested_and_retrieved(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(retrieval, "INDEX_PATH", tmp_path / "index.json")
    INDEXED_RECORDS.clear()
    chunks = parse_file("systems.csv", b"name,owner\nInventory API,Supply Team")
    assert add_records("systems.csv", chunks) == 1
    results = retrieve("Who owns Inventory API?")
    assert results[0].source == "systems.csv"
