"""Checks for the seed-derived Hallow's Eve art, read from disk.

Run from the pack root:

    python -m unittest tools/test_derive_art.py -v

The checks are written independently of derive_art.py: the bounds maths re-implements
hytale-shared-source's BlockyModelBoundsParser (accumulateNodeBounds), and the face-rect
maths re-implements the Hytale team's Blockbench plugin (hytale_plugin.js, the
textureLayout -> UV parse), where a mirrored axis runs from `offset` back towards zero and
angle 90/180/270 swap or flip the rect.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.dont_write_bytecode = True

TOOLS = Path(__file__).resolve().parent
PACK = TOOLS.parent
ITEMS = PACK / "Common" / "Items" / "Hallows_Eve"
ICONS = PACK / "Common" / "Icons" / "ItemsGenerated"
VANILLA = PACK.parents[1] / "hytale-shared-source" / "HytaleAssets" / "Common"

TIERS = ("Common", "Uncommon", "Rare", "Epic")
BOMB_TEXTURES = [f"Lantern_Bomb/Lantern_Bomb_{t}_Texture.png" for t in TIERS]
MODEL_TEXTURES = {
    "Lantern_Bomb/Lantern_Bomb.blockymodel": BOMB_TEXTURES,
    "Lantern_Bomb/Lantern_Bomb_Center.blockymodel": BOMB_TEXTURES,
    "Jack_Helm/Jack_Helm.blockymodel": [
        "Jack_Helm/Jack_Helm_Texture.png",
        "Jack_Helm/Burning_Jack_Helm_Texture.png",
    ],
    "Jack_Shield/Jack_Shield.blockymodel": [
        "Jack_Shield/Jack_Shield_Texture.png",
        "Jack_Shield/Flaming_Jack_Shield_Texture.png",
    ],
    "Jack_Lantern/Jack_Lantern.blockymodel": [
        "Jack_Lantern/Jack_Lantern_Texture.png",
        "Jack_Lantern/Hollow_Lantern_Texture.png",
    ],
}
BOMB_MODELS = ("Lantern_Bomb/Lantern_Bomb.blockymodel", "Lantern_Bomb/Lantern_Bomb_Center.blockymodel")
HELM_MODEL = "Jack_Helm/Jack_Helm.blockymodel"
SHIELD_MODEL = "Jack_Shield/Jack_Shield.blockymodel"
PROP_MODEL = "Jack_Lantern/Jack_Lantern.blockymodel"

ICON_IDS = [f"Hallows_Eve_Lantern_Bomb_{t}" for t in TIERS] + [
    "Hallows_Eve_Jack_Helm",
    "Hallows_Eve_Burning_Jack_Helm",
    "Hallows_Eve_Jack_Shield",
    "Hallows_Eve_Flaming_Jack_Shield",
    "Hallows_Eve_Jack_Lantern",
    "Hallows_Eve_Hollow_Lantern",
]


def expected_paths():
    """Every output, as a pack-relative POSIX path."""
    paths = {f"Common/Items/Hallows_Eve/{m}" for m in MODEL_TEXTURES}
    paths |= {f"Common/Items/Hallows_Eve/{t}" for ts in MODEL_TEXTURES.values() for t in ts}
    paths |= {f"Common/Icons/ItemsGenerated/{i}.png" for i in ICON_IDS}
    return sorted(paths)


def load_model(rel):
    return json.loads((ITEMS / rel).read_text(encoding="utf-8"))


def walk(nodes, parent=None):
    """Yields (node, parent) for every node, depth first."""
    for node in nodes:
        yield node, parent
        yield from walk(node.get("children", []), node)


def find(model, name):
    hits = [n for n, _ in walk(model["nodes"]) if n.get("name") == name]
    return hits[0] if hits else None


# --- BlockyModelBoundsParser maths (quaternions as (x, y, z, w)) -----------------------

def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def q_rot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    # t = 2 * cross(q.xyz, v); v' = v + w * t + cross(q.xyz, t)
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def vec3(obj, default):
    if not isinstance(obj, dict):
        return default
    return tuple(float(obj.get(k, d)) for k, d in zip("xyz", default))


def quat(obj):
    """A node orientation, normalised as JOML's Quaternionf.transform does."""
    if not isinstance(obj, dict):
        return (0.0, 0.0, 0.0, 1.0)
    q = tuple(float(obj.get(k, d)) for k, d in zip("xyzw", (0, 0, 0, 1)))
    norm = sum(c * c for c in q) ** 0.5
    return tuple(c / norm for c in q)


