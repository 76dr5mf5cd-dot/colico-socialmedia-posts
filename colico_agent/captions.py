from __future__ import annotations

import base64
import io
import json

import requests
from PIL import Image

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
VISION_MAX_SIDE = 1568
JPEG_QUALITY = 88


def image_data_uri(path) -> str:
    image = Image.open(path)
    image = image.convert("RGB")
    image.thumbnail((VISION_MAX_SIDE, VISION_MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def build_prompt(brand, captions) -> str:
    hashtags = ", ".join(captions.hashtags_extra)
    lines = [
        f"Je bent de socialmedia-copywriter van {brand.name} ({brand.website}), "
        f"het atelier van {brand.owner}: {brand.description}",
        f"Kijk naar de foto en schrijf een {captions.language}tintige social post.",
        f"Toon: {captions.tone}.",
    ]
    if captions.extra_instructions:
        lines.append(f"Extra instructies: {captions.extra_instructions}")
    lines += [
        f"Werk deze hashtags in of voeg ze toe: {hashtags}.",
        "Antwoord uitsluitend met JSON met precies deze sleutels:",
        '{"caption": "...", "hashtags": ["tag1", "tag2"], "alt_text": "..."}',
        "caption: pakkend onderschrift, max 3 korte zinnen, geen hashtags in de caption.",
        "hashtags: 6 tot 10 relevante tags zonder # teken.",
        "alt_text: objectieve beschrijving van de afbeelding voor schermlezers, max 200 tekens.",
    ]
    return "\n".join(lines)


def parse_caption_response(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    hashtags = [
        tag.lstrip("#").strip().lower()
        for tag in data.get("hashtags", [])
        if str(tag).strip()
    ]
    return {
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": hashtags,
        "alt_text": str(data.get("alt_text", "")).strip(),
    }


def generate_draft(image_path, settings, session=None) -> dict:
    session = session or requests
    payload = {
        "model": settings.captions.model,
        "temperature": 0.7,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(settings.brand, settings.captions)},
                    {
                        "type": "image_url",
                        "image_url": image_data_uri(image_path),
                    },
                ],
            }
        ],
    }
    response = session.post(
        MISTRAL_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
        timeout=180,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return parse_caption_response(content)
