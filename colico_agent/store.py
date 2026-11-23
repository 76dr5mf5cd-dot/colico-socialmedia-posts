from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

STATUS_NEW = "new"
STATUS_DRAFTED = "drafted"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_POSTED = "posted"


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "post"


def sha1_of(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Store:
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.state_path = workdir / "state.json"
        self.drafts_dir = workdir / "drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.state: dict = self._load()

    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"photos": {}, "posted": []}

    def save(self) -> None:
        self.state_path.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def entry(self, rel_path: str) -> dict:
        return self.state["photos"].setdefault(rel_path, {})

    def draft_path(self, draft_id: str) -> Path:
        return self.drafts_dir / f"{draft_id}.json"

    def new_images(self, folder: Path) -> list[Path]:
        found = []
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = path.relative_to(folder).as_posix()
            if rel in self.state["photos"]:
                continue
            found.append(path)
        return found

    def register(self, rel_path: str, digest: str, draft_id: str, draft: dict) -> None:
        entry = self.entry(rel_path)
        entry.update(
            {
                "sha1": digest,
                "status": STATUS_DRAFTED,
                "draft_id": draft_id,
                "draft": draft,
            }
        )
        self.save()

    def read_draft(self, draft_id: str) -> dict:
        return json.loads(self.draft_path(draft_id).read_text(encoding="utf-8"))

    def write_draft(self, draft_id: str, draft: dict, meta: dict) -> None:
        self.draft_path(draft_id).write_text(
            json.dumps({**draft, **meta}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def set_status(self, rel_path: str, status: str) -> None:
        entry = self.entry(rel_path)
        entry["status"] = status
        if entry.get("draft_id"):
            self.state.setdefault("draft_index", {})[entry["draft_id"]] = rel_path
        for draft_id, linked in self.state.get("draft_index", {}).items():
            if linked == rel_path:
                continue
        self.save()

    def approve(self, draft_id: str) -> str | None:
        rel = self._rel_for_draft(draft_id)
        if rel:
            entry = self.entry(rel)
            entry["status"] = STATUS_APPROVED
            try:
                entry["draft"] = self.read_draft(draft_id)
            except FileNotFoundError:
                pass
            self.save()
        return rel

    def reject(self, draft_id: str) -> None:
        rel = self._rel_for_draft(draft_id)
        if rel:
            self.entry(rel)["status"] = STATUS_REJECTED
            self.save()

    def _rel_for_draft(self, draft_id: str) -> str | None:
        for rel, entry in self.state["photos"].items():
            if entry.get("draft_id") == draft_id:
                return rel
        return None

    def mark_posted(
        self, draft_id: str, platform: str, result: dict
    ) -> None:
        rel = self._rel_for_draft(draft_id)
        if not rel:
            return
        entry = self.entry(rel)
        entry.setdefault("posted", {})[platform] = result
        posted_platforms = set(entry["posted"].keys())
        all_platforms = {"instagram", "bluesky"}
        if posted_platforms & all_platforms:
            entry["status"] = STATUS_POSTED
        self.state["posted"].append(
            {"draft_id": draft_id, "platform": platform, "result": result}
        )
        self.save()

    def pending_approval(self) -> list[tuple[str, dict]]:
        return [
            (rel, entry)
            for rel, entry in self.state["photos"].items()
            if entry.get("status") == STATUS_DRAFTED
        ]

    def approved(self) -> list[tuple[str, dict]]:
        return [
            (rel, entry)
            for rel, entry in self.state["photos"].items()
            if entry.get("status") == STATUS_APPROVED
        ]