BOX_CORNERS = [(-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5), (-.5, -.5, -.5),
               (.5, .5, .5), (-.5, .5, .5), (-.5, -.5, .5), (.5, -.5, .5)]


def quad_corners(shape):
    normal = (shape.get("settings") or {}).get("normal", "+Z")
    if normal in ("+X", "-X"):
        return [(0, -.5, -.5), (0, .5, -.5), (0, .5, .5), (0, -.5, .5)]
    if normal in ("+Y", "-Y"):
        return [(-.5, 0, -.5), (.5, 0, -.5), (.5, 0, .5), (-.5, 0, .5)]
    return [(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)]


def accumulate(node, parent_pos, parent_ori, acc):
    shape = node.get("shape")
    if shape is not None and shape.get("visible", True) is False:
        return
    pos = vec3(node.get("position"), (0, 0, 0))
    ori = quat(node.get("orientation"))
    off = vec3(shape.get("offset"), (0, 0, 0)) if shape else (0, 0, 0)
    local = tuple(a + b for a, b in zip(q_rot(ori, off), pos))
    world_pos = tuple(a + b for a, b in zip(q_rot(parent_ori, local), parent_pos))
    world_ori = q_mul(parent_ori, ori)
    if shape and shape.get("type") in ("box", "quad"):
        size = vec3((shape.get("settings") or {}).get("size"), (0, 0, 0))
        stretch = vec3(shape.get("stretch"), (1, 1, 1))
        s = tuple(a * b for a, b in zip(size, stretch))
        corners = BOX_CORNERS if shape["type"] == "box" else quad_corners(shape)
        for c in corners:
            p = q_rot(world_ori, tuple(a * b for a, b in zip(c, s)))
            p = tuple(a + b for a, b in zip(p, world_pos))
            for i in range(3):
                acc[i] = min(acc[i], p[i])
                acc[i + 3] = max(acc[i + 3], p[i])
    for child in node.get("children", []):
        accumulate(child, world_pos, world_ori, acc)


def bounds(nodes):
    """[minX, minY, minZ, maxX, maxY, maxZ] in model pixels (before the 1/32 block scale)."""
    acc = [float("inf")] * 3 + [float("-inf")] * 3
    for node in nodes:
        accumulate(node, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), acc)
    return acc


# --- textureLayout face rects (hytale_plugin.js parse) -----------------------------------

def face_dims(shape, face):
    size = shape["settings"]["size"]
    if shape["type"] == "quad":
        return size["x"], size["y"]
    if face in ("front", "back"):
        return size["x"], size["y"]
    if face in ("left", "right"):
        return size["z"], size["y"]
    return size["x"], size["z"]


def face_rect(layout, w, h):
    ox, oy = layout["offset"]["x"], layout["offset"]["y"]
    mirror = layout.get("mirror") or {}
    mx = -1 if mirror.get("x") else 1
    my = -1 if mirror.get("y") else 1
    angle = layout.get("angle", 0)
    if angle == 90:
        w, h, mx, my = h, w, -my, mx
        r = (ox, oy + h * my, ox + w * mx, oy)
    elif angle == 270:
        w, h, mx, my = h, w, my, -mx
        r = (ox + w * mx, oy, ox, oy + h * my)
    elif angle == 180:
        r = (ox - w * mx, oy - h * my, ox, oy)
    else:
        r = (ox, oy, ox + w * mx, oy + h * my)
    return min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3])


