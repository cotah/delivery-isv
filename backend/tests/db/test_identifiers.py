from uuid import UUID

from app.db.identifiers import new_public_id, new_uuid


def test_new_uuid_returns_uuid_v4() -> None:
    result = new_uuid()
    assert isinstance(result, UUID)
    assert result.version == 4


def test_new_uuid_generates_unique_ids_in_bulk() -> None:
    ids = {new_uuid() for _ in range(1000)}
    assert len(ids) == 1000


def test_new_public_id_default_prefix_and_length() -> None:
    result = new_public_id()
    assert result.startswith("ISV-")
    assert len(result) == 12  # "ISV-" (4 chars) + 8 chars


def test_new_public_id_custom_prefix() -> None:
    result = new_public_id("ORD")
    assert result.startswith("ORD-")
    assert len(result) == 12


def test_new_public_id_excludes_ambiguous_chars() -> None:
    forbidden = set("0O1IL")
    for _ in range(200):
        pid = new_public_id()
        suffix = pid.split("-", 1)[1]
        assert not (set(suffix) & forbidden), f"Found forbidden char in {pid}"


def test_new_public_id_generates_unique_ids_in_bulk() -> None:
    ids = {new_public_id() for _ in range(1000)}
    assert len(ids) == 1000
