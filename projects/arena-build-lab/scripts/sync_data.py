#!/usr/bin/env python3
"""Download and normalize the static data used by Arena Build Lab."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


SCHEMA_VERSION = 1
LOCALE = "zh_CN"
FOCUS_CHAMPIONS = ("Aatrox", "Darius")
VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
ARENA_AUGMENTS_URL_TEMPLATE = (
    "https://raw.communitydragon.org/{patch}/cdragon/arena/zh_cn.json"
)


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {"br", "p", "div", "li"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def markup_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def fetch_json(url: str) -> Tuple[Any, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "arena-build-lab-data-sync/0.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    return json.loads(payload.decode("utf-8")), digest


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source(url: str, sha256: str) -> Dict[str, str]:
    return {"url": url, "sha256": sha256}


def community_dragon_patch(data_dragon_patch: str) -> str:
    parts = data_dragon_patch.split(".")
    if len(parts) < 2:
        raise ValueError(f"invalid Data Dragon patch: {data_dragon_patch}")
    return ".".join(parts[:2])


def normalize_champions(
    summary: Dict[str, Any], details: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    records = []
    for champion in summary["data"].values():
        detail = details.get(champion["id"])
        record = {
            "id": champion["id"],
            "key": int(champion["key"]),
            "name": champion["name"],
            "title": champion["title"],
            "tags": champion.get("tags", []),
            "partype": champion.get("partype", ""),
            "stats": champion.get("stats", {}),
        }
        if detail:
            record["passive"] = {
                "name": detail["passive"]["name"],
                "description": markup_to_text(detail["passive"]["description"]),
            }
            record["spells"] = [
                {
                    "id": spell["id"],
                    "name": spell["name"],
                    "description": markup_to_text(spell["description"]),
                    "tooltip": markup_to_text(spell.get("tooltip", "")),
                    "cooldown": spell.get("cooldown", []),
                    "cost": spell.get("cost", []),
                }
                for spell in detail.get("spells", [])
            ]
        records.append(record)
    return sorted(records, key=lambda item: item["id"])


def normalize_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = []
    for item_id, item in payload["data"].items():
        if not item.get("maps", {}).get("30", False):
            continue
        # Data Dragon currently contains one unnamed, non-purchasable Arena
        # placeholder. It cannot be recognized or recommended to a player.
        if not item.get("name"):
            continue
        records.append(
            {
                "id": int(item_id),
                "nameRaw": item["name"],
                "name": markup_to_text(item["name"]),
                "descriptionRaw": item.get("description", ""),
                "description": markup_to_text(item.get("description", "")),
                "gold": item.get("gold", {}),
                "purchasable": bool(item.get("gold", {}).get("purchasable", False)),
                "inStore": item.get("inStore", True),
                "tags": item.get("tags", []),
                "stats": item.get("stats", {}),
                "from": [int(value) for value in item.get("from", [])],
                "into": [int(value) for value in item.get("into", [])],
                "image": item.get("image", {}).get("full", ""),
                "arenaMap": True,
            }
        )
    return sorted(records, key=lambda item: item["id"])


def normalize_augments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = []
    for augment in payload["augments"]:
        records.append(
            {
                "id": int(augment["id"]),
                "apiName": augment["apiName"],
                "name": augment["name"],
                "rarity": int(augment["rarity"]),
                "descriptionRaw": augment.get("desc", ""),
                "description": markup_to_text(augment.get("desc", "")),
                "tooltipRaw": augment.get("tooltip", ""),
                "tooltip": markup_to_text(augment.get("tooltip", "")),
                "iconSmall": augment.get("iconSmall", ""),
                "iconLarge": augment.get("iconLarge", ""),
                "dataValues": augment.get("dataValues", {}),
                "calculations": augment.get("calculations", {}),
            }
        )
    return sorted(records, key=lambda item: item["id"])


def ensure_unique(records: Iterable[Dict[str, Any]], field: str, label: str) -> None:
    values = [record[field] for record in records]
    if len(values) != len(set(values)):
        raise ValueError(f"{label} field {field!r} contains duplicate values")


def validate(
    champions: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
    augments: List[Dict[str, Any]],
) -> None:
    if len(champions) < 170:
        raise ValueError(f"champion count is unexpectedly low: {len(champions)}")
    if len(items) < 100:
        raise ValueError(f"Arena item count is unexpectedly low: {len(items)}")
    if len(augments) < 150:
        raise ValueError(f"augment count is unexpectedly low: {len(augments)}")

    ensure_unique(champions, "id", "champion")
    ensure_unique(champions, "key", "champion")
    ensure_unique(items, "id", "item")
    ensure_unique(augments, "id", "augment")
    ensure_unique(augments, "apiName", "augment")

    champions_by_id = {record["id"]: record for record in champions}
    for champion_id in FOCUS_CHAMPIONS:
        champion = champions_by_id.get(champion_id)
        if not champion:
            raise ValueError(f"missing focus champion: {champion_id}")
        if len(champion.get("spells", [])) != 4:
            raise ValueError(f"missing spell details for: {champion_id}")

    for item in items:
        if not item["arenaMap"] or not item["name"]:
            raise ValueError(f"invalid Arena item: {item.get('id')}")

    for augment in augments:
        if not augment["name"] or not augment["iconSmall"]:
            raise ValueError(f"invalid augment: {augment.get('id')}")


def envelope(
    patch: str,
    source_info: Any,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "gamePatch": patch,
        "locale": LOCALE,
        "source": source_info,
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", help="Data Dragon patch; defaults to latest")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_dir / "data" / "normalized",
        help="directory containing versioned normalized snapshots",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    versions, versions_hash = fetch_json(VERSIONS_URL)
    patch = args.patch or versions[0]
    base = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/{LOCALE}"
    champions_url = f"{base}/champion.json"
    items_url = f"{base}/item.json"
    augments_url = ARENA_AUGMENTS_URL_TEMPLATE.format(
        patch=community_dragon_patch(patch)
    )

    champions_payload, champions_hash = fetch_json(champions_url)
    items_payload, items_hash = fetch_json(items_url)
    augments_payload, augments_hash = fetch_json(augments_url)

    detail_payloads: Dict[str, Dict[str, Any]] = {}
    detail_sources = []
    for champion_id in FOCUS_CHAMPIONS:
        url = f"{base}/champion/{champion_id}.json"
        payload, digest = fetch_json(url)
        detail_payloads[champion_id] = payload["data"][champion_id]
        detail_sources.append(source(url, digest))

    champions = normalize_champions(champions_payload, detail_payloads)
    items = normalize_items(items_payload)
    augments = normalize_augments(augments_payload)
    validate(champions, items, augments)

    output_dir = args.output_dir / patch
    champions_source = {
        "summary": source(champions_url, champions_hash),
        "focusDetails": detail_sources,
    }
    write_json(
        output_dir / "champions.json",
        envelope(patch, champions_source, champions),
    )
    write_json(
        output_dir / "items-arena.json",
        envelope(patch, source(items_url, items_hash), items),
    )
    write_json(
        output_dir / "augments.json",
        envelope(patch, source(augments_url, augments_hash), augments),
    )

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "gamePatch": patch,
        "locale": LOCALE,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "versionIndex": source(VERSIONS_URL, versions_hash),
        "recordCounts": {
            "champions": len(champions),
            "itemsArenaCatalog": len(items),
            "itemsArenaPurchasable": sum(item["purchasable"] for item in items),
            "augments": len(augments),
        },
        "files": ["champions.json", "items-arena.json", "augments.json"],
    }
    write_json(output_dir / "manifest.json", manifest)

    print(
        f"synced patch {patch}: "
        f"{len(champions)} champions, {len(items)} Arena catalog items "
        f"({sum(item['purchasable'] for item in items)} purchasable), "
        f"{len(augments)} augments"
    )
    print(f"output: {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"data sync failed: {exc}", file=sys.stderr)
        sys.exit(1)