def load_derive_art():
    spec = importlib.util.spec_from_file_location("derive_art", TOOLS / "derive_art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hash_tree(root, rels):
    return {rel: hashlib.sha256((Path(root) / rel).read_bytes()).hexdigest() for rel in rels}


class DerivedArtTest(unittest.TestCase):

    def test_every_listed_file_exists(self):
        missing = [rel for rel in expected_paths() if not (PACK / rel).is_file()]
        self.assertEqual([], missing, "derived art missing; run python tools/derive_art.py")

    def test_models_parse_with_at_most_255_nodes(self):
        for rel in MODEL_TEXTURES:
            with self.subTest(model=rel):
                model = load_model(rel)
                count = sum(1 for _ in walk(model["nodes"]))
                self.assertGreater(count, 0)
                self.assertLessEqual(count, 255)

    def test_every_box_and_quad_size_is_an_integer(self):
        for rel in MODEL_TEXTURES:
            for node, _ in walk(load_model(rel)["nodes"]):
                shape = node.get("shape") or {}
                if shape.get("type") not in ("box", "quad"):
                    continue
                size = shape["settings"]["size"]
                axes = "xy" if shape["type"] == "quad" else "xyz"
                for axis in axes:
                    with self.subTest(model=rel, node=node["name"], axis=axis):
                        value = size[axis]
                        self.assertTrue(type(value) is int, f"size.{axis} = {value!r}")
                        self.assertGreater(value, 0)

    def test_every_face_rect_lies_inside_its_texture(self):
        for rel, textures in MODEL_TEXTURES.items():
            model = load_model(rel)
            for tex in textures:
                with Image.open(ITEMS / tex) as image:
                    width, height = image.size
                for node, _ in walk(model["nodes"]):
                    shape = node.get("shape") or {}
                    if shape.get("type") not in ("box", "quad"):
                        continue
                    layout = shape.get("textureLayout") or {}
                    self.assertTrue(layout, f"{rel} {node['name']} has no textureLayout")
                    for face, entry in layout.items():
                        with self.subTest(model=rel, texture=tex, node=node["name"], face=face):
                            x0, y0, x1, y1 = face_rect(entry, *face_dims(shape, face))
                            self.assertGreaterEqual(x0, 0)
                            self.assertGreaterEqual(y0, 0)
                            self.assertLessEqual(x1, width)
                            self.assertLessEqual(y1, height)

    def test_required_node_names_and_chains(self):
        for rel in BOMB_MODELS:
            with self.subTest(model=rel):
                model = load_model(rel)
                for name in ("R-Attachment", "Origin_Projectile", "Origin_Item", "Fuse", "Fuse2", "Fuse_Lit"):
                    self.assertIsNotNone(find(model, name), name)
                self.assert_chain(model, ["R-Attachment", "Origin_Projectile", "Origin_Item"])
                fuse = find(model, "Fuse")
                self.assertEqual(["Fuse2"], [c["name"] for c in fuse["children"]])
                self.assertEqual(["Fuse_Lit"], [c["name"] for c in fuse["children"][0]["children"]])
        helm = load_model(HELM_MODEL)
        self.assertEqual(["Head"], [n["name"] for n in helm["nodes"]])
        self.assertEqual("none", helm["nodes"][0]["shape"]["type"])
        shield = load_model(SHIELD_MODEL)
        self.assert_chain(shield, ["L-Attachment", "Origin_Projectile", "Origin_Item"])
        self.assertEqual(1, len(load_model(PROP_MODEL)["nodes"]))

    def assert_chain(self, model, names):
        self.assertEqual([names[0]], [n["name"] for n in model["nodes"]])
        node = model["nodes"][0]
        for name in names[1:]:
            self.assertEqual("none", node["shape"]["type"], node["name"])
            children = [c for c in node.get("children", []) if c["name"] == name]
            self.assertEqual(1, len(children), f"{name} under {node['name']}")
            node = children[0]

    def test_every_model_keeps_a_fullbright_glow_quad(self):
        for rel in MODEL_TEXTURES:
            with self.subTest(model=rel):
                glow = [n for n, _ in walk(load_model(rel)["nodes"])
                        if (n.get("shape") or {}).get("type") == "quad"
                        and n["shape"].get("shadingMode") == "fullbright"]
                self.assertTrue(glow, "no fullbright quad")

    def test_chains_match_their_vanilla_sources(self):
        if not VANILLA.is_dir():
            self.skipTest(f"hytale-shared-source not found at {VANILLA}")
        pairs = [
            (BOMB_MODELS[0], "NPC/Intelligent/Goblin/Models/Weapons/Bomb/Fire.blockymodel",
             ["R-Attachment", "Origin_Projectile", "Origin_Item"]),
            (BOMB_MODELS[1], "NPC/Intelligent/Goblin/Models/Weapons/Bomb/Fire_Center.blockymodel",
             ["R-Attachment", "Origin_Projectile", "Origin_Item"]),
            (SHIELD_MODEL, "Items/Weapons/Shield/Iron.blockymodel",
             ["L-Attachment", "Origin_Projectile", "Origin_Item"]),
            (HELM_MODEL, "Items/Armors/Iron/Head.blockymodel", ["Head"]),
            (PROP_MODEL, "Items/Halloween_Props/Pumpkin_Carve_01.blockymodel", ["R-Attachment"]),
        ]
        for rel, vanilla_rel, names in pairs:
            ours = load_model(rel)
            theirs = json.loads((VANILLA / vanilla_rel).read_text(encoding="utf-8"))
            for name in names:
                with self.subTest(model=rel, node=name):
                    a, b = find(ours, name), find(theirs, name)
                    self.assertIsNotNone(a)
                    self.assertEqual(vec3(b["position"], (0, 0, 0)), vec3(a["position"], (0, 0, 0)))
                    self.assertEqual(quat(b["orientation"]), quat(a["orientation"]))
                    self.assertEqual(vec3(b["shape"].get("offset"), (0, 0, 0)),
                                     vec3(a["shape"].get("offset"), (0, 0, 0)))
                    self.assertEqual(b["shape"]["type"], a["shape"]["type"])
                    self.assertEqual(b["shape"]["settings"].get("isPiece"),
                                     a["shape"]["settings"].get("isPiece"))
        fire = json.loads((VANILLA / pairs[0][1]).read_text(encoding="utf-8"))
        for rel in BOMB_MODELS:
            for name in ("Fuse", "Fuse2", "Fuse_Lit"):
                with self.subTest(model=rel, fuse=name):
                    a, b = find(load_model(rel), name)["shape"], find(fire, name)["shape"]
                    self.assertEqual(b["settings"]["size"], a["settings"]["size"])
                    self.assertEqual(b["shadingMode"], a["shadingMode"])

    def test_bounds_follow_the_bounds_parser(self):
        cases = [
            # (model, subtree root or None for the whole model, min width, max width)
            (BOMB_MODELS[0], "Base", 14, 18),
            (BOMB_MODELS[1], "Base", 14, 18),
            (HELM_MODEL, None, 32, 36),
            (PROP_MODEL, None, 28, 32),
        ]
        for rel, root, low, high in cases:
            with self.subTest(model=rel, root=root):
                model = load_model(rel)
                nodes = [find(model, root)] if root else model["nodes"]
                self.assertNotIn(None, nodes)
                acc = bounds(nodes)
                width = acc[3] - acc[0]
                self.assertGreaterEqual(width, low)
                self.assertLessEqual(width, high)

    def test_icons_are_64_rgba_with_content(self):
        for icon in ICON_IDS:
            with self.subTest(icon=icon):
                with Image.open(ICONS / f"{icon}.png") as image:
                    self.assertEqual("RGBA", image.mode)
                    self.assertEqual((64, 64), image.size)
                    self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_the_helm_has_no_stem_and_the_lantern_keeps_its_own(self):
        helm = [n["name"] for n, _ in walk(load_model(HELM_MODEL)["nodes"])]
        self.assertEqual([], [n for n in helm if n.startswith("Stem")], helm)
        lantern = [n["name"] for n, _ in walk(load_model(PROP_MODEL)["nodes"])]
        self.assertIn("Stem", lantern)
        self.assertIn("Stem2", lantern)

    def test_the_helm_icon_differs_visibly_from_the_lantern_icon(self):
        helm, lantern = ICONS / "Hallows_Eve_Jack_Helm.png", ICONS / "Hallows_Eve_Jack_Lantern.png"
        self.assertNotEqual(hashlib.sha256(helm.read_bytes()).hexdigest(),
                            hashlib.sha256(lantern.read_bytes()).hexdigest(), "byte-identical icons")
        with Image.open(helm) as a, Image.open(lantern) as b:
            diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
            mean = sum(ImageStat.Stat(diff).mean) / 4
        # Mean absolute difference per RGBA channel, 0..255: identical icons score 0.
        self.assertGreater(mean, 8.0)

    def test_a_second_run_writes_byte_identical_files(self):
        derive_art = load_derive_art()
        rels = expected_paths()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.assertEqual(0, derive_art.main(["--out", first]))
            self.assertEqual(0, derive_art.main(["--out", second]))
            written = sorted(p.relative_to(first).as_posix() for p in Path(first).rglob("*") if p.is_file())
            self.assertEqual(rels, written)
            run_one = hash_tree(first, rels)
            self.assertEqual(run_one, hash_tree(second, rels))
            self.assertEqual(run_one, hash_tree(PACK, rels), "the tree is stale; rerun derive_art.py")

    def test_check_mode_passes_without_writing(self):
        derive_art = load_derive_art()
        before = {rel: (PACK / rel).stat().st_mtime_ns for rel in expected_paths()}
        self.assertEqual(0, derive_art.main(["--check"]))
        after = {rel: (PACK / rel).stat().st_mtime_ns for rel in expected_paths()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
