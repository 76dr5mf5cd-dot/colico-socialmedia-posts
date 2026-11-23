from __future__ import annotations

import unicodedata

import requests

MAX_TEXT_CHARS = 300


def _session(credentials: dict, session=None):
    return session or requests


def _create_session(credentials: dict, session=None) -> dict:
    url = credentials["pds"].rstrip("/") + "/xrpc/com.atproto.server.createSession"
    response = session.post(
        url,
        json={"identifier": credentials["handle"], "password": credentials["app_password"]},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _trim(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return unicodedata.normalize("NFC", text)[: limit - 1].rstrip() + "…"


def publish_image(image_path, draft, credentials: dict, session=None) -> dict:
    session = session or requests
    session_data = _create_session(credentials, session)
    upload_url = credentials["pds"].rstrip("/") + "/xrpc/com.atproto.repo.uploadBlob"
    with image_path.open("rb") as handle:
        image_bytes = handle.read()
    upload = session.post(
        upload_url,
        headers={
            "Authorization": f"Bearer {session_data['accessJwt']}",
            "Content-Type": "image/jpeg",
        },
        data=image_bytes,
        timeout=120,
    )
    upload.raise_for_status()
    blob = upload.json()["blob"]

    text_parts = [draft.get("caption", "").strip()]
    tags = draft.get("hashtags", [])
    if tags:
        text_parts.append(" ".join("#" + tag.lstrip("#") for tag in tags))
    text = "\n\n".join(part for part in text_parts if part)
    record = {
        "$type": "app.bsky.feed.post",
        "text": _trim(text),
        "createdAt": credentials.get("created_at"),
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [
                {
                    "alt": draft.get("alt_text", ""),
                    "image": blob,
                    "aspectRatio": {
                        "width": credentials.get("width", 1),
                        "height": credentials.get("height", 1),
                    },
                }
            ],
        },
    }
    record_url = credentials["pds"].rstrip("/") + "/xrpc/com.atproto.repo.createRecord"
    create = session.post(
        record_url,
        headers={"Authorization": f"Bearer {session_data['accessJwt']}"},
        json={
            "repo": session_data["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        timeout=30,
    )
    create.raise_for_status()
    data = create.json()
    return {"uri": data["uri"], "cid": data["cid"]}
