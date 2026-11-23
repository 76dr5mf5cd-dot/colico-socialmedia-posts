from colico_agent import instagram


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    def post(self, url, data=None, params=None, timeout=None):
        self.calls.append({"url": url, "data": data, "params": params})
        if "media_publish" in url:
            return FakeResponse({"id": "1791"})
        return FakeResponse({"id": "178000"})

    def get(self, url, params=None, timeout=None):
        return FakeResponse({"status_code": self.statuses.pop(0)})


def test_publish_photo_polls_then_publishes():
    session = FakeSession(["IN_PROGRESS", "FINISHED"])
    result = instagram.publish_photo(
        "https://www.colico.be/media/foto.jpg",
        "Morgenlicht",
        "178414000",
        "token",
        session=session,
    )
    assert result == {"creation_id": "178000", "post_id": "1791"}
    container_call = session.calls[0]
    assert container_call["data"]["image_url"] == "https://www.colico.be/media/foto.jpg"
    assert container_call["params"] == {"access_token": "token"}
    publish_call = session.calls[-1]
    assert publish_call["data"] == {"creation_id": "178000"}


def test_error_status_raises():
    import pytest

    session = FakeSession(["ERROR"])
    with pytest.raises(RuntimeError):
        instagram.publish_photo("https://x/f.jpg", "c", "id", "tok", session=session)
