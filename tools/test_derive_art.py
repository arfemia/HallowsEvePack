"""Checks for the derived Hallow's Eve art, read from disk.

Run from the pack root:

    python -m unittest tools/test_derive_art.py -v

The checks are written independently of derive_art.py: the bounds maths re-implements
shared-source/release's BlockyModelBoundsParser (accumulateNodeBounds), and the face-rect
maths re-implements the Hytale team's Blockbench plugin (hytale_plugin.js, the
textureLayout -> UV parse), where a mirrored axis runs from `offset` back towards zero and
angle 90/180/270 swap or flip the rect. Two checks read outside the pack and skip when the
source is absent: the vanilla rigs in the workspace's shared source, and the installed game's
Assets.zip (HYTALE_ASSETS_ZIP, else the install the MMO's gradle.properties names, mmo-skills
found through the workspace's family.properties).
"""
import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.dont_write_bytecode = True

TOOLS = Path(__file__).resolve().parent
PACK = TOOLS.parent
COMMON = PACK / "Common"
VENDORED = TOOLS / "seed" / "vanilla"


def read_properties(path):
    """{key: value} from a .properties file's `key=value` lines, `#` comments skipped."""
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def mmo_skills(start):
    """The MMO repo: <root>/<repo.mmo-skills>, where root is the nearest folder above `start` holding
    family.properties (the workspace, or a tree under worktrees/); None outside a workspace."""
    root = next((p for p in start.parents if (p / "family.properties").is_file()), None)
    if root is None:
        return None
    rel = read_properties(root / "family.properties").get("repo.mmo-skills")
    return root / rel if rel else None


def shared_source(start):
    """The shared source: the first folder above `start` holding reference/shared-source/release (a tree
    holds none, so the walk passes its root up to main's), else the first holding shared-source/release
    (the layout before the un-nest), else the first marker, relative to the working folder."""
    markers = (Path("reference", "shared-source", "release"), Path("shared-source", "release"))
    return next((p / m for m in markers for p in start.parents if (p / m).is_dir()), markers[0])


MMO = mmo_skills(PACK)
SHARED_SOURCE = shared_source(PACK)
VANILLA = SHARED_SOURCE / "HytaleAssets" / "Common"

HE = "Items/Hallows_Eve"
TIERS = ("Common", "Uncommon", "Rare", "Epic")
BOMB_TEXTURES = [f"{HE}/Lantern_Bomb/Lantern_Bomb_{t}_Texture.png" for t in TIERS]
BOMB_MODELS = (f"{HE}/Lantern_Bomb/Lantern_Bomb.blockymodel", f"{HE}/Lantern_Bomb/Lantern_Bomb_Center.blockymodel")
HELM_MODEL = f"{HE}/Jack_Helm/Jack_Helm.blockymodel"
SHIELD_MODEL = f"{HE}/Jack_Shield/Jack_Shield.blockymodel"
PROP_MODEL = f"{HE}/Jack_Lantern/Jack_Lantern.blockymodel"
PUMPKIN_MODEL = f"{HE}/Hallowed_Pumpkin/Hallowed_Pumpkin.blockymodel"
GEODE_MODEL = f"{HE}/Cursed_Geode/Cursed_Geode.blockymodel"
BENCH_MODEL = "Blocks/Hallows_Eve/Carving_Bench/Carving_Bench.blockymodel"
SOUL_MODEL = "NPC/Hallows_Eve/Lost_Soul/Lost_Soul.blockymodel"
WRAITH_MODEL = "NPC/Hallows_Eve/Geode_Wraith/Geode_Wraith.blockymodel"
WAND_RIG = "Items/Weapons/Wand/Wood.blockymodel"
ESSENCE_RIG = "Resources/Ingredients/Essence.blockymodel"
GHOUL_RIG = "NPC/Undead/Ghoul/Models/Model.blockymodel"

