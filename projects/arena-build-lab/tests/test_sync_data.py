import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_data.py"
SPEC = importlib.util.spec_from_file_location("sync_data", MODULE_PATH)
sync_data = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(sync_data)


class MarkupToTextTest(unittest.TestCase):
    def test_converts_game_markup_to_readable_text(self):
        value = "<mainText><stats>50 攻击力<br>20% 急速</stats><br><br>持续作战</mainText>"

        self.assertEqual(sync_data.markup_to_text(value), "50 攻击力\n20% 急速\n持续作战")

    def test_decodes_html_entities(self):
        self.assertEqual(sync_data.markup_to_text("攻击力 &amp; 生命值"), "攻击力 & 生命值")

    def test_maps_data_dragon_patch_to_community_dragon_patch(self):
        self.assertEqual(sync_data.community_dragon_patch("16.16.1"), "16.16")


class NormalizationTest(unittest.TestCase):
    def test_filters_items_by_arena_map(self):
        payload = {
            "data": {
                "1": {"name": "峡谷装备", "maps": {"30": False}},
                "226660": {"name": "", "maps": {"30": True}},
                "2": {
                    "name": "斗魂装备",
                    "maps": {"30": True},
                    "description": "<mainText>说明</mainText>",
                    "gold": {"total": 1000},
                    "tags": ["Damage"],
                    "stats": {"FlatPhysicalDamageMod": 10},
                    "from": ["3"],
                    "into": ["4"],
                    "image": {"full": "2.png"},
                },
            }
        }

        records = sync_data.normalize_items(payload)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], 2)
        self.assertEqual(records[0]["description"], "说明")
        self.assertTrue(records[0]["arenaMap"])
        self.assertFalse(records[0]["purchasable"])

    def test_normalizes_augment_identity_and_text(self):
        payload = {
            "augments": [
                {
                    "id": 93,
                    "apiName": "WarmupRoutine",
                    "name": "热身动作",
                    "rarity": 0,
                    "desc": "造成<attention>更多伤害</attention>",
                    "tooltip": "最多@MaxStacks@层",
                    "iconSmall": "small.png",
                    "iconLarge": "large.png",
                    "dataValues": {"MaxStacks": [20]},
                    "calculations": {},
                }
            ]
        }

        records = sync_data.normalize_augments(payload)

        self.assertEqual(records[0]["description"], "造成更多伤害")
        self.assertEqual(records[0]["dataValues"]["MaxStacks"], [20])


if __name__ == "__main__":
    unittest.main()
