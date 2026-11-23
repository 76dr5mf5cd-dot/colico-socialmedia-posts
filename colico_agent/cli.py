from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

from PIL import Image

from .bluesky import publish_image as publish_bsky
from .captions import generate_draft
from .config import load_settings
from .instagram import publish_photo as publish_ig
from .store import (
    STATUS_APPROVED,
    STATUS_DRAFTED,
    STATUS_POSTED,
    Store,
    sha1_of,
    slugify,
)

EDITOR = os.environ.get("EDITOR", "nano")


def _draft_id(rel_path: str, digest: str) -> str:
    return f"{slugify(Path(rel_path).stem)}-{digest[:8]}"


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def cmd_scan(args, settings) -> int:
    store = Store(Path(args.workdir))
    folder = Path(args.folder or settings.photos.folder).resolve()
    if not folder.exists():
        print(f"Fotomap bestaat niet: {folder}")
        return 1
    if not settings.mistral_api_key:
        print("Geen MISTRAL_API_KEY gezet; zet die in .env of je omgeving.")
        return 1
    new_images = store.new_images(folder)[: settings.photos.max_per_scan]
    if not new_images:
        print("Geen nieuwe foto's gevonden.")
        return 0
    for image in new_images:
        rel = image.relative_to(folder).as_posix()
        digest = sha1_of(image)
        print(f"Concept maken voor {rel} ...")
        try:
            draft = generate_draft(image, settings)
        except Exception as error:
            print(f"  Fout bij onderschriftgeneratie: {error}", file=sys.stderr)
            continue
        draft_id = _draft_id(rel, digest)
        store.register(rel, digest, draft_id, draft)
        store.write_draft(
            draft_id,
            draft,
            {
                "draft_id": draft_id,
                "image": str(image),
                "rel_path": rel,
                "status": STATUS_DRAFTED,
            },
        )
        print(f"  Concept klaar: {draft_id}")
    return 0


def cmd_drafts(args, settings) -> int:
    store = Store(Path(args.workdir))
    pending = store.pending_approval()
    if not pending:
        print("Geen concepten die op goedkeuring wachten.")
        return 0
    for rel, entry in pending:
        draft = entry.get("draft", {})
        print(f"[{entry['draft_id']}] {rel} — status: {entry['status']}")
        print(f"  caption: {draft.get('caption', '')}")
        tags = " ".join("#" + tag for tag in draft.get("hashtags", []))
        print(f"  hashtags: {tags}")
    return 0


def cmd_show(args, settings) -> int:
    store = Store(Path(args.workdir))
    draft = store.read_draft(args.draft_id)
    print(json.dumps(draft, indent=2, ensure_ascii=False))
    return 0


def cmd_edit(args, settings) -> int:
    store = Store(Path(args.workdir))
    path = store.draft_path(args.draft_id)
    subprocess.run([EDITOR, str(path)], check=True)
    updated = json.loads(path.read_text(encoding="utf-8"))
    store.write_draft(args.draft_id, updated, updated)
    print(f"Concept {args.draft_id} bijgewerkt.")
    return 0


def cmd_approve(args, settings) -> int:
    store = Store(Path(args.workdir))
    rel = store.approve(args.draft_id)
    if not rel:
        print(f"Concept {args.draft_id} niet gevonden.")
        return 1
    print(f"Goedgekeurd: {args.draft_id} ({rel})")
    return 0


def cmd_reject(args, settings) -> int:
    store = Store(Path(args.workdir))
    store.reject(args.draft_id)
    print(f"Afgewezen: {args.draft_id}")
    return 0


def _public_url(rel_path: str, settings) -> str | None:
    base = settings.photos.public_url_base
    if not base:
        return None
    return base.rstrip("/") + "/" + urllib.parse.quote(rel_path)