# Every model we ship, with the textures worn on it (Common/-relative).
MODEL_TEXTURES = {
    BOMB_MODELS[0]: BOMB_TEXTURES,
    BOMB_MODELS[1]: BOMB_TEXTURES,
    HELM_MODEL: [f"{HE}/Jack_Helm/Jack_Helm_Texture.png", f"{HE}/Jack_Helm/Burning_Jack_Helm_Texture.png"],
    SHIELD_MODEL: [f"{HE}/Jack_Shield/Jack_Shield_Texture.png", f"{HE}/Jack_Shield/Flaming_Jack_Shield_Texture.png"],
    PROP_MODEL: [f"{HE}/Jack_Lantern/Jack_Lantern_Texture.png", f"{HE}/Jack_Lantern/Hollow_Lantern_Texture.png",
                 f"{HE}/Jack_Lantern/Ecto_Lantern_Texture.png"],
    PUMPKIN_MODEL: [f"{HE}/Hallowed_Pumpkin/Hallowed_Pumpkin_Texture.png"],
    GEODE_MODEL: [f"{HE}/Cursed_Geode/Cursed_Geode_Texture.png"],
    BENCH_MODEL: ["Blocks/Hallows_Eve/Carving_Bench/Carving_Bench_Texture.png"],
    SOUL_MODEL: ["NPC/Hallows_Eve/Lost_Soul/Lost_Soul_Texture.png"],
    WRAITH_MODEL: ["NPC/Hallows_Eve/Geode_Wraith/Geode_Wraith_Texture.png"],
}
# Vanilla rigs an item wears one of our textures on (read from the vendored copies).
RIG_TEXTURES = {
    WAND_RIG: (f"{HE}/Costume_Wand/Costume_Wand_Texture.png", "Items/Weapons/Wand/Wood_Texture.png"),
    ESSENCE_RIG: (f"{HE}/Ectoplasm/Ectoplasm_Texture.png",
                  "Resources/Ingredients/Essence_Textures/Life_Essence_Texture.png"),
    GHOUL_RIG: ("NPC/Hallows_Eve/Hollow_Ghoul/Hollow_Ghoul_Texture.png", "NPC/Undead/Ghoul/Models/Texture.png"),
}
GLOW_MODELS = (*BOMB_MODELS, HELM_MODEL, SHIELD_MODEL, PROP_MODEL, GEODE_MODEL, BENCH_MODEL)
VANILLA_FILES = (
    "Blocks/Benches/Workbench.blockymodel", "Blocks/Benches/Workbench_Texture.png",
    WAND_RIG, "Items/Weapons/Wand/Wood_Texture.png",
    "NPC/Elemental/Spirit_Ember/Models/Model.blockymodel", "NPC/Elemental/Spirit_Ember/Models/Texture.png",
    "NPC/Undead/Wraith/Models/Model.blockymodel", "NPC/Undead/Wraith/Models/Texture.png",
    ESSENCE_RIG, "Resources/Ingredients/Essence_Textures/Life_Essence_Texture.png",
    GHOUL_RIG, "NPC/Undead/Ghoul/Models/Texture.png",
)

ICON_IDS = [f"Hallows_Eve_Lantern_Bomb_{t}" for t in TIERS] + [
    "Hallows_Eve_Jack_Helm",
    "Hallows_Eve_Burning_Jack_Helm",
    "Hallows_Eve_Jack_Shield",
    "Hallows_Eve_Flaming_Jack_Shield",
    "Hallows_Eve_Jack_Lantern",
    "Hallows_Eve_Hollow_Lantern",
    "Hallows_Eve_Ecto_Lantern",
    "Hallows_Eve_Hallowed_Pumpkin",
    "Hallows_Eve_Cursed_Geode",
    "Hallows_Eve_Costume_Wand",
    "Hallows_Eve_Ectoplasm",
    "Hallows_Eve_Carving_Bench",
]
MODEL_ICON_IDS = ["Hallows_Eve_Lost_Soul", "Hallows_Eve_Geode_Wraith", "Hallows_Eve_Hollow_Ghoul"]
HORNS = {"R-Horn", "R-Horn2", "R-Horn3", "R-Horn-End", "R-Horn-End2",
         "L-Horn", "L-Horn2", "L-Horn3", "L-Horn-End", "L-Horn-End2"}


def expected_paths():
    """Every output, as a pack-relative POSIX path."""
    paths = {f"Common/{m}" for m in MODEL_TEXTURES}
    paths |= {f"Common/{t}" for ts in MODEL_TEXTURES.values() for t in ts}
    paths |= {f"Common/{ours}" for ours, _ in RIG_TEXTURES.values()}
    paths |= {f"Common/Icons/ItemsGenerated/{i}.png" for i in ICON_IDS}
    paths |= {f"Common/Icons/ModelsGenerated/{i}.png" for i in MODEL_ICON_IDS}
    return sorted(paths)


