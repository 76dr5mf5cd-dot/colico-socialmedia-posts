import json
from pathlib import Path

from colico_agent import store as store_mod
from colico_agent.store import STATUS_APPROVED, STATUS_DRAFTED, Store


def make_store(tmp_path):
    return Store(tmp_path / "work")


def test_new_images_skips_registered(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for name in ("a.jpg", "b.png", "c.txt"):
        (photos / name).write_bytes(b"x")
    work = make_store(tmp_path)
    found = work.new_images(photos)
    assert sorted(p.name for p in found) == ["a.jpg", "b.png"]
    work.register("a.jpg", "deadbeef", "a-deadbeef", {"caption": "hi"})
    found = work.new_images(photos)
    assert [p.name for p in found] == ["b.png"]


def test_approve_reads_back_edited_draft(tmp_path):
    work = make_store(tmp_path)
    work.register("fotos/zon.jpg", "abc12345", "zon-abc12345", {"caption": "oud"})
    work.write_draft("zon-abc12345", {"caption": "nieuw"}, {})
    rel = work.approve("zon-abc12345")
    assert rel == "fotos/zon.jpg"
    entry = work.entry(rel)
    assert entry["status"] == STATUS_APPROVED
    assert entry["draft"]["caption"] == "nieuw"


def test_mark_posted_sets_status_and_log(tmp_path):
    work = make_store(tmp_path)
    work.register("x.jpg", "abcd1234", "x-abcd1234", {"caption": "c"})
    work.approve("x-abcd1234")
    work.mark_posted("x-abcd1234", "bluesky", {"uri": "at://...", "cid": "cid1"})
    entry = work.entry("x.jpg")
    assert entry["status"] == store_mod.STATUS_POSTED
    assert entry["posted"]["bluesky"]["cid"] == "cid1"
    assert work.state["posted"] == [
        {"draft_id": "x-abcd1234", "platform": "bluesky", "result": {"uri": "at://...", "cid": "cid1"}}
    ]


def test_state_persists(tmp_path):
    work = make_store(tmp_path)
    work.register("p.jpg", "d1", "p-d1", {"caption": "c"})
    again = Store(tmp_path / "work")
    assert "p.jpg" in again.state["photos"]
    assert again.entry("p.jpg")["status"] == STATUS_DRAFTED
    assert (Path(tmp_path) / "work" / "drafts" / "p-d1.json").exists() is False
    work.write_draft("p-d1", {"caption": "c"}, {})
    assert json.loads((tmp_path / "work" / "drafts" / "p-d1.json").read_text())["caption"] == "c"