def _truncated(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _publish_one(store, rel_path: str, entry: dict, platforms: list[str], settings, dry_run: bool) -> None:
    draft_id = entry["draft_id"]
    draft = store.read_draft(draft_id)
    image = Path(draft.get("image", ""))
    if not image.exists():
        print(f"  Foto ontbreekt: {image}", file=sys.stderr)
        return
    caption = draft.get("caption", "")
    tags = draft.get("hashtags", [])
    caption_full = "\n\n".join(
        part for part in [caption, " ".join("#" + t.lstrip("#") for t in tags)] if part
    )
    width, height = _image_size(image)

    if "bluesky" in platforms:
        if not (settings.bluesky_handle and settings.bluesky_app_password):
            print("  Bluesky overgeslagen: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD ontbreken.")
        else:
            credentials = {
                "pds": settings.bluesky_pds,
                "handle": settings.bluesky_handle,
                "app_password": settings.bluesky_app_password,
                "width": width,
                "height": height,
            }
            if dry_run:
                print(f"  [dry-run] Bluesky: {_truncated(caption_full, 80)}")
            else:
                result = publish_bsky(image, draft, credentials)
                store.mark_posted(draft_id, "bluesky", result)
                print(f"  Bluesky geplaatst: {result['uri']}")

    if "instagram" in platforms:
        url = _public_url(rel_path, settings)
        if not (settings.instagram_token and settings.instagram_user_id):
            print("  Instagram overgeslagen: IG_ACCESS_TOKEN / IG_USER_ID ontbreken.")
        elif not url:
            print(
                "  Instagram overgeslagen: de Graph API heeft een publieke URL nodig. "
                "Zet photos.public_url_base in settings.yaml (bijv. je eigen website)."
            )
        elif dry_run:
            print(f"  [dry-run] Instagram ({url}): {_truncated(caption_full, 80)}")
        else:
            result = publish_ig(
                url, caption_full[: settings.limits.instagram_caption_chars],
                settings.instagram_user_id, settings.instagram_token,
            )
            store.mark_posted(draft_id, "instagram", result)
            print(f"  Instagram geplaatst: post_id {result['post_id']}")


def cmd_publish(args, settings) -> int:
    store = Store(Path(args.workdir))
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    if args.all:
        targets = store.approved()
    elif args.draft_id:
        rel = store._rel_for_draft(args.draft_id)
        targets = [(rel, store.entry(rel))] if rel else []
        if not targets:
            print(f"Concept {args.draft_id} niet gevonden.")
            return 1
    else:
        print("Geef een concept-id of --all.")
        return 1
    if not targets:
        print("Geen goedgekeurde concepten om te publiceren.")
        return 0
    for rel, entry in targets:
        print(f"Publiceren: {rel} op {', '.join(platforms)}")
        _publish_one(store, rel, entry, platforms, settings, args.dry_run)
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workdir", default=argparse.SUPPRESS, help="Map met state.json en drafts/")
    common.add_argument("--settings", default=argparse.SUPPRESS, help="Pad naar settings.yaml")

    parser = argparse.ArgumentParser(
        prog="colico-agent",
        description="Maakt en publiceert Colico-posts uit een map met foto's.",
    )
    parser.add_argument(
        "--workdir", default=".", help="Map met state.json en drafts/ (standaard huidige map)"
    )
    parser.add_argument(
        "--settings", default="settings.yaml", help="Pad naar settings.yaml"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", parents=[common], help="Nieuwe foto's vinden en concepten maken")
    scan.add_argument("--folder", default="")
    scan.set_defaults(func=cmd_scan)

    drafts = sub.add_parser("drafts", parents=[common], help="Concepten tonen die wachten op goedkeuring")
    drafts.set_defaults(func=cmd_drafts)

    show = sub.add_parser("show", parents=[common], help="Volledig concept tonen")
    show.add_argument("draft_id")
    show.set_defaults(func=cmd_show)

    edit = sub.add_parser("edit", parents=[common], help="Concept bewerken in je editor")
    edit.add_argument("draft_id")
    edit.set_defaults(func=cmd_edit)

    approve = sub.add_parser("approve", parents=[common], help="Concept goedkeuren")
    approve.add_argument("draft_id")
    approve.set_defaults(func=cmd_approve)

    reject = sub.add_parser("reject", parents=[common], help="Concept afwijzen")
    reject.add_argument("draft_id")
    reject.set_defaults(func=cmd_reject)

    publish = sub.add_parser("publish", parents=[common], help="Goedgekeurd concept publiceren")
    publish.add_argument("draft_id", nargs="?", default=None)
    publish.add_argument("--all", action="store_true", help="Alle goedgekeurde concepten")
    publish.add_argument(
        "--platforms", default="bluesky,instagram", help="Komma-gescheiden: bluesky,instagram"
    )
    publish.add_argument("--dry-run", action="store_true")
    publish.set_defaults(func=cmd_publish)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(args.settings)
    return args.func(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