def load_model(rel):
    return json.loads((COMMON / rel).read_text(encoding="utf-8"))


def load_vendored(rel):
    return json.loads((VENDORED / "Common" / rel).read_text(encoding="utf-8"))


def walk(nodes, parent=None):
    """Yields (node, parent) for every node, depth first."""
    for node in nodes:
        yield node, parent
        yield from walk(node.get("children", []), node)


def find(model, name):
    hits = [n for n, _ in walk(model["nodes"]) if n.get("name") == name]
    return hits[0] if hits else None


def without(model, drop):
    """The model's nodes with every subtree whose root `drop(name)` accepts removed, ids
    stripped and every shape shown: what is left of a derived model once its additions go."""
    nodes = copy.deepcopy(model["nodes"])

    def prune(node):
        node.pop("id", None)
        (node.get("shape") or {}).pop("visible", None)
        kept = [c for c in node.get("children", []) if not drop(c["name"])]
        for child in kept:
            prune(child)
        if kept:
            node["children"] = kept
        else:
            node.pop("children", None)
        return node

    return [prune(n) for n in nodes if not drop(n["name"])]


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


def accumulate(node, parent_pos, parent_ori, acc, start=None):
    """Grows acc by the node's subtree; with `start`, only subtrees whose root name it accepts."""
    shape = node.get("shape")
    if shape is not None and shape.get("visible", True) is False:
        return
    pos = vec3(node.get("position"), (0, 0, 0))
    ori = quat(node.get("orientation"))
    off = vec3(shape.get("offset"), (0, 0, 0)) if shape else (0, 0, 0)
    local = tuple(a + b for a, b in zip(q_rot(ori, off), pos))
    world_pos = tuple(a + b for a, b in zip(q_rot(parent_ori, local), parent_pos))
    world_ori = q_mul(parent_ori, ori)
    counting = start is None or start(node["name"])
    if counting and shape and shape.get("type") in ("box", "quad"):
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
        accumulate(child, world_pos, world_ori, acc, None if counting else start)


def bounds(nodes, start=None):
    """[minX, minY, minZ, maxX, maxY, maxZ] in model pixels (before the 1/32 block scale)."""
    acc = [float("inf")] * 3 + [float("-inf")] * 3
    for node in nodes:
        accumulate(node, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), acc, start)
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


def assert_rects_inside(test, label, model, width, height):
    for node, _ in walk(model["nodes"]):
        shape = node.get("shape") or {}
        if shape.get("type") not in ("box", "quad"):
            continue
        layout = shape.get("textureLayout") or {}
        test.assertTrue(layout, f"{label} {node['name']} has no textureLayout")
        for face, entry in layout.items():
            with test.subTest(model=label, node=node["name"], face=face):
                x0, y0, x1, y1 = face_rect(entry, *face_dims(shape, face))
                test.assertGreaterEqual(x0, 0)
                test.assertGreaterEqual(y0, 0)
                test.assertLessEqual(x1, width)
                test.assertLessEqual(y1, height)


