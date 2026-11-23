from __future__ import annotations

import time

import requests

GRAPH_VERSION = "v21.0"
CONTAINER_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 5


def _base() -> str:
    return f"https://graph.facebook.com/{GRAPH_VERSION}"


def start_container(image_url, caption, ig_user_id, token, session=None) -> str:
    session = session or requests
    response = session.post(
        f"{_base()}/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption.strip()},
        params={"access_token": token},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["id"]


def wait_for_container(creation_id, token, session=None, deadline=CONTAINER_TIMEOUT_SECONDS) -> bool:
    session = session or requests
    url = f"{_base()}/{creation_id}"
    waited = 0
    while waited <= deadline:
        response = session.get(
            url,
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        response.raise_for_status()
        status = response.json().get("status_code", "")
        if status == "FINISHED":
            return True
        if status in {"EXPIRED", "ERROR"}:
            raise RuntimeError(f"Instagram container {creation_id} kwam in status {status}")
        time.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS
    raise TimeoutError(f"Instagram container {creation_id} klaarde niet binnen {deadline}s")


def publish_photo(image_url, caption, ig_user_id, token, session=None) -> dict:
    session = session or requests
    creation_id = start_container(image_url, caption, ig_user_id, token, session)
    wait_for_container(creation_id, token, session)
    response = session.post(
        f"{_base()}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id},
        params={"access_token": token},
        timeout=60,
    )
    response.raise_for_status()
    return {"creation_id": creation_id, "post_id": response.json()["id"]}
