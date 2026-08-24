import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_DIR / "scripts" / "build_database.py"
SNAPSHOT_DIR = PROJECT_DIR / "data" / "normalized" / "16.16.1"
SCHEMA_PATH = PROJECT_DIR / "database" / "content-schema.sql"

SPEC = importlib.util.spec_from_file_location("build_database", MODULE_PATH)
build_database = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(build_database)


def load(name):
    return json.loads((SNAPSHOT_DIR / name).read_text(encoding="utf-8"))


class DatabaseBuildTest(unittest.TestCase):
    def test_builds_queryable_content_database(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            database_path = Path(temporary_dir) / "arena-content.db"
            build_database.build_database(SNAPSHOT_DIR, database_path, SCHEMA_PATH)

            connection = sqlite3.connect(database_path)
            try:
                metadata = dict(connection.execute("SELECT key, value FROM content_metadata"))
                self.assertEqual(metadata["gamePatch"], "16.16.1")
                self.assertEqual(metadata["locale"], "zh_CN")

                self.assertEqual(
                    connection.execute("SELECT count(*) FROM champions").fetchone()[0],
                    173,
                )
                self.assertEqual(
                    connection.execute("SELECT count(*) FROM items").fetchone()[0],
                    231,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM items WHERE purchasable = 1"
                    ).fetchone()[0],
                    187,
                )
                self.assertEqual(
                    connection.execute("SELECT count(*) FROM augments").fetchone()[0],
                    225,
                )

                champions = connection.execute(
                    "SELECT id, name, title FROM champions WHERE id IN ('Aatrox', 'Darius')"
                ).fetchall()
                self.assertEqual(
                    set(champions),
                    {
                        ("Aatrox", "暗裔剑魔", "亚托克斯"),
                        ("Darius", "诺克萨斯之手", "德莱厄斯"),
                    },
                )
                for champion_id in ("Aatrox", "Darius"):
                    slots = connection.execute(
                        "SELECT slot FROM champion_abilities WHERE champion_id = ?",
                        (champion_id,),
                    ).fetchall()
                    self.assertEqual({slot[0] for slot in slots}, {"P", "Q", "W", "E", "R"})

                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM items WHERE name = '黑色切割者' AND purchasable = 1"
                    ).fetchone()[0],
                    "黑色切割者",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM augments WHERE name = '热身动作'"
                    ).fetchone()[0],
                    "热身动作",
                )
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT count(*) FROM tags").fetchone()[0], 0)
                self.assertEqual(
                    connection.execute("SELECT count(*) FROM synergy_rules").fetchone()[0],
                    0,
                )
            finally:
                connection.close()

    def test_rejects_mixed_patch_snapshot(self):
        manifest = load("manifest.json")
        champions = copy.deepcopy(load("champions.json"))
        champions["gamePatch"] = "0.0.0"

        with self.assertRaisesRegex(ValueError, "mixed patches"):
            build_database.validate_snapshot(
                manifest,
                champions,
                load("items-arena.json"),
                load("augments.json"),
            )


if __name__ == "__main__":
    unittest.main()
