from app.retrieval import retrieve


def test_retrieve_payment_dependencies() -> None:
    results = retrieve("What depends on Payment Service?")
    assert results
    assert any("Payment Service" in result.text for result in results)


def test_unknown_question_returns_no_context() -> None:
    assert retrieve("Tell me about vacations") == []
