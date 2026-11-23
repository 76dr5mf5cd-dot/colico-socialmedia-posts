from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

DEFAULT_SETTINGS_PATH = "settings.yaml"


@dataclass
class Brand:
    name: str = "Colico"
    website: str = "https://www.colico.be"
    owner: str = "Marc Noël"
    description: str = (
        "Fotografie en olieverfschilderijen: natuur, landschappen, steden, "
        "feesten, documentair werk en portretten."
    )


@dataclass
class Captions:
    language: str = "nl"
    tone: str = "warm, uitnodigend, artistiek"
    model: str = "pixtral-12b-2409"
    extra_instructions: str = ""
    hashtags_extra: list[str] = field(default_factory=lambda: ["colico", "marcnoel"])


@dataclass
class Photos:
    folder: Path = Path("./photos")
    public_url_base: str = ""
    max_per_scan: int = 5


@dataclass
class Limits:
    instagram_caption_chars: int = 2200
    bluesky_caption_chars: int = 300


@dataclass
class Settings:
    brand: Brand = field(default_factory=Brand)
    captions: Captions = field(default_factory=Captions)
    photos: Photos = field(default_factory=Photos)
    limits: Limits = field(default_factory=Limits)

    @property
    def mistral_api_key(self) -> str:
        return os.environ.get("MISTRAL_API_KEY", "")

    @property
    def bluesky_handle(self) -> str:
        return os.environ.get("BLUESKY_HANDLE", "")

    @property
    def bluesky_app_password(self) -> str:
        return os.environ.get("BLUESKY_APP_PASSWORD", "")

    @property
    def bluesky_pds(self) -> str:
        return os.environ.get("BLUESKY_PDS", "https://bsky.social")

    @property
    def instagram_token(self) -> str:
        return os.environ.get("IG_ACCESS_TOKEN", "")

    @property
    def instagram_user_id(self) -> str:
        return os.environ.get("IG_USER_ID", "")


def load_settings(path: str | Path = DEFAULT_SETTINGS_PATH) -> Settings:
    settings_path = Path(path)
    load_dotenv(settings_path.parent / ".env")
    load_dotenv()
    data: dict = {}
    if settings_path.exists():
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
    settings = Settings()
    brand = data.get("brand") or {}
    settings.brand = Brand(
        name=brand.get("name", settings.brand.name),
        website=brand.get("website", settings.brand.website),
        owner=brand.get("owner", settings.brand.owner),
        description=brand.get("description", settings.brand.description),
    )
    caps = data.get("captions") or {}
    settings.captions = Captions(
        language=caps.get("language", settings.captions.language),
        tone=caps.get("tone", settings.captions.tone),
        model=caps.get("model", settings.captions.model),
        extra_instructions=caps.get("extra_instructions", ""),
        hashtags_extra=caps.get(
            "hashtags_extra", settings.captions.hashtags_extra
        ),
    )
    photos = data.get("photos") or {}
    settings.photos = Photos(
        folder=Path(photos.get("folder", settings.photos.folder)),
        public_url_base=photos.get("public_url_base", ""),
        max_per_scan=photos.get("max_per_scan", settings.photos.max_per_scan),
    )
    limits = data.get("limits") or {}
    settings.limits = Limits(
        instagram_caption_chars=limits.get(
            "instagram_caption_chars", settings.limits.instagram_caption_chars
        ),
        bluesky_caption_chars=limits.get(
            "bluesky_caption_chars", settings.limits.bluesky_caption_chars
        ),
    )
    return settings
