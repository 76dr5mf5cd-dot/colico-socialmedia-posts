import json
from pathlib import Path

from colico_agent import bluesky


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, headers=None, json=None, data=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "data": data})
        if "createSession" in url:
            return FakeResponse({"accessJwt": "jwt", "did": "did:plc:abc"})
        if "uploadBlob" in url:
            return FakeResponse({"blob": {"$type": "blob", "ref": "x", "size": 10}})
        if "createRecord" in url:
            return FakeResponse({"uri": "at://did/app.bsky.feed.post/1", "cid": "cid1"})
        raise AssertionError(url)


CREDENTIALS = {
    "pds": "https://bsky.social",
    "handle": "colico.bsky.social",
    "app_password": "pw",
    "width": 1080,
    "height": 1080,
}


def test_publish_image_uploads_blob_and_creates_record(tmp_path):
    image = tmp_path / "shot.jpg"
    image.write_bytes(b"fakejpeg")
    draft = {
        "caption": "Zonsondergang",
        "hashtags": ["natuur", "colico"],
        "alt_text": "oranje lucht",
    }
    session = FakeSession()
    result = bluesky.publish_image(image, draft, CREDENTIALS, session=session)
    assert result["cid"] == "cid1"
    urls = [c["url"] for c in session.calls]
    assert any("createSession" in u for u in urls)
    assert any("uploadBlob" in u for u in urls)
    assert any("createRecord" in u for u in urls)

    record_call = next(c for c in session.calls if "createRecord" in c["url"])
    record = record_call["json"]["record"]
    assert record["text"] == "Zonsondergang\n\n#natuur #colico"
    assert record["embed"]["images"][0]["alt"] == "oranje lucht"
    assert record["embed"]["images"][0]["aspectRatio"] == {"width": 1080, "height": 1080}
    upload_call = next(c for c in session.calls if "uploadBlob" in c["url"])
    assert upload_call["data"] == b"fakejpeg"
    assert upload_call["headers"]["Content-Type"] == "image/jpeg"


def test_trim_long_text():
    assert bluesky._trim("a" * 350).endswith("…")
    assert len(bluesky._trim("a" * 350)) == 300
    assert bluesky._trim("kort") == "kort"
