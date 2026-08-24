import json
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = PROJECT_DIR / "data" / "normalized" / "16.16.1"


def load(name):
    return json.loads((SNAPSHOT_DIR / name).read_text(encoding="utf-8"))


class SnapshotTest(unittest.TestCase):
    def test_manifest_matches_snapshot_files(self):
        manifest = load("manifest.json")
        champions = load("champions.json")["records"]
        items = load("items-arena.json")["records"]
        augments = load("augments.json")["records"]

        self.assertEqual(manifest["gamePatch"], "16.16.1")
        self.assertEqual(manifest["recordCounts"]["champions"], len(champions))
        self.assertEqual(manifest["recordCounts"]["itemsArenaCatalog"], len(items))
        self.assertEqual(
            manifest["recordCounts"]["itemsArenaPurchasable"],
            sum(item["purchasable"] for item in items),
        )
        self.assertEqual(manifest["recordCounts"]["augments"], len(augments))

    def test_focus_champions_have_skill_details(self):
        records = {record["id"]: record for record in load("champions.json")["records"]}

        for champion_id in ("Aatrox", "Darius"):
            self.assertIn(champion_id, records)
            self.assertEqual(len(records[champion_id]["spells"]), 4)
            self.assertTrue(records[champion_id]["passive"]["name"])

    def test_static_identity_fields_are_unique(self):
        champions = load("champions.json")["records"]
        items = load("items-arena.json")["records"]
        augments = load("augments.json")["records"]

        self.assertEqual(len({item["id"] for item in champions}), len(champions))
        self.assertEqual(len({item["id"] for item in items}), len(items))
        self.assertEqual(len({item["id"] for item in augments}), len(augments))
        self.assertEqual(len({item["apiName"] for item in augments}), len(augments))

    def test_all_catalog_items_are_named_and_arena_scoped(self):
        items = load("items-arena.json")["records"]

        self.assertTrue(items)
        self.assertTrue(all(item["name"] and item["arenaMap"] for item in items))


if __name__ == "__main__":
    unittest.main()
