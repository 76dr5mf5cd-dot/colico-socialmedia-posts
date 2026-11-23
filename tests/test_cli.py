from pathlib import Path

import pytest
from PIL import Image

from colico_agent import cli
from colico_agent.config import load_settings
from colico_agent.store import STATUS_APPROVED, STATUS_POSTED, Store


@pytest.fixture
def project(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    image = photos / "zonsondergang.jpg"
    Image.new("RGB", (120, 90), color=(200, 120, 40)).save(image, format="JPEG")
    (tmp_path / "settings.yaml").write_text(
        "photos:\n  folder: ./photos\n  public_url_base: https://www.colico.be/insta\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "MISTRAL_API_KEY=k\nBLUESKY_HANDLE=colico.bsky.social\nBLUESKY_APP_PASSWORD=pw\n"
        "IG_USER_ID=1781\nIG_ACCESS_TOKEN=igtok\n",
        encoding="utf-8",
    )
    return tmp_path, photos, image


def test_full_flow_scan_review_publish(tmp_path, project, monkeypatch):
    tmp, photos, image = project
    monkeypatch.chdir(tmp)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")

    from colico_agent.captions import parse_caption_response as _orig

    def fake_generate_draft(path, settings, session=None):
        return {
            "caption": "Gouden uur boven de Leie",
            "hashtags": ["natuur", "colico"],
            "alt_text": "oranje lucht boven rivier",
        }

    monkeypatch.setattr(cli, "generate_draft", fake_generate_draft)

    assert cli.main(["--workdir", str(tmp / "work"), "--settings", "settings.yaml", "scan"]) == 0

    work = Store(tmp / "work")
    assert len(work.pending_approval()) == 1
    rel, entry = work.pending_approval()[0]
    draft_id = entry["draft_id"]
    assert work.draft_path(draft_id).exists()

    assert cli.main(["--workdir", str(tmp / "work"), "--settings", "settings.yaml", "approve", draft_id]) == 0
    work = Store(tmp / "work")
    rel2, entry2 = work.approved()[0]
    assert entry2["status"] == STATUS_APPROVED

    monkeypatch.setattr(
        cli, "publish_bsky", lambda img, draft, creds: {"uri": "at://p", "cid": "c"}
    )
    monkeypatch.setattr(
        cli, "publish_ig", lambda url, cap, uid, token, session=None: {"creation_id": "1", "post_id": "9"}
    )
    assert (
        cli.main(
            ["--workdir", str(tmp / "work"), "--settings", "settings.yaml", "publish", draft_id]
        )
        == 0
    )
    work = Store(tmp / "work")
    entry3 = work.entry(rel2)
    assert entry3["status"] == STATUS_POSTED
    assert entry3["posted"]["bluesky"]["cid"] == "c"
    assert entry3["posted"]["instagram"]["post_id"] == "9"


def test_scan_without_api_key_fails(project, monkeypatch):
    tmp, photos, image = project
    monkeypatch.chdir(tmp)
    (tmp / ".env").unlink()
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert cli.main(["--workdir", str(tmp / "work"), "--settings", "settings.yaml", "scan"]) == 1
