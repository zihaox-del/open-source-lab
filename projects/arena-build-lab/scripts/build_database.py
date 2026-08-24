#!/usr/bin/env python3
"""Build a versioned SQLite content database from normalized JSON snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable


ABILITY_SLOTS = ("Q", "W", "E", "R")


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def insert_metadata(connection: sqlite3.Connection, values: Dict[str, Any]) -> None:
    connection.executemany(
        "INSERT INTO content_metadata(key, value) VALUES (?, ?)",
        ((key, str(value)) for key, value in sorted(values.items())),
    )


def insert_champions(
    connection: sqlite3.Connection, records: Iterable[Dict[str, Any]]
) -> None:
    for champion in records:
        connection.execute(
            """
            INSERT INTO champions(
                id, champion_key, name, title, partype, tags_json, stats_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                champion["id"],
                champion["key"],
                champion["name"],
                champion["title"],
                champion["partype"],
                compact_json(champion["tags"]),
                compact_json(champion["stats"]),
            ),
        )

        passive = champion.get("passive")
        if passive:
            connection.execute(
                """
                INSERT INTO champion_abilities(
                    champion_id, slot, ability_id, name, description, tooltip,
                    cooldown_json, cost_json
                ) VALUES (?, 'P', NULL, ?, ?, '', '[]', '[]')
                """,
                (champion["id"], passive["name"], passive["description"]),
            )

        for slot, ability in zip(ABILITY_SLOTS, champion.get("spells", [])):
            connection.execute(
                """
                INSERT INTO champion_abilities(
                    champion_id, slot, ability_id, name, description, tooltip,
                    cooldown_json, cost_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    champion["id"],
                    slot,
                    ability["id"],
                    ability["name"],
                    ability["description"],
                    ability["tooltip"],
                    compact_json(ability["cooldown"]),
                    compact_json(ability["cost"]),
                ),
            )


def insert_items(
    connection: sqlite3.Connection, records: Iterable[Dict[str, Any]]
) -> None:
    connection.executemany(
        """
        INSERT INTO items(
            id, name, name_raw, description, description_raw, purchasable,
            in_store, gold_json, tags_json, stats_json, from_json, into_json, image
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item["id"],
                item["name"],
                item["nameRaw"],
                item["description"],
                item["descriptionRaw"],
                int(item["purchasable"]),
                int(item["inStore"]),
                compact_json(item["gold"]),
                compact_json(item["tags"]),
                compact_json(item["stats"]),
                compact_json(item["from"]),
                compact_json(item["into"]),
                item["image"],
            )
            for item in records
        ),
    )


def insert_augments(
    connection: sqlite3.Connection, records: Iterable[Dict[str, Any]]
) -> None:
    connection.executemany(
        """
        INSERT INTO augments(
            id, api_name, name, rarity, description, description_raw, tooltip,
            tooltip_raw, icon_small, icon_large, data_values_json,
            calculations_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                augment["id"],
                augment["apiName"],
                augment["name"],
                augment["rarity"],
                augment["description"],
                augment["descriptionRaw"],
                augment["tooltip"],
                augment["tooltipRaw"],
                augment["iconSmall"],
                augment["iconLarge"],
                compact_json(augment["dataValues"]),
                compact_json(augment["calculations"]),
            )
            for augment in records
        ),
    )


def validate_snapshot(
    manifest: Dict[str, Any],
    champions: Dict[str, Any],
    items: Dict[str, Any],
    augments: Dict[str, Any],
) -> str:
    patches = {
        manifest["gamePatch"],
        champions["gamePatch"],
        items["gamePatch"],
        augments["gamePatch"],
    }
    if len(patches) != 1:
        raise ValueError(f"snapshot contains mixed patches: {sorted(patches)}")

    counts = manifest["recordCounts"]
    actual = {
        "champions": len(champions["records"]),
        "itemsArenaCatalog": len(items["records"]),
        "itemsArenaPurchasable": sum(
            item["purchasable"] for item in items["records"]
        ),
        "augments": len(augments["records"]),
    }
    if counts != actual:
        raise ValueError(f"manifest counts do not match snapshot: {counts} != {actual}")
    return patches.pop()


def verify_database(connection: sqlite3.Connection, manifest: Dict[str, Any]) -> None:
    expected = manifest["recordCounts"]
    actual = {
        "champions": connection.execute("SELECT count(*) FROM champions").fetchone()[0],
        "itemsArenaCatalog": connection.execute("SELECT count(*) FROM items").fetchone()[0],
        "itemsArenaPurchasable": connection.execute(
            "SELECT count(*) FROM items WHERE purchasable = 1"
        ).fetchone()[0],
        "augments": connection.execute("SELECT count(*) FROM augments").fetchone()[0],
    }
    if expected != actual:
        raise ValueError(f"database counts do not match manifest: {expected} != {actual}")

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(f"SQLite integrity check failed: {integrity}")


def build_database(snapshot_dir: Path, output_path: Path, schema_path: Path) -> None:
    manifest = load_json(snapshot_dir / "manifest.json")
    champions = load_json(snapshot_dir / "champions.json")
    items = load_json(snapshot_dir / "items-arena.json")
    augments = load_json(snapshot_dir / "augments.json")
    patch = validate_snapshot(manifest, champions, items, augments)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()

    try:
        connection = sqlite3.connect(str(temporary_path))
        try:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
            with connection:
                insert_metadata(
                    connection,
                    {
                        "schemaVersion": manifest["schemaVersion"],
                        "gamePatch": patch,
                        "locale": manifest["locale"],
                        "generatedAt": manifest["generatedAt"],
                        "sourceManifest": compact_json(manifest),
                    },
                )
                insert_champions(connection, champions["records"])
                insert_items(connection, items["records"])
                insert_augments(connection, augments["records"])
            verify_database(connection, manifest)
            connection.execute("VACUUM")
        finally:
            connection.close()
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", default="16.16.1")
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=project_dir / "database" / "content-schema.sql",
    )
    args = parser.parse_args()
    args.snapshot_dir = args.snapshot_dir or (
        project_dir / "data" / "normalized" / args.patch
    )
    args.output = args.output or (
        project_dir / "dist" / f"arena-content-{args.patch}.db"
    )
    return args


def main() -> int:
    args = parse_args()
    build_database(args.snapshot_dir, args.output, args.schema)
    print(f"built SQLite content database: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(f"database build failed: {exc}", file=sys.stderr)
        sys.exit(1)