def load_derive_art():
    spec = importlib.util.spec_from_file_location("derive_art", TOOLS / "derive_art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hash_tree(root, rels):
    return {rel: hashlib.sha256((Path(root) / rel).read_bytes()).hexdigest() for rel in rels}


def installed_assets_zip():
    """The game Assets.zip the MMO builds against: HYTALE_ASSETS_ZIP, else the MMO's gradle.properties'
    hytaleHome/patchline/game_build (as its tools/dev-env.ps1 resolves it)."""
    override = os.environ.get("HYTALE_ASSETS_ZIP")
    if override:
        return Path(override)
    if MMO is None or not (MMO / "gradle.properties").is_file():
        return None
    values = read_properties(MMO / "gradle.properties")
    if "hytaleHome" not in values:
        return None
    return (Path(values["hytaleHome"]) / values.get("patchline", "release") / "package" / "game"
            / values.get("game_build", "latest") / "Assets.zip")


def mean_difference(a, b):
    """Mean absolute difference per RGBA channel, 0..255: identical images score 0."""
    with Image.open(a) as x, Image.open(b) as y:
        diff = ImageChops.difference(x.convert("RGBA"), y.convert("RGBA"))
        return sum(ImageStat.Stat(diff).mean) / 4


@unittest.skipUnless(VENDORED.is_dir(), "run python tools/derive_art.py --vendor <Assets.zip> first")
class DerivedArtTest(unittest.TestCase):

    def test_every_listed_file_exists(self):
        missing = [rel for rel in expected_paths() if not (PACK / rel).is_file()]
        self.assertEqual([], missing, "derived art missing; run python tools/derive_art.py")

    def test_the_vendored_vanilla_inputs_are_all_there(self):
        missing = [rel for rel in VANILLA_FILES if not (VENDORED / "Common" / rel).is_file()]
        self.assertEqual([], missing, "rerun python tools/derive_art.py --vendor <Assets.zip>")

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
                with Image.open(COMMON / tex) as image:
                    assert_rects_inside(self, f"{rel} on {tex}", model, *image.size)
        for rig, (ours, _) in RIG_TEXTURES.items():
            with Image.open(COMMON / ours) as image:
                assert_rects_inside(self, f"{rig} on {ours}", load_vendored(rig), *image.size)

    def test_a_recoloured_vanilla_texture_keeps_its_size_and_cut_out(self):
        # The vanilla model's UVs must land on the same texels, so only colour may change.
        pairs = [(ours, theirs) for ours, theirs in RIG_TEXTURES.values()]
        pairs.append(("NPC/Hallows_Eve/Lost_Soul/Lost_Soul_Texture.png", "NPC/Elemental/Spirit_Ember/Models/Texture.png"))
        for ours, theirs in pairs:
            with self.subTest(texture=ours):
                with Image.open(COMMON / ours) as a, Image.open(VENDORED / "Common" / theirs) as b:
                    self.assertEqual(b.size, a.size)
                    self.assertEqual(b.convert("RGBA").getchannel("A").tobytes(),
                                     a.convert("RGBA").getchannel("A").tobytes())

    def test_the_geode_wraith_texture_only_grows_below_the_wraiths(self):
        with Image.open(COMMON / MODEL_TEXTURES[WRAITH_MODEL][0]) as ours, \
                Image.open(VENDORED / "Common" / "NPC/Undead/Wraith/Models/Texture.png") as theirs:
            w, h = theirs.size
            self.assertEqual(w, ours.size[0])
            self.assertGreater(ours.size[1], h)
            self.assertEqual(theirs.convert("RGBA").getchannel("A").tobytes(),
                             ours.convert("RGBA").crop((0, 0, w, h)).getchannel("A").tobytes())

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
        for rel in (PUMPKIN_MODEL, GEODE_MODEL, BENCH_MODEL):
            with self.subTest(model=rel):
                roots = load_model(rel)["nodes"]
                self.assertEqual(["R-Attachment"], [n["name"] for n in roots])
                self.assertEqual("none", roots[0]["shape"]["type"])

    def assert_chain(self, model, names):
        self.assertEqual([names[0]], [n["name"] for n in model["nodes"]])
        node = model["nodes"][0]
        for name in names[1:]:
            self.assertEqual("none", node["shape"]["type"], node["name"])
            children = [c for c in node.get("children", []) if c["name"] == name]
            self.assertEqual(1, len(children), f"{name} under {node['name']}")
            node = children[0]

    def test_every_lit_model_keeps_a_fullbright_glow_quad(self):
        for rel in GLOW_MODELS:
            with self.subTest(model=rel):
                glow = [n for n, _ in walk(load_model(rel)["nodes"])
                        if (n.get("shape") or {}).get("type") == "quad"
                        and n["shape"].get("shadingMode") == "fullbright"]
                self.assertTrue(glow, "no fullbright quad")

    def test_the_hallowed_pumpkin_is_uncarved(self):
        model = load_model(PUMPKIN_MODEL)
        names = [n["name"] for n, _ in walk(model["nodes"])]
        self.assertNotIn("Glow", names)
        self.assertIn("Stem", names)
        base = find(model, "Base")
        self.assertEqual(base["shape"]["textureLayout"]["back"]["offset"],
                         base["shape"]["textureLayout"]["front"]["offset"],
                         "the front shows plain rind, like the back")

    def test_chains_match_their_vanilla_sources(self):
        if not VANILLA.is_dir():
            self.skipTest(f"shared-source/release not found at {VANILLA}")
        pairs = [
            (BOMB_MODELS[0], "NPC/Intelligent/Goblin/Models/Weapons/Bomb/Fire.blockymodel",
             ["R-Attachment", "Origin_Projectile", "Origin_Item"]),
            (BOMB_MODELS[1], "NPC/Intelligent/Goblin/Models/Weapons/Bomb/Fire_Center.blockymodel",
             ["R-Attachment", "Origin_Projectile", "Origin_Item"]),
            (SHIELD_MODEL, "Items/Weapons/Shield/Iron.blockymodel",
             ["L-Attachment", "Origin_Projectile", "Origin_Item"]),
            (HELM_MODEL, "Items/Armors/Iron/Head.blockymodel", ["Head"]),
            (PROP_MODEL, "Items/Halloween_Props/Pumpkin_Carve_01.blockymodel", ["R-Attachment"]),
            (PUMPKIN_MODEL, "Resources/Ingredients/Pumpkin.blockymodel", ["R-Attachment"]),
            (GEODE_MODEL, "Resources/Ingredients/Essence.blockymodel", ["R-Attachment"]),
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

    def test_derived_rigs_keep_every_vanilla_node(self):
        # G7: a vanilla animation drives nodes by name, so what is left of each derived model
        # once its additions go must be the vanilla model itself (shapes hidden or shown).
        cases = [
            (SOUL_MODEL, "NPC/Elemental/Spirit_Ember/Models/Model.blockymodel", lambda name: False),
            (WRAITH_MODEL, "NPC/Undead/Wraith/Models/Model.blockymodel", lambda name: name.startswith("Crystal_")),
            (BENCH_MODEL, "Blocks/Benches/Workbench.blockymodel",
             lambda name: name.startswith(("Carving_", "Shelf_Pumpkin"))),
        ]
        for ours, theirs, added in cases:
            with self.subTest(model=ours):
                self.assertEqual(without(load_vendored(theirs), lambda name: False),
                                 without(load_model(ours), added))

    def test_the_lost_soul_hides_only_its_horns(self):
        hidden = {n["name"] for n, _ in walk(load_model(SOUL_MODEL)["nodes"])
                  if (n.get("shape") or {}).get("visible", True) is False}
        self.assertEqual(HORNS, hidden)

    def test_the_geode_wraith_wears_lit_crystals(self):
        crystals = [n for n, _ in walk(load_model(WRAITH_MODEL)["nodes"]) if n["name"].startswith("Crystal_")]
        self.assertTrue(crystals)
        for node in crystals:
            with self.subTest(node=node["name"]):
                self.assertEqual("box", node["shape"]["type"])
                self.assertEqual("fullbright", node["shape"]["shadingMode"])

    def test_the_carving_props_stay_on_the_bench(self):
        model = load_model(BENCH_MODEL)
        props = bounds(model["nodes"], lambda name: name.startswith(("Carving_", "Shelf_Pumpkin")))
        # The Bench_Workbench hitbox: two blocks wide (x -48..16), one deep (z -16..16).
        self.assertGreaterEqual(props[0], -48)
        self.assertLessEqual(props[3], 16)
        self.assertGreaterEqual(props[2], -16)
        self.assertLessEqual(props[5], 16)
        self.assertGreaterEqual(props[1], 0)
        self.assertLessEqual(props[4], 64)
        names = {n["name"] for n, _ in walk(model["nodes"])}
        for prop in ("Carving_Lantern", "Carving_Lantern_Glow", "Carving_Knife", "Carving_Knife_Blade",
                     "Shelf_Pumpkin1", "Shelf_Pumpkin2"):
            self.assertIn(prop, names)

    def test_the_geode_crack_is_cut_through_and_lit_from_behind(self):
        model = load_model(GEODE_MODEL)
        shell, glow = find(model, "Shell"), find(model, "Glow")
        front = shell["shape"]["textureLayout"]["front"]["offset"]
        w, h = shell["shape"]["settings"]["size"]["x"], shell["shape"]["settings"]["size"]["y"]
        with Image.open(COMMON / MODEL_TEXTURES[GEODE_MODEL][0]) as image:
            alpha = image.convert("RGBA").getchannel("A").crop((front["x"], front["y"], front["x"] + w, front["y"] + h))
            holes = [(x, y) for y in range(h) for x in range(w) if alpha.getpixel((x, y)) == 0]
        self.assertTrue(holes, "the front face has no crack")
        depth = shell["shape"]["settings"]["size"]["z"] / 2
        self.assertLess(glow["position"]["z"], depth, "the glow sits behind the front face")
        gw, gh = glow["shape"]["settings"]["size"]["x"], glow["shape"]["settings"]["size"]["y"]
        for x, y in holes:
            # face pixel (x, y) is at shell-local (x - w/2 + 0.5, h/2 - y - 0.5)
            self.assertLessEqual(abs(x - w / 2 + 0.5), gw / 2, f"crack pixel {(x, y)} unlit")
            self.assertLessEqual(abs(h / 2 - y - 0.5), gh / 2, f"crack pixel {(x, y)} unlit")

    def test_bounds_follow_the_bounds_parser(self):
        cases = [
            # (model, subtree root or None for the whole model, min width, max width)
            (BOMB_MODELS[0], "Base", 14, 18),
            (BOMB_MODELS[1], "Base", 14, 18),
            (HELM_MODEL, None, 32, 36),
            (PROP_MODEL, None, 28, 32),
            (PUMPKIN_MODEL, None, 28, 32),
            (GEODE_MODEL, "Shell", 14, 22),
            (BENCH_MODEL, None, 62, 66),
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
                with Image.open(COMMON / "Icons/ItemsGenerated" / f"{icon}.png") as image:
                    self.assertEqual("RGBA", image.mode)
                    self.assertEqual((64, 64), image.size)
                    self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_model_icons_are_128_rgba_with_content(self):
        for icon in MODEL_ICON_IDS:
            with self.subTest(icon=icon):
                with Image.open(COMMON / "Icons/ModelsGenerated" / f"{icon}.png") as image:
                    self.assertEqual("RGBA", image.mode)
                    self.assertEqual((128, 128), image.size)
                    self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_the_helm_has_no_stem_and_the_lantern_keeps_its_own(self):
        helm = [n["name"] for n, _ in walk(load_model(HELM_MODEL)["nodes"])]
        self.assertEqual([], [n for n in helm if n.startswith("Stem")], helm)
        lantern = [n["name"] for n, _ in walk(load_model(PROP_MODEL)["nodes"])]
        self.assertIn("Stem", lantern)
        self.assertIn("Stem2", lantern)

    def test_icons_that_share_a_model_read_apart(self):
        icons = COMMON / "Icons/ItemsGenerated"
        pairs = [
            ("Hallows_Eve_Jack_Helm", "Hallows_Eve_Jack_Lantern"),
            ("Hallows_Eve_Ecto_Lantern", "Hallows_Eve_Jack_Lantern"),
            ("Hallows_Eve_Ecto_Lantern", "Hallows_Eve_Hollow_Lantern"),
            ("Hallows_Eve_Hallowed_Pumpkin", "Hallows_Eve_Jack_Lantern"),
        ]
        for a, b in pairs:
            with self.subTest(pair=(a, b)):
                pa, pb = icons / f"{a}.png", icons / f"{b}.png"
                self.assertNotEqual(hashlib.sha256(pa.read_bytes()).hexdigest(),
                                    hashlib.sha256(pb.read_bytes()).hexdigest(), "byte-identical icons")
                self.assertGreater(mean_difference(pa, pb), 8.0)

    def test_the_vendored_inputs_match_the_installed_game(self):
        archive = installed_assets_zip()
        if archive is None or not archive.is_file():
            self.skipTest(f"no installed Assets.zip (looked for {archive})")
        with zipfile.ZipFile(archive) as game:
            for rel in VANILLA_FILES:
                with self.subTest(file=rel):
                    theirs = game.read(f"Common/{rel}")
                    ours = (VENDORED / "Common" / rel).read_bytes()
                    if rel.endswith(".blockymodel"):
                        self.assertEqual(json.loads(theirs), json.loads(ours))
                    else:
                        self.assertEqual(theirs, ours)

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
