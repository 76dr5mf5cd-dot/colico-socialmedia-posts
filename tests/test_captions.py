import json as jsonlib

import pytest

from colico_agent import captions


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return FakeResponse(
            {
                "choices": [
                    {"message": {"content": jsonlib.dumps(self.payload, ensure_ascii=False)}}
                ]
            }
        )


def test_parse_plain_json():
    data = captions.parse_caption_response(
        '{"caption": "Morgenlicht", "hashtags": ["#Natuur", "zon "], "alt_text": "Zonsopgang"}'
    )
    assert data == {
        "caption": "Morgenlicht",
        "hashtags": ["natuur", "zon"],
        "alt_text": "Zonsopgang",
    }


def test_parse_fenced_json():
    raw = '```json\n{"caption": "c", "hashtags": ["a"], "alt_text": "b"}\n```'
    assert captions.parse_caption_response(raw)["caption"] == "c"


def test_build_prompt_mentions_brand_and_language():
    from colico_agent.config import Brand, Captions

    prompt = captions.build_prompt(Brand(), Captions(language="nl"))
    assert "Colico" in prompt and "colico.be" in prompt
    assert "nl" in prompt.lower() or "Nederland" in prompt
    assert '"caption"' in prompt


@pytest.fixture
def tiny_image(tmp_path):
    from PIL import Image

    path = tmp_path / "shot.jpg"
    Image.new("RGB", (64, 48), color=(10, 120, 200)).save(path, format="JPEG")
    return path


def test_generate_draft_sends_image_and_parses(tiny_image, monkeypatch):
    from colico_agent.config import Settings

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    settings = Settings()
    payload = {"caption": "ochtend", "hashtags": ["mist"], "alt_text": "mist boven veld"}
    session = FakeSession(payload)
    result = captions.generate_draft(tiny_image, settings, session=session)
    assert result["caption"] == "ochtend"
    call = session.calls[0]
    assert "api.mistral.ai" in call["url"]
    content = call["json"]["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert call["headers"]["Authorization"] == "Bearer test-key"
