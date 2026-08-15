from masoora import DataCatalog


def test_catalog_basic_mapping_ops() -> None:
    cat = DataCatalog({"a": 1})
    cat["b"] = [1, 2]
    assert cat["a"] == 1
    assert cat["b"] == [1, 2]
    assert len(cat) == 2
    assert set(cat) == {"a", "b"}
    del cat["a"]
    assert "a" not in cat


def test_catalog_snapshot_is_a_copy() -> None:
    cat = DataCatalog({"a": 1})
    snap = cat.snapshot()
    cat["b"] = 2
    assert snap == {"a": 1}
