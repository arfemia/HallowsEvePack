"""Checks for tools/check_refs.py, on throwaway packs built in a temp folder.

Run from the pack root:

    python -m unittest tools/test_check_refs.py -v
"""
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

TOOLS = Path(__file__).resolve().parent


def load_check_refs():
    spec = importlib.util.spec_from_file_location("check_refs", TOOLS / "check_refs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path.write_bytes(data)


def game_zip(root, names):
    path = root / "Assets.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, b"x")
    return path


class CheckRefsTest(unittest.TestCase):

    def setUp(self):
        self.check_refs = load_check_refs()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pack = self.root / "pack"
        write(self.pack, "Common/Items/Hallows_Eve/Thing/Thing.blockymodel", b"{}")
        write(self.pack, "Common/Icons/ItemsGenerated/Hallows_Eve_Thing.png", b"png")
        write(self.pack, "Common/Icons/ItemsGenerated/Hallows_Eve_Unused.png", b"png")
        write(self.pack, "Server/Item/Items/Hallows_Eve/Hallows_Eve_Thing.json", {
            "Icon": "Icons/ItemsGenerated/Hallows_Eve_Thing.png",
            "Model": "Items/Hallows_Eve/Thing/Thing.blockymodel",
            "Texture": "Items/Weapons/Wand/Wood_Texture.png",
            "BlockType": {"CustomModelTexture": [{"Texture": "Items/Hallows_Eve/Thing/Missing.png", "Weight": 1}]},
            "Tags": {"Type": ["Weapon"]},
        })
        self.assets = game_zip(self.root, ["Common/Items/Weapons/Wand/Wood_Texture.png"])

    def tearDown(self):
        self.temp.cleanup()

    def test_every_art_path_in_any_json_value_is_collected(self):
        refs = self.check_refs.references(self.pack)
        self.assertEqual({
            "Icons/ItemsGenerated/Hallows_Eve_Thing.png",
            "Items/Hallows_Eve/Thing/Thing.blockymodel",
            "Items/Weapons/Wand/Wood_Texture.png",
            "Items/Hallows_Eve/Thing/Missing.png",
        }, set(refs))

    def test_a_path_in_neither_the_pack_nor_the_game_is_missing(self):
        missing, unchecked, _ = self.check_refs.check(self.pack, self.assets)
        self.assertEqual(["Items/Hallows_Eve/Thing/Missing.png"], list(missing))
        self.assertEqual(["Server/Item/Items/Hallows_Eve/Hallows_Eve_Thing.json"],
                         missing["Items/Hallows_Eve/Thing/Missing.png"])
        self.assertEqual({}, unchecked)

    def test_paths_match_without_regard_to_case(self):
        write(self.pack, "Server/Item/Items/Hallows_Eve/Upper.json", {"Icon": "icons/itemsgenerated/HALLOWS_EVE_THING.PNG"})
        missing, _, _ = self.check_refs.check(self.pack, self.assets)
        self.assertNotIn("icons/itemsgenerated/HALLOWS_EVE_THING.PNG", missing)

    def test_without_a_game_zip_vanilla_paths_are_unchecked_not_missing(self):
        missing, unchecked, _ = self.check_refs.check(self.pack, self.root / "absent.zip")
        self.assertIn("Items/Weapons/Wand/Wood_Texture.png", unchecked)
        self.assertNotIn("Items/Weapons/Wand/Wood_Texture.png", missing)

    def test_art_no_json_names_is_an_orphan(self):
        _, _, orphans = self.check_refs.check(self.pack, self.assets)
        self.assertEqual(["Icons/ItemsGenerated/Hallows_Eve_Unused.png"], orphans)

    def test_the_command_fails_only_on_a_missing_path(self):
        self.assertEqual(1, self.check_refs.main(["--pack", str(self.pack), "--assets", str(self.assets)]))
        (self.pack / "Server/Item/Items/Hallows_Eve/Hallows_Eve_Thing.json").write_text(
            json.dumps({"Icon": "Icons/ItemsGenerated/Hallows_Eve_Thing.png"}), encoding="utf-8")
        self.assertEqual(0, self.check_refs.main(["--pack", str(self.pack), "--assets", str(self.assets), "--orphans"]))


if __name__ == "__main__":
    unittest.main()
