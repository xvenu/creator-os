import pytest
from app.modules.content.engine import generate_content, persist_content


@pytest.mark.parametrize("kind", ["news", "profile", "review", "ranking", "short"])
def test_generate_all_kinds(kind):
    c = generate_content(kind, "Test Song", genre="pop", artist="Tester")
    assert c.title and c.body and c.kind == kind


def test_generate_invalid_kind():
    with pytest.raises(ValueError):
        generate_content("podcast", "X")


def test_persist_content(db):
    c = generate_content("news", "Hit Song")
    row = persist_content(db, c)
    assert row.id is not None and row.status == "draft"
