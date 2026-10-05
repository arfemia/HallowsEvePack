#!/usr/bin/env python3
"""Derives the Hallow's Eve art from one seed model and a few vendored vanilla files.

    python tools/derive_art.py              # regenerate every output into the pack
    python tools/derive_art.py --check      # validate and compare with the tree; writes nothing
    python tools/derive_art.py --out DIR    # write the outputs under DIR instead of the pack
    python tools/derive_art.py --seed DIR   # read the seed (and DIR/vanilla) from DIR
    python tools/derive_art.py --vendor ZIP # refresh tools/seed/vanilla/ from a game Assets.zip

The seed is JackoLantern01.blockymodel and JackoLantern01_Texture.png, read from tools/seed/
(a byte copy, kept beside the tool so the pack rebuilds from its own repo) unless --seed
names another folder. The vanilla inputs are byte copies of twelve files from the installed
game's Assets.zip, kept under tools/seed/vanilla/ at their Assets.zip paths (VANILLA_FILES);
--vendor rewrites them from the Assets.zip it is given. A rerun writes byte-identical
files: nothing here is random, and PNGs carry no metadata.

What it writes (pack-relative):
  Common/Items/Hallows_Eve/<Model>/<Model>.blockymodel  seven item models, each a vanilla
      rig around seed or scripted geometry; scaling goes through `shape.stretch`, so every
      `settings.size` stays an integer and the UVs stay locked to it.
  Common/Items/Hallows_Eve/<Model>/*_Texture.png        Pillow/numpy textures: variants of
      the seed texture, recolours of the vanilla wand and essence textures, and the painted
      Cursed Geode.
  Common/Blocks/Hallows_Eve/Carving_Bench/              the Carving Bench: the vanilla
      Workbench rig with carving props on it, and its 128x128 atlas.
  Common/NPC/Hallows_Eve/<Mob>/                         the Lost Soul (on the Spirit_Ember
      rig) and the Geode Wraith (on the Wraith rig): every vanilla node kept, so the vanilla
      animations still drive them, plus a recoloured texture.
  Common/Icons/ItemsGenerated/Hallows_Eve_*.png         64x64 item icons from a small
      orthographic renderer at each family's vanilla IconProperties angle.
  Common/Icons/ModelsGenerated/Hallows_Eve_*.png        128x128 model icons for the two mobs.

Format facts this relies on (hytale-shared-source and the Hytale Blockbench plugin):
  - A node's shape is centred at position + orientation * offset, in its parent's frame,
    and its children hang from that same point (BlockyModelBoundsParser).
  - `stretch` scales the node's own size only, so a uniform scale of a subtree multiplies
    every stretch, offset and child position by k.
  - A textureLayout face covers `offset` plus the face's size; a mirrored axis runs from
    `offset` back towards zero (hytale_plugin.js, the textureLayout parse).
  - A vanilla animation drives nodes by name, so a derived model that keeps every vanilla
    node name (adding nodes, or hiding a shape with `visible: false`) animates as the vanilla
    model does.
"""
import argparse
import copy
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parent
PACK = TOOLS.parent
DEFAULT_SEED = TOOLS / "seed"
SEED_MODEL = "JackoLantern01.blockymodel"
SEED_TEXTURE = "JackoLantern01_Texture.png"

HE_ITEMS = "Items/Hallows_Eve"      # Common/-relative, the way an item or block JSON names a file
HE_BLOCKS = "Blocks/Hallows_Eve"
HE_NPCS = "NPC/Hallows_Eve"
ICONS = "Common/Icons/ItemsGenerated"
MODEL_ICONS = "Common/Icons/ModelsGenerated"

# --- scale -------------------------------------------------------------------------------

SEED_BODY = (30, 28, 30)        # the seed's Base box, in px
K_BOMB = 16 / 30                # the lantern shrinks to vanilla Weapon_Bomb's 16 px body
K_HELM = 1.15                   # 34.5 px: wide enough to swallow the player's 30 px head
K_PLATE = 1.4                   # the shield plate: a 42 x 39 px face, 5.6 px thick

# Lantern_Bomb_Center drops the body 10 px, as vanilla Fire_Center.blockymodel drops `Bomb`.
BOMB_CENTER_DROP = -10.0
# Jack_Helm centres the pumpkin 1 px above the head attachment's centre (vanilla
# Helmet_Base sits 2 px up; 1 px leaves a 1 px margin under the chin and 3 px over the crown).
HELM_CENTRE_Y = 1.0

# --- texture layout (64x64, x, y, w, h) -----------------------------------------------------

FRONT = (0, 0, 30, 28)          # the carved face; its transparent pixels are the cut-outs
SIDE = (0, 28, 30, 28)          # rind: back, right and (mirrored) left
TOP = (30, 0, 30, 30)           # rind: top and bottom (mirrored)
GLOW = (30, 30, 28, 20)         # the radial glow behind the cut-outs
STEM = (2, 56, 12, 8)
HANDLE = (14, 56, 24, 7)        # new: the shield grip, in pixels the seed leaves empty
FUSE_CORD = (40, 56, 3, 8)      # new: Fuse sides
FUSE_CORD_END = (43, 56, 3, 3)  # new: Fuse top and bottom
FUSE_BURN = (46, 56, 3, 5)      # new: Fuse2 sides
FUSE_BURN_END = (49, 56, 3, 3)  # new: Fuse2 top and bottom
FUSE_TIP = (52, 56, 3, 1)       # new: Fuse_Lit sides
FUSE_TIP_END = (52, 57, 3, 3)   # new: Fuse_Lit top

# Jack Helm's worn-gear mark, painted into the face and rind regions it already uses. Rows
# count down each 28-row face; the carved mouth ends on row 23, so the mark starts below it.
HELM_BAND_ROWS = (24, 25)       # a leather chin band right round the helm, under the mouth
HELM_RIM_ROWS = (26, 27)        # the hollowed neck rim on the bottom edge
HELM_STRAP = (12, 6, 6, 18)     # x, first row, width, rows: a cheek strap down the rind
HELM_BUCKLE = (11, 13, 8, 5)    # x, first row, width, rows: a brass buckle on that strap

# --- vanilla rigs (copied verbatim from hytale-shared-source/HytaleAssets/Common/) ----------

def none_node(name, position, orientation, is_piece, offset=(0, 0, 0), shading="flat"):
    return {
        "name": name,
        "position": vec(position),
        "orientation": quat(orientation),
        "shape": {
            "type": "none",
            "offset": vec(offset),
            "stretch": vec((1, 1, 1)),
            "settings": {"isPiece": is_piece},
            "textureLayout": {},
            "unwrapMode": "custom",
            "visible": True,
            "doubleSided": False,
            "shadingMode": shading,
        },
        "children": [],
    }


# NPC/Intelligent/Goblin/Models/Weapons/Bomb/Fire.blockymodel (and Fire_Center.blockymodel)
def bomb_chain():
    r = none_node("R-Attachment", (0, 0, 0), (-0.035349, 0.175192, 0.050483, 0.982604), True)
    p = none_node("Origin_Projectile", (0, 13, 0), (0, 0, 0, 1), True)
    i = none_node("Origin_Item", (0, -5, 0), (0, 0, 0, 1), False)
    r["children"].append(p)
    p["children"].append(i)
    return r, i


# Items/Weapons/Shield/Iron.blockymodel
def shield_chain():
    l_att = none_node("L-Attachment", (0, 34, 0), (0, 0, 0, 1), True)
    p = none_node("Origin_Projectile", (3, 26, 14), (0.258819, 0, 0, 0.965926), True)
    i = none_node("Origin_Item", (1, -29.51666, 0.875644), (-0.258819, 0, 0, 0.965926), False)
    l_att["children"].append(p)
    p["children"].append(i)
    return l_att, i


# Iron.blockymodel's Handle, and Shield1's place under it: Shield1 undoes the Handle's
# orientation, so the plate lines up with Origin_Item, its outer face on +X ("right":
# vanilla paints every shield emblem into the right faces and plain planks into the left).
SHIELD_HANDLE_POSITION = (-4, 0, 0)
SHIELD_HANDLE_ORIENTATION = (-0.430459, -0.560986, 0.430459, 0.560986)
SHIELD_HANDLE_SIZE = (24, 6, 7)
SHIELD_HANDLE_STRETCH = (1.2, 1, 1)
SHIELD_PLATE_POSITION = (0, 0, -6.6)
SHIELD_PLATE_ORIENTATION = (0.430459, 0.560986, -0.430459, 0.560986)
SHIELD_PLATE_SIZE = (4, 28, 30)     # thickness, then the seed face's 28 x 30 on y and z


# Items/Armors/Iron/Head.blockymodel
def helm_root():
    return none_node("Head", (0, 0, -2), (0, 0, 0, 1), True, offset=(0, 15, 3))


# Items/Halloween_Props/Pumpkin_Carve_01.blockymodel
def prop_root():
    return none_node("R-Attachment", (0, 0, 0), (0, 0, 0, 1), True, shading="fullbright")


# Fire.blockymodel's fuse, which hangs from `Bomb_Top` (9 px up, turned 180 degrees about Y).
# The lantern has no cap, so the fuse hangs from the body with that turn folded in:
# orientation = Bomb_Top * Fuse, position = Bomb_Top's turn applied to Fuse's position.
FUSE_ORIENTATION = (-0.014919, 0.917418, 0.203387, 0.341695)
FUSE_XZ = (0.332731, -0.378676)
# The fuse's pivot sits 1 px above the body's top face; its box starts 2 px below the pivot,
# so it roots 1 px into the body (vanilla's roots into the 4 px Bomb_Top cap instead).
FUSE_RISE = 1.0
FUSE_SPECS = [
    # name, position, orientation, offset, stretch, size, shading
    ("Fuse", None, FUSE_ORIENTATION, (0, 2, 0), (0.953088, 1, 0.987346), (3, 8, 3), "flat"),
    ("Fuse2", (0, 3.12711, 0.065393), (-0.376923, 0, 0, 0.926245), (0, 2, 0),
     (0.974462, 1, 1.00301), (3, 5, 3), "fullbright"),
    ("Fuse_Lit", (0, 2.721891, 0), (0, 0, 0, 1), (0, 0, 0), (0.866498, 1, 0.927509), (3, 1, 3),
     "fullbright"),
]
FUSE_FACES = {
    "Fuse": ({f: FUSE_CORD for f in ("front", "back", "right", "left")}
             | {f: FUSE_CORD_END for f in ("top", "bottom")}),
    "Fuse2": ({f: FUSE_BURN for f in ("front", "back", "right", "left")}
              | {f: FUSE_BURN_END for f in ("top", "bottom")}),
    "Fuse_Lit": {f: FUSE_TIP for f in ("front", "back", "right", "left")} | {"top": FUSE_TIP_END},
}

# --- icon angles: each family's vanilla IconProperties.Rotation (Server/Item/Items/) --------

ANGLE_BOMB = (4.685, 6.935, 315)        # Weapon/Bomb/Weapon_Bomb.json
ANGLE_SHIELD = (315, 270, 0)            # Weapon/Shield/Template_Weapon_Shield.json
# The helm takes the lower armor-head tilt (Armor/Mithril/Armor_Mithril_Head.json) rather than
# Armor_Iron_Head's (22.5, 45, 22.5), which is also the block angle: less crown and more side,
# so the strap and neck rim show and the helm never renders as the lantern's twin.
ANGLE_HELM = (15, 45, 15)
ANGLE_BLOCK = (22.5, 45, 22.5)          # Deco/Deco_Halloween_Pumpkin_Scary.json
ANGLE_WAND = (45, 90, 0)                # Weapon/Wand/Weapon_Wand_Wood.json
ANGLE_ESSENCE = (0, 0, 0)               # Ingredient/Ingredient_Life_Essence.json
ANGLE_CRYSTAL = (34.315, 29.815, 22.5)  # Ingredient/Crystal/Ingredient_Crystal_Purple.json

# --- quality colours: Server/Item/Qualities/<Quality>.json TextColor ------------------------

TIERS = {
    # quality: (TextColor, how far the rind moves toward it, brightness gain on that colour)
    "Common": ("#c9d2dd", 0.12, 1.15),
    "Uncommon": ("#3e9049", 0.72, 1.15),
    "Rare": ("#2770b7", 0.75, 1.15),
    "Epic": ("#8b339e", 0.82, 1.3),
}

# --- vanilla inputs: byte copies of the installed game's files, under tools/seed/vanilla/ ----
# Keys are Common/-relative, as a model or item JSON names them. Each one is identical in the
# live 0.6.8 Assets.zip and in Update 7's pre-release Assets.zip.

WORKBENCH = "Blocks/Benches/Workbench.blockymodel"
WORKBENCH_TEXTURE = "Blocks/Benches/Workbench_Texture.png"
WAND = "Items/Weapons/Wand/Wood.blockymodel"
WAND_TEXTURE = "Items/Weapons/Wand/Wood_Texture.png"
SPIRIT = "NPC/Elemental/Spirit_Ember/Models/Model.blockymodel"
SPIRIT_TEXTURE = "NPC/Elemental/Spirit_Ember/Models/Texture.png"
WRAITH = "NPC/Undead/Wraith/Models/Model.blockymodel"
WRAITH_TEXTURE = "NPC/Undead/Wraith/Models/Texture.png"
ESSENCE = "Resources/Ingredients/Essence.blockymodel"
ESSENCE_TEXTURE = "Resources/Ingredients/Essence_Textures/Life_Essence_Texture.png"
GHOUL = "NPC/Undead/Ghoul/Models/Model.blockymodel"
GHOUL_TEXTURE = "NPC/Undead/Ghoul/Models/Texture.png"
VANILLA_FILES = tuple(f"Common/{rel}" for rel in (
    WORKBENCH, WORKBENCH_TEXTURE, WAND, WAND_TEXTURE, SPIRIT, SPIRIT_TEXTURE,
    WRAITH, WRAITH_TEXTURE, ESSENCE, ESSENCE_TEXTURE, GHOUL, GHOUL_TEXTURE))

# --- the Cursed Geode: a scripted stone with a lit crack (64x64 texture, x, y, w, h) ---------

GEODE_SHELL = (14, 12, 14)      # the main stone, in px
GEODE_FRONT = (0, 0, 14, 12)    # stone with the crack cut through it (transparent pixels)
GEODE_SIDE = (14, 0, 14, 12)    # stone: back, right, left; the lumps take sub-rects of it
GEODE_TOP = (28, 0, 14, 14)     # stone: top and bottom
GEODE_GLOW = (42, 0, 12, 12)    # the cursed light behind the crack
GEODE_CRYSTAL_SIDE = (0, 16, 3, 7)
GEODE_CRYSTAL_TOP = (3, 16, 3, 3)
# The crack's column on each of the front face's 12 rows; rows 4-7 are two pixels wide.
GEODE_CRACK = (7, 7, 6, 6, 6, 7, 8, 8, 7, 6, 6, 7)
GEODE_WIDE_ROWS = (4, 5, 6, 7)
GEODE_LUMPS = [
    # name, centre (from the shell's centre), size, yaw in degrees: kept off the front face
    ("Shell2", (-3, 4, -2), (10, 8, 12), 20),
    ("Shell3", (3, -3, 0), (12, 6, 10), -15),
]
GEODE_CRYSTALS = [
    # name, root on the top face (from the shell's centre), size, (pitch, roll) in degrees
    ("Crystal", (0.5, 5, 1), (3, 7, 3), (8, -12)),
    ("Crystal2", (-2.5, 5, -1), (2, 5, 2), (0, 25)),
    ("Crystal3", (3, 5, -2), (3, 6, 3), (-10, -35)),
]

# --- the Carving Bench: the vanilla Workbench with carving props (128x128 atlas) -------------

BENCH_SIZE = (128, 128)         # the Workbench's 128x64 texture on top, the seed's 64x64 below
BENCH_SEED_AT = (0, 64)         # where the seed texture sits on the bench atlas
BLADE = (64, 64, 8, 8)          # the carving knife's steel, on the bench atlas
BENCH_BITS = (4, 96)            # 2x2 of rind on the atlas, for the carved-out pieces
K_BENCH_LANTERN = 0.6           # an 18 px jack-o'-lantern on the tabletop
K_BENCH_PUMPKIN = 0.3           # 9 px pumpkins stored on the lower shelf
TABLETOP_Y = 32                 # the Workbench's tabletop surface, in model px
SHELF_Y = 16.5                  # the Workbench's lower shelf (Base2) surface
# World positions (model px), placed clear of the Workbench's spool, papers, hammer, screws
# and vice, inside the Bench_Workbench hitbox (x -48..16, z -16..16).
BENCH_LANTERN_AT = (-36, -6)    # x, z on the tabletop, left end, carved face to the front (+Z)
BENCH_PUMPKINS_AT = ((-28, 0), (-14, 0))    # x, z on the shelf
BENCH_KNIFE_AT = (-4, 13)       # x, z of the handle: the knife lies along the front edge
BENCH_KNIFE_YAW = 100           # degrees about Y: the blade points to +X
BENCH_BITS_AT = ((-24, 11), (-21, 13))      # x, z: two carved-out pieces of rind

# --- the mobs (G7): vanilla rigs kept whole, with their own texture ---------------------------

# The Lost Soul is the Spirit_Ember rig without its horns: a pale soul with a mint glow.
LOST_SOUL_HIDDEN_PREFIXES = ("R-Horn", "L-Horn")
# The Geode Wraith is the Wraith rig with amethyst growing out of its back and shoulders.
WRAITH_TEXTURE_GROWTH = 32      # rows added under the Wraith's 352x192 texture for the crystals
WRAITH_CRYSTAL_SIDE = (0, 192, 6, 16)   # on the grown Geode Wraith texture
WRAITH_CRYSTAL_TOP = (6, 192, 6, 6)
WRAITH_CRYSTALS = [
    # name, parent node, root (from the parent's centre), size, (pitch, roll) in degrees
    ("Crystal_Back", "Chest", (-6, 6, -10.5), (6, 16, 6), (-40, 10)),
    ("Crystal_Back2", "Chest", (5, 9, -10.5), (5, 13, 5), (-55, -15)),
    ("Crystal_Back3", "Chest", (0, -3, -10.5), (4, 10, 4), (-70, 5)),
    ("Crystal_L_Shoulder", "L-Shoulder", (2, 4, 0), (4, 11, 4), (5, -30)),
    ("Crystal_R_Shoulder", "R-Shoulder", (-2, 4, 0), (4, 11, 4), (-5, 30)),
]
ANGLE_MODEL = (10, 25, 0)       # the mobs' model icons: nearly front-on, like vanilla's

# --- the Costume Wand: the vanilla wood wand's texture, recoloured by the nodes it skins -----

WAND_PARTS = [
    # node names, the colour they turn, strength, brightness gain on that colour
    (("Handle", "Handle2", "Stick"), "#3b2448", 0.85, 1.25),   # blackened wood, a violet cast
    (("Leave_Staff", "Leave_Staff2"), "#f28a1e", 0.9, 1.35),   # the leaves turn pumpkin orange
    (("Rope3", "Rope4"), "#8fd14a", 0.85, 1.2),                # a green cord
]


# =========================================================================================
# JSON helpers
# =========================================================================================

def num(value):
    """Six decimals like vanilla; integral values as ints, and never -0."""
    r = round(float(value), 6)
    if r == 0:
        return 0
    return int(r) if r.is_integer() else r


def vec(v):
    return {"x": num(v[0]), "y": num(v[1]), "z": num(v[2])}


def quat(q):
    return {"x": num(q[0]), "y": num(q[1]), "z": num(q[2]), "w": num(q[3])}


def layout(rect, mirror=(False, False)):
    return {"offset": {"x": rect[0], "y": rect[1]},
            "mirror": {"x": mirror[0], "y": mirror[1]}, "angle": 0}


def box_node(name, position, orientation, size, stretch, faces, shading="flat", offset=(0, 0, 0)):
    return {
        "name": name,
        "position": vec(position),
        "orientation": quat(orientation),
        "shape": {
            "type": "box",
            "offset": vec(offset),
            "stretch": vec(stretch),
            "settings": {"isPiece": False, "size": {"x": size[0], "y": size[1], "z": size[2]}},
            "textureLayout": {face: layout(rect) for face, rect in faces.items()},
            "unwrapMode": "custom",
            "visible": True,
            "doubleSided": False,
            "shadingMode": shading,
        },
        "children": [],
    }


def finish_model(root):
    """Numbers the nodes depth first and drops empty `children` lists from leaves."""
    counter = [0]

    def visit(node):
        counter[0] += 1
        node["id"] = str(counter[0])
        ordered = {"id": node["id"]}
        ordered.update({k: v for k, v in node.items() if k != "id"})
        node.clear()
        node.update(ordered)
        for child in node.get("children", []):
            visit(child)
        if not node.get("children"):
            node.pop("children", None)

    visit(root)
    return {"nodes": [root], "lod": "auto"}


# =========================================================================================
# The seed
# =========================================================================================

SEED_NAMES = {"cube--C1": "Glow", "cube--C2": "Stem", "cube--C3": "Stem2"}


def load_seed(seed_dir):
    model = json.loads((seed_dir / SEED_MODEL).read_text(encoding="utf-8"))
    base = next(n for n in walk(model["nodes"]) if n["name"] == "Base")
    base = copy.deepcopy(base)
    for node in walk([base]):
        node["name"] = SEED_NAMES.get(node["name"], node["name"])
        node.pop("id", None)
    with Image.open(seed_dir / SEED_TEXTURE) as image:
        texture = np.array(image.convert("RGBA"))
    return base, texture


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def scaled_body(seed_base, k, placement):
    """The seed's Base subtree, uniformly scaled by k about its own pivot.

    `stretch`, `offset` and every child `position` are multiplied by k; `settings.size`
    never changes. The returned body's centre sits at `placement` in its parent's frame.
    """
    body = copy.deepcopy(seed_base)

    def visit(node, is_root):
        shape = node["shape"]
        if not is_root:
            node["position"] = vec([node["position"][a] * k for a in "xyz"])
        node["orientation"] = quat([node["orientation"][a] for a in "xyzw"])
        shape["offset"] = vec([shape["offset"][a] * k for a in "xyz"])
        if shape["type"] in ("box", "quad"):
            shape["stretch"] = vec([shape["stretch"][a] * k for a in "xyz"])
        for child in node.get("children", []):
            visit(child, False)

    visit(body, True)
    centre = seed_base["shape"]["offset"]["y"] * k
    body["position"] = vec((placement[0], placement[1] - centre, placement[2]))
    return body


def fuse_chain(body_half_height):
    nodes = []
    for name, position, orientation, offset, stretch, size, shading in FUSE_SPECS:
        if position is None:
            position = (FUSE_XZ[0], body_half_height + FUSE_RISE, FUSE_XZ[1])
        nodes.append(box_node(name, position, orientation, size, stretch, FUSE_FACES[name],
                              shading=shading, offset=offset))
    nodes[0]["children"].append(nodes[1])
    nodes[1]["children"].append(nodes[2])
    return nodes[0]


# =========================================================================================
# Vanilla inputs and node frames
# =========================================================================================

def load_vanilla(seed_dir):
    """The vendored vanilla inputs: {Common/-relative path: model dict, or RGBA uint8 array}."""
    out = {}
    for rel in VANILLA_FILES:
        path = seed_dir / "vanilla" / rel
        key = rel[len("Common/"):]
        if key.endswith(".blockymodel"):
            out[key] = json.loads(path.read_text(encoding="utf-8"))
        else:
            with Image.open(path) as image:
                out[key] = np.array(image.convert("RGBA"))
    return out


def vendor(zip_path, seed_dir):
    """Copies VANILLA_FILES out of a game Assets.zip into seed_dir/vanilla, byte for byte."""
    with zipfile.ZipFile(zip_path) as archive:
        for rel in VANILLA_FILES:
            target = seed_dir / "vanilla" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(rel))
    return len(VANILLA_FILES)


def vanilla_root(model):
    """A copy of a vanilla model's single root node, ids dropped (finish_model renumbers)."""
    if len(model["nodes"]) != 1:
        raise ValueError(f"expected one root node, found {len(model['nodes'])}")
    root = copy.deepcopy(model["nodes"][0])
    for node in walk([root]):
        node.pop("id", None)
    return root


def find_node(root, name):
    return next(n for n in walk([root]) if n["name"] == name)


def q_mul(a, b):
    """Quaternion product a * b, each (x, y, z, w)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def q_rot(q, v):
    """Turns vector v by the unit quaternion q (x, y, z, w)."""
    x, y, z, w = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def q_axis(axis, degrees):
    """A unit quaternion (x, y, z, w) turning `degrees` about the 'x', 'y' or 'z' axis."""
    half = math.radians(degrees) / 2
    s, c = math.sin(half), math.cos(half)
    return {"x": (s, 0.0, 0.0, c), "y": (0.0, s, 0.0, c), "z": (0.0, 0.0, s, c)}[axis]


def node_frames(root):
    """{id(node): (centre, orientation)} in model px for every node under `root`.

    The centre is where a node's shape sits and where its children hang: position plus
    orientation * offset, in the parent's frame (BlockyModelBoundsParser)."""
    frames = {}

    def visit(node, parent_centre, parent_ori):
        ori = tuple(float(node["orientation"][a]) for a in "xyzw")
        norm = math.sqrt(sum(c * c for c in ori))
        ori = tuple(c / norm for c in ori)
        pos = tuple(float(node["position"][a]) for a in "xyz")
        off = tuple(float((node.get("shape") or {}).get("offset", {}).get(a, 0)) for a in "xyz")
        local = tuple(p + o for p, o in zip(pos, q_rot(ori, off)))
        centre = tuple(c + l for c, l in zip(parent_centre, q_rot(parent_ori, local)))
        world_ori = q_mul(parent_ori, ori)
        frames[id(node)] = (centre, world_ori)
        for child in node.get("children", []):
            visit(child, centre, world_ori)

    visit(root, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    return frames


def hang(child, parent, frames, world_centre):
    """Hangs `child` from `parent` so that the child's shape is centred at `world_centre`."""
    centre, ori = frames[id(parent)]
    inverse = (-ori[0], -ori[1], -ori[2], ori[3])
    local = q_rot(inverse, tuple(w - c for w, c in zip(world_centre, centre)))
    child_ori = tuple(child["orientation"][a] for a in "xyzw")
    off = tuple(child["shape"]["offset"][a] for a in "xyz")
    child["position"] = vec(tuple(l - o for l, o in zip(local, q_rot(child_ori, off))))
    parent.setdefault("children", []).append(child)


def rename_subtree(node, name):
    """Names a seed body `name` and each of its children `<name>_<child>` (Glow, Stem, Stem2)."""
    node["name"] = name
    for child in node.get("children", []):
        child["name"] = f"{name}_{child['name']}"


def shift_uv(node, dx, dy):
    """Moves every face of a subtree by (dx, dy) on its texture: the seed's place on an atlas."""
    for n in walk([node]):
        for entry in (n.get("shape") or {}).get("textureLayout", {}).values():
            entry["offset"] = {"x": entry["offset"]["x"] + dx, "y": entry["offset"]["y"] + dy}


def quad_node(name, position, orientation, size, rect, shading="fullbright"):
    """A two-sided quad facing +Z, its one face at `rect` (the seed's Glow shape)."""
    return {
        "name": name,
        "position": vec(position),
        "orientation": quat(orientation),
        "shape": {
            "type": "quad",
            "offset": vec((0, 0, 0)),
            "stretch": vec((1, 1, 1)),
            "settings": {"isPiece": False, "size": {"x": size[0], "y": size[1]}, "normal": "+Z"},
            "textureLayout": {"front": layout(rect)},
            "unwrapMode": "custom",
            "visible": True,
            "doubleSided": True,
            "shadingMode": shading,
        },
        "children": [],
    }


# =========================================================================================
# Models
# =========================================================================================

def bomb_model(seed_base, center):
    root, origin_item = bomb_chain()
    drop = BOMB_CENTER_DROP if center else 0.0
    body = scaled_body(seed_base, K_BOMB, (0, drop, 0))
    body["children"].append(fuse_chain(SEED_BODY[1] / 2 * K_BOMB))
    origin_item["children"].append(body)
    return finish_model(root)


def helm_model(seed_base):
    root = helm_root()
    body = scaled_body(seed_base, K_HELM, (0, HELM_CENTRE_Y, 0))
    # A worn helm has no stem: only the carved face's glow quad stays.
    body["children"] = [c for c in body["children"] if not c["name"].startswith("Stem")]
    root["children"].append(body)
    return finish_model(root)


def shield_model(seed_base):
    root, origin_item = shield_chain()
    handle = box_node("Handle", SHIELD_HANDLE_POSITION, SHIELD_HANDLE_ORIENTATION,
                      SHIELD_HANDLE_SIZE, SHIELD_HANDLE_STRETCH,
                      {f: HANDLE for f in ("front", "back", "left", "right", "top", "bottom")})
    k = K_PLATE
    thick, _, _ = SHIELD_PLATE_SIZE
    plate = box_node("Plate", SHIELD_PLATE_POSITION, SHIELD_PLATE_ORIENTATION, SHIELD_PLATE_SIZE,
                     (k, k, k), {
                         "right": FRONT[:2],             # outer: the carved face
                         "left": SIDE[:2],               # inner: plain rind
                         "front": SIDE[:2], "back": SIDE[:2],
                         "top": TOP[:2], "bottom": TOP[:2],
                     })
    # The seed's glow quad sits 0.2 px inside the carved face and 4 px below its centre;
    # turned to face +X it does the same behind the plate's outer face.
    seed_glow = next(n for n in walk([seed_base]) if n["name"] == "Glow")
    glow = copy.deepcopy(seed_glow)
    glow["position"] = vec(((thick / 2 - 0.2) * k, -4 * k, 0))
    glow["orientation"] = quat((0, 0, 0, 1))
    glow["shape"]["offset"] = vec((0, 0, 0))
    glow["shape"]["stretch"] = vec((k, k, k))
    glow["shape"]["settings"] = {"isPiece": False, "size": dict(seed_glow["shape"]["settings"]["size"]),
                                 "normal": "+X"}
    plate["children"].append(glow)
    handle["children"].append(plate)
    origin_item["children"].append(handle)
    return finish_model(root)


def lantern_model(seed_base):
    root = prop_root()
    root["children"].append(scaled_body(seed_base, 1.0, (0, SEED_BODY[1] / 2, 0)))
    return finish_model(root)


def uncarved_body(seed_base, k, placement):
    """The seed pumpkin uncarved: the carved front takes the plain rind, and the glow goes."""
    body = scaled_body(seed_base, k, placement)
    body["children"] = [c for c in body["children"] if c["name"] != "Glow"]
    body["shape"]["textureLayout"]["front"] = layout(SIDE)
    return body


def pumpkin_model(seed_base):
    """The Hallowed Pumpkin: the uncarved seed at full size on vanilla Pumpkin.blockymodel's
    root, standing on the ground (the item ships this model, since Update 7 redraws the
    vanilla pumpkin's UV layout)."""
    root = none_node("R-Attachment", (0, 0, 0), (0, 0, 0, 1), True)
    root["children"].append(uncarved_body(seed_base, 1.0, (0, SEED_BODY[1] / 2, 0)))
    return finish_model(root)


def crystal_faces(side, top):
    return {f: side for f in ("front", "back", "right", "left")} | {"top": top, "bottom": top}


def crystal_node(name, root_at, size, pitch_roll, side, top):
    """An amethyst shard, rooted at `root_at` and growing up its own Y, tilted by pitch
    (about X) then roll (about Z)."""
    pitch, roll = pitch_roll
    orientation = q_mul(q_axis("x", pitch), q_axis("z", roll))
    return box_node(name, root_at, orientation, size, (1, 1, 1), crystal_faces(side, top),
                    shading="fullbright", offset=(0, size[1] / 2, 0))


def geode_model():
    """The Cursed Geode: a stone with two lumps, a crack in its front face lit from inside by
    a glow quad 0.2 px behind it (the seed's carved-face trick), and amethyst on top."""
    root = none_node("R-Attachment", (0, 0, 0), (0, 0, 0, 1), True)
    w, h, d = GEODE_SHELL
    faces = {f: GEODE_SIDE for f in ("back", "right", "left")}
    faces |= {"front": GEODE_FRONT, "top": GEODE_TOP, "bottom": GEODE_TOP}
    shell = box_node("Shell", (0, 0, 0), (0, 0, 0, 1), GEODE_SHELL, (1, 1, 1), faces,
                     offset=(0, h / 2, 0))
    for name, centre, size, yaw in GEODE_LUMPS:
        lump = {f: GEODE_SIDE for f in ("front", "back", "right", "left")}
        lump |= {"top": GEODE_TOP, "bottom": GEODE_TOP}
        shell["children"].append(box_node(name, centre, q_axis("y", yaw), size, (1, 1, 1), lump))
    shell["children"].append(quad_node("Glow", (0, 0, d / 2 - 0.2), (0, 0, 0, 1),
                                       GEODE_GLOW[2:], GEODE_GLOW))
    for name, root_at, size, pitch_roll in GEODE_CRYSTALS:
        shell["children"].append(crystal_node(name, root_at, size, pitch_roll,
                                              GEODE_CRYSTAL_SIDE, GEODE_CRYSTAL_TOP))
    root["children"].append(shell)
    return finish_model(root)


def bench_model(workbench, seed_base):
    """The Carving Bench: the vanilla Workbench with every node kept, so its own crafting and
    placing animations still play on it, plus a lit jack-o'-lantern, a knife and two carved-out
    pieces on the tabletop and two pumpkins on the shelf. The props hang from the node they
    rest on, so they ride the tabletop's shake while it works."""
    root = vanilla_root(workbench)
    frames = node_frames(root)
    tabletop, shelf = find_node(root, "Tabletop"), find_node(root, "Base2")
    sx, sy = BENCH_SEED_AT
    lantern = scaled_body(seed_base, K_BENCH_LANTERN, (0, 0, 0))
    rename_subtree(lantern, "Carving_Lantern")
    shift_uv(lantern, sx, sy)
    x, z = BENCH_LANTERN_AT
    hang(lantern, tabletop, frames, (x, TABLETOP_Y + SEED_BODY[1] / 2 * K_BENCH_LANTERN, z))
    for i, (x, z) in enumerate(BENCH_PUMPKINS_AT, start=1):
        pumpkin = uncarved_body(seed_base, K_BENCH_PUMPKIN, (0, 0, 0))
        rename_subtree(pumpkin, f"Shelf_Pumpkin{i}")
        shift_uv(pumpkin, sx, sy)
        hang(pumpkin, shelf, frames, (x, SHELF_Y + SEED_BODY[1] / 2 * K_BENCH_PUMPKIN, z))
    every = ("front", "back", "left", "right", "top", "bottom")
    knife = box_node("Carving_Knife", (0, 0, 0), q_axis("y", BENCH_KNIFE_YAW), (2, 2, 5), (1, 1, 1),
                     {f: (HANDLE[0] + sx, HANDLE[1] + sy) for f in every})
    knife["children"].append(box_node("Carving_Knife_Blade", (0, -0.5, 6.5), (0, 0, 0, 1),
                                      (2, 1, 8), (1, 1, 1), {f: BLADE for f in every}))
    x, z = BENCH_KNIFE_AT
    hang(knife, tabletop, frames, (x, TABLETOP_Y + 1, z))
    for i, (x, z) in enumerate(BENCH_BITS_AT, start=1):
        bit = box_node(f"Carving_Bit{i}", (0, 0, 0), q_axis("y", 30 * i), (2, 2, 2), (1, 1, 1),
                       {f: BENCH_BITS for f in every})
        hang(bit, tabletop, frames, (x, TABLETOP_Y + 1, z))
    return finish_model(root)


def lost_soul_model(spirit):
    """The Lost Soul: the Spirit_Ember rig whole (its animations are Spirit_Root's set), with
    the horns' shapes hidden, so it reads as a round, pale soul rather than an ember demon."""
    root = vanilla_root(spirit)
    for node in walk([root]):
        if node["name"].startswith(LOST_SOUL_HIDDEN_PREFIXES):
            node["shape"]["visible"] = False
    return finish_model(root)


def geode_wraith_model(wraith):
    """The Geode Wraith: the Wraith rig whole (its animations are the Player set) with lit
    amethyst growing out of its back and shoulders."""
    root = vanilla_root(wraith)
    for name, parent_name, root_at, size, pitch_roll in WRAITH_CRYSTALS:
        crystal = crystal_node(name, root_at, size, pitch_roll,
                               WRAITH_CRYSTAL_SIDE, WRAITH_CRYSTAL_TOP)
        find_node(root, parent_name).setdefault("children", []).append(crystal)
    return finish_model(root)


# =========================================================================================
# Textures
# =========================================================================================

def hex_rgb(value):
    value = value.lstrip("#")
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


def rect_mask(rect, shape=(64, 64)):
    mask = np.zeros(shape, dtype=bool)
    x, y, w, h = rect
    mask[y:y + h, x:x + w] = True
    return mask


def luminance(rgb):
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def box_blur(values, radius):
    """Mean over a (2r+1)^2 window, edges clamped. Pure numpy, so it is bit-stable."""
    padded = np.pad(values, radius, mode="edge")
    size = 2 * radius + 1
    out = np.zeros_like(values)
    for dy in range(size):
        for dx in range(size):
            out += padded[dy:dy + values.shape[0], dx:dx + values.shape[1]]
    return out / (size * size)


def dilate(mask, radius):
    """Grows a boolean mask by `radius` pixels (square neighbourhood)."""
    padded = np.pad(mask, radius)
    out = np.zeros_like(mask)
    size = 2 * radius + 1
    for dy in range(size):
        for dx in range(size):
            out |= padded[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return out


def ramp(t, stops):
    """Piecewise-linear colour ramp; stops are (position, '#rrggbb')."""
    t = np.clip(t, 0.0, 1.0)
    out = np.zeros(t.shape + (3,))
    positions = [p for p, _ in stops]
    colours = [hex_rgb(c) for _, c in stops]
    for channel in range(3):
        out[..., channel] = np.interp(t, positions, [c[channel] for c in colours])
    return out


class Paint:
    """A float RGBA copy of the seed texture with its region masks."""

    def __init__(self, seed_texture):
        self.rgba = seed_texture.astype(np.float64) / 255.0
        opaque = self.rgba[..., 3] > 0
        self.rind = opaque & (rect_mask(FRONT) | rect_mask(SIDE) | rect_mask(TOP))
        self.glow = rect_mask(GLOW) & opaque
        self.stem = rect_mask(STEM) & opaque
        rgb = self.rgba[..., :3]
        self.lum = luminance(rgb)
        self.rind_ref = float(self.lum[self.rind].mean())
        # Grooves: rind pixels darker than their neighbourhood (the ribs and carve rims).
        filled = np.where(self.rind, self.lum, self.rind_ref)
        self.groove = np.clip((box_blur(filled, 2) - self.lum) / 0.10, 0.0, 1.0) * self.rind
        # The carved cut-outs, and the rind right around them.
        holes = rect_mask(FRONT) & ~opaque
        self.rim = dilate(holes, 1) & self.rind
        self.near_hole = dilate(holes, 2) & self.rind

    def set(self, mask, rgb):
        self.rgba[..., :3] = np.where(mask[..., None], np.clip(rgb, 0.0, 1.0), self.rgba[..., :3])

    def tint_rind(self, colour, strength, gain=1.0):
        rgb = self.rgba[..., :3]
        shaded = hex_rgb(colour)[None, None, :] * (self.lum / self.rind_ref * gain)[..., None]
        self.set(self.rind, rgb * (1 - strength) + shaded * strength)

    def glow_ramp(self, stops):
        lum = self.lum
        lo, hi = float(lum[self.glow].min()), float(lum[self.glow].max())
        self.set(self.glow, ramp((lum - lo) / max(hi - lo, 1e-6), stops))

    def fill(self, rect, rgb_rows):
        """Paints `rect` row by row: rgb_rows[y][x] are '#rrggbb' strings."""
        x, y, w, h = rect
        for dy in range(h):
            for dx in range(w):
                self.rgba[y + dy, x + dx, :3] = hex_rgb(rgb_rows[dy][dx])
                self.rgba[y + dy, x + dx, 3] = 1.0

    def png(self):
        data = np.clip(np.rint(self.rgba * 255.0), 0, 255).astype(np.uint8)
        return png_bytes(Image.fromarray(data))


def paint_fuse(p):
    cord = ["#4a3322", "#6b4a2e", "#33231a"]
    p.fill(FUSE_CORD, [[cord[(x + y) % 3] for x in range(3)] for y in range(8)])
    p.fill(FUSE_CORD_END, [["#3a281b"] * 3 for _ in range(3)])
    burn = ["#ffd36b", "#ff9a2e", "#d2581c", "#7a3a1e", "#4a3322"]
    p.fill(FUSE_BURN, [[burn[y]] * 3 for y in range(5)])
    p.fill(FUSE_BURN_END, [["#ff9a2e"] * 3 for _ in range(3)])
    p.fill(FUSE_TIP, [["#fff4b8"] * 3])
    p.fill(FUSE_TIP_END, [["#ffd36b", "#ffe98f", "#ffd36b"],
                          ["#ffe98f", "#fffbe6", "#ffe98f"],
                          ["#ffd36b", "#ffe98f", "#ffd36b"]])


def paint_handle(p):
    grain = ["#5e3d22", "#6e4828", "#7a5230", "#6e4828", "#5e3d22", "#4e321c", "#43291a"]
    rows = []
    for y in range(HANDLE[3]):
        row = [grain[y]] * HANDLE[2]
        for x in range(HANDLE[2]):
            if (x * 7 + y * 3) % 11 == 0:
                row[x] = "#4a2f1a"
        rows.append(row)
    p.fill(HANDLE, rows)


def wear_mark(p):
    """Marks the helm as worn gear: a hollowed neck rim, a leather chin band and cheek straps.

    The band and rim run along the bottom of the carved face and of the rind region; that
    region is the back, right and (mirrored) left face, so the band goes right round the helm.
    The strap is centred on the rind region, so it sits mid-cheek on both sides and down the
    nape at the back, and meets the band. The face's cut-outs and the glow are untouched.
    """
    leather_top, leather, leather_edge = hex_rgb("#7a4b2a"), hex_rgb("#55311a"), hex_rgb("#341c0e")
    for x, y, w, _ in (FRONT, SIDE):
        cols = slice(x, x + w)
        p.rgba[y + HELM_BAND_ROWS[0], cols, :3] = leather_top
        p.rgba[y + HELM_BAND_ROWS[1], cols, :3] = leather
        p.rgba[y + HELM_RIM_ROWS[0], cols, :3] = p.rgba[y + HELM_RIM_ROWS[0], cols, :3] * 0.4
        p.rgba[y + HELM_RIM_ROWS[1], cols, :3] = hex_rgb("#1a0d06")
    sx, sy, sw, sh = HELM_STRAP
    top = SIDE[1] + sy
    p.rgba[top:top + sh, sx:sx + sw, :3] = leather
    p.rgba[top:top + sh, sx + 1, :3] = leather_top
    p.rgba[top:top + sh, sx, :3] = leather_edge
    p.rgba[top:top + sh, sx + sw - 1, :3] = leather_edge
    bx, by, bw, bh = HELM_BUCKLE
    top = SIDE[1] + by
    p.rgba[top:top + bh, bx:bx + bw, :3] = hex_rgb("#b8862f")
    p.rgba[top, bx:bx + bw, :3] = hex_rgb("#e8c063")
    p.rgba[top + bh - 1, bx:bx + bw, :3] = hex_rgb("#7a5518")
    p.rgba[top + 1:top + bh - 1, bx + 2:bx + bw - 2, :3] = leather_edge


def char(p):
    """Charred rind: charcoal with ember cracks along the ribs, and a black rim round the cut-outs."""
    charcoal = hex_rgb("#2b1d17")[None, None, :] * (0.55 + 0.75 * p.lum / p.rind_ref)[..., None]
    crack = np.clip((p.groove - 0.35) / 0.65, 0, 1) * ~p.near_hole
    ember = ramp(crack, [(0.0, "#5a2412"), (0.5, "#c8400e"), (1.0, "#ff8a24")])
    t = np.clip(crack * 1.3, 0, 1)[..., None]
    p.set(p.rind, charcoal * (1 - t) + ember * t)
    p.set(p.rim, hex_rgb("#120b08")[None, None, :] * np.ones_like(p.lum)[..., None])
    p.set(p.stem, hex_rgb("#1b1411")[None, None, :] * (0.6 + 0.8 * p.lum[..., None]))
    p.glow_ramp([(0.0, "#c42a00"), (0.45, "#ff7a12"), (0.8, "#ffd23f"), (1.0, "#fff7d6")])


def hollow(p):
    """A pale ghost pumpkin with a cold glow."""
    pale = hex_rgb("#e4e8ef")[None, None, :] * (0.35 + 0.65 * p.lum / p.rind_ref)[..., None]
    rib = hex_rgb("#6f7f9c")[None, None, :] * (0.7 + 0.3 * p.lum / p.rind_ref)[..., None]
    t = np.clip(p.groove * 1.1, 0, 1)[..., None]
    p.set(p.rind, pale * (1 - t) + rib * t)
    grey = luminance(p.rgba[..., :3])[..., None] * hex_rgb("#c8c2b8")[None, None, :] * 1.1
    p.set(p.stem, grey)
    p.glow_ramp([(0.0, "#1d4fa8"), (0.45, "#3fb6ff"), (0.8, "#a8ecff"), (1.0, "#f2ffff")])


def ecto(p):
    """The Ecto Lantern: a sickly rind and an ectoplasm glow, green running from each cut-out."""
    p.tint_rind("#7f7a36", 0.6, 0.95)
    p.glow_ramp([(0.0, "#0e5a2a"), (0.45, "#2fe07a"), (0.8, "#a4ffc8"), (1.0, "#f0fff6")])
    x0, y0, w, h = FRONT
    alpha = p.rgba[..., 3]
    for x in range(x0, x0 + w):
        for row in range(h - 1):
            if alpha[y0 + row, x] == 0 and alpha[y0 + row + 1, x] > 0:   # a cut-out's bottom edge
                for d in range(1, 2 + (x * 7 + row * 3) % 4):
                    y = y0 + row + d
                    if y >= y0 + h or alpha[y, x] == 0:
                        break
                    p.rgba[y, x, :3] = hex_rgb("#a4ffc8" if d == 1 else "#3fd98a")


def hallowed(p):
    """The Hallowed Pumpkin: a midnight-violet rind with gold light along the ribs."""
    violet = hex_rgb("#3d2456")[None, None, :] * (0.55 + 0.75 * p.lum / p.rind_ref)[..., None]
    gold = ramp(np.clip(p.groove * 1.4, 0, 1), [(0.0, "#5a3a2a"), (0.5, "#c8902a"), (1.0, "#ffe08a")])
    t = np.clip(p.groove * 1.3, 0, 1)[..., None]
    p.set(p.rind, violet * (1 - t) + gold * t)
    p.set(p.stem, hex_rgb("#2a1f17")[None, None, :] * (0.7 + 0.6 * p.lum[..., None]))


def textures(seed_texture):
    out = {}
    for tier, (colour, strength, gain) in TIERS.items():
        p = Paint(seed_texture)
        p.tint_rind(colour, strength, gain)
        paint_fuse(p)
        out[f"Lantern_Bomb/Lantern_Bomb_{tier}_Texture.png"] = p
    helm = Paint(seed_texture)
    wear_mark(helm)
    out["Jack_Helm/Jack_Helm_Texture.png"] = helm
    burning = Paint(seed_texture)
    char(burning)
    wear_mark(burning)
    out["Jack_Helm/Burning_Jack_Helm_Texture.png"] = burning
    shield = Paint(seed_texture)
    paint_handle(shield)
    out["Jack_Shield/Jack_Shield_Texture.png"] = shield
    flaming = Paint(seed_texture)
    char(flaming)
    paint_handle(flaming)
    out["Jack_Shield/Flaming_Jack_Shield_Texture.png"] = flaming
    out["Jack_Lantern/Jack_Lantern_Texture.png"] = Paint(seed_texture)
    pale = Paint(seed_texture)
    hollow(pale)
    out["Jack_Lantern/Hollow_Lantern_Texture.png"] = pale
    ecto_lantern = Paint(seed_texture)
    ecto(ecto_lantern)
    out["Jack_Lantern/Ecto_Lantern_Texture.png"] = ecto_lantern
    pumpkin = Paint(seed_texture)
    hallowed(pumpkin)
    out["Hallowed_Pumpkin/Hallowed_Pumpkin_Texture.png"] = pumpkin
    return out


def float_png(rgba):
    """PNG bytes of a float RGBA image (0..1), rounded the way Paint.png rounds."""
    data = np.clip(np.rint(rgba * 255.0), 0, 255).astype(np.uint8)
    return png_bytes(Image.fromarray(data))


def rgb_to_hsv(rgb):
    """Vectorised RGB (0..1) to HSV, hue in [0, 1)."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
    d = mx - mn
    safe = np.where(d > 1e-12, d, 1.0)
    hue = np.select([d <= 1e-12, mx == r, mx == g],
                    [np.zeros_like(mx), ((g - b) / safe) % 6.0, (b - r) / safe + 2.0],
                    (r - g) / safe + 4.0) / 6.0
    sat = np.where(mx > 1e-12, d / np.where(mx > 1e-12, mx, 1.0), 0.0)
    return np.stack([hue, sat, mx], axis=-1)


def hsv_to_rgb(hsv):
    h, s, v = hsv[..., 0] % 1.0, hsv[..., 1], hsv[..., 2]
    i = np.floor(h * 6.0).astype(int) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return np.stack([np.choose(i, [v, q, p, p, t, v]),
                     np.choose(i, [t, v, v, q, p, p]),
                     np.choose(i, [p, p, t, v, v, q])], axis=-1)


def hash01(x, y, salt):
    """Integer-hash noise in [0, 1): the same pixel and salt always give the same value."""
    x = np.asarray(x, dtype=np.uint64)
    y = np.asarray(y, dtype=np.uint64)
    mask = np.uint64(0xFFFFFFFF)
    v = (x * np.uint64(374761393) + y * np.uint64(668265263) + np.uint64(salt * 2246822519)) & mask
    v = ((v ^ (v >> np.uint64(13))) * np.uint64(1274126177)) & mask
    return ((v ^ (v >> np.uint64(16))) & np.uint64(0xFFFF)).astype(np.float64) / 65536.0


def paint_stone(rgba, rect, salt):
    """Cool, cursed stone: two octaves of hash noise through a grey-violet ramp, edges darker."""
    x, y, w, h = rect
    ys, xs = np.mgrid[y:y + h, x:x + w]
    n = 0.55 * hash01(xs // 2, ys // 2, salt) + 0.45 * hash01(xs, ys, salt + 1)
    colour = ramp(n, [(0.0, "#2b2530"), (0.55, "#4d4552"), (1.0, "#7a7080")])
    edge = (xs == x) | (xs == x + w - 1) | (ys == y) | (ys == y + h - 1)
    rgba[y:y + h, x:x + w, :3] = np.where(edge[..., None], colour * 0.75, colour)
    rgba[y:y + h, x:x + w, 3] = 1.0


def paint_crystal(rgba, side, top):
    """Amethyst: each side face light at the tip and dark at the root, one edge lit."""
    x, y, w, h = side
    for row in range(h):
        colour = ramp(np.array(1 - row / max(h - 1, 1)), [(0.0, "#4a1f7a"), (0.6, "#a86bff"), (1.0, "#f1ddff")])
        for col in range(w):
            shade = 0.8 if col == 0 else (1.1 if col == w - 1 else 1.0)
            rgba[y + row, x + col, :3] = np.clip(colour * shade, 0, 1)
    rgba[y:y + h, x:x + w, 3] = 1.0
    x, y, w, h = top
    rgba[y:y + h, x:x + w, :3] = hex_rgb("#e9d4ff")
    rgba[y + h // 2, x + w // 2, :3] = hex_rgb("#ffffff")
    rgba[y:y + h, x:x + w, 3] = 1.0


def geode_texture():
    """The Cursed Geode's 64x64 texture: stone, the crack cut through the front, the glow."""
    rgba = np.zeros((64, 64, 4))
    for salt, rect in enumerate((GEODE_FRONT, GEODE_SIDE, GEODE_TOP), start=1):
        paint_stone(rgba, rect, 10 * salt)
    x0, y0 = GEODE_FRONT[:2]
    crack = np.zeros((64, 64), dtype=bool)
    for row, col in enumerate(GEODE_CRACK):
        crack[y0 + row, x0 + col] = True
        if row in GEODE_WIDE_ROWS:
            crack[y0 + row, x0 + col + 1] = True
    rim = dilate(crack, 1) & ~crack & rect_mask(GEODE_FRONT)
    rgba[..., :3] = np.where(rim[..., None], rgba[..., :3] * 0.5 + hex_rgb("#9a5cff") * 0.5, rgba[..., :3])
    rgba[crack] = 0.0
    gx, gy, gw, gh = GEODE_GLOW
    ys, xs = np.mgrid[0:gh, 0:gw]
    dist = np.hypot((xs + 0.5 - gw / 2) / (gw / 2), (ys + 0.5 - gh / 2) / (gh / 2))
    rgba[gy:gy + gh, gx:gx + gw, :3] = ramp(1 - np.clip(dist, 0, 1),
                                            [(0.0, "#3b1466"), (0.5, "#9a4dff"), (1.0, "#f3dcff")])
    rgba[gy:gy + gh, gx:gx + gw, 3] = 1.0
    paint_crystal(rgba, GEODE_CRYSTAL_SIDE, GEODE_CRYSTAL_TOP)
    return rgba


def face_mask(model, names, shape):
    """Every texel that a face of one of the named nodes covers."""
    mask = np.zeros(shape, dtype=bool)
    for node in walk(model["nodes"]):
        s = node.get("shape") or {}
        if node["name"] not in names or s.get("type") not in ("box", "quad"):
            continue
        for face, entry in s.get("textureLayout", {}).items():
            x0, y0, x1, y1 = face_rect(entry, *face_dims(s, face))
            mask[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)] = True
    return mask


def wand_texture(model, texture):
    """The Costume Wand: the vanilla wood wand's texture, each part tinted with its shading kept."""
    rgba = texture.astype(np.float64) / 255.0
    lum = luminance(rgba[..., :3])
    opaque = rgba[..., 3] > 0
    for names, colour, strength, gain in WAND_PARTS:
        mask = face_mask(model, names, opaque.shape) & opaque
        ref = float(lum[mask].mean())
        shaded = hex_rgb(colour)[None, None, :] * (lum / ref * gain)[..., None]
        mixed = np.clip(rgba[..., :3] * (1 - strength) + shaded * strength, 0, 1)
        rgba[..., :3] = np.where(mask[..., None], mixed, rgba[..., :3])
    return rgba


def ectoplasm_texture(texture):
    """Ectoplasm: the vanilla life essence's shading, mapped onto a ghost green."""
    rgba = texture.astype(np.float64) / 255.0
    opaque = rgba[..., 3] > 0
    lum = luminance(rgba[..., :3])
    lo, hi = float(lum[opaque].min()), float(lum[opaque].max())
    colour = ramp((lum - lo) / max(hi - lo, 1e-6),
                  [(0.0, "#0b3a2c"), (0.45, "#1fb37a"), (0.8, "#7dffc4"), (1.0, "#effff8")])
    rgba[..., :3] = np.where(opaque[..., None], colour, rgba[..., :3])
    return rgba


def bench_texture(workbench_texture, seed_texture):
    """The Carving Bench atlas: the Workbench's texture weathered on top, the seed's below
    (the knife handle's grain painted into it), and the knife's steel beside that."""
    rgba = np.zeros((BENCH_SIZE[1], BENCH_SIZE[0], 4))
    wood = workbench_texture.astype(np.float64) / 255.0
    grey = luminance(wood[..., :3])[..., None]
    wood[..., :3] = np.clip((wood[..., :3] * 0.7 + grey * 0.3) * 0.88, 0, 1)
    rgba[:wood.shape[0], :wood.shape[1]] = wood
    seed = Paint(seed_texture)
    paint_handle(seed)
    sx, sy = BENCH_SEED_AT
    rgba[sy:sy + 64, sx:sx + 64] = seed.rgba
    bx, by, bw, bh = BLADE
    steel = ["#e9eef2", "#cfd6dc", "#b3bcc4", "#98a2ab", "#7f8a94", "#69737d", "#555e67", "#434a52"]
    for row in range(bh):
        rgba[by + row, bx:bx + bw, :3] = hex_rgb(steel[row])
    rgba[by:by + bh, bx:bx + bw, 3] = 1.0
    return rgba


def soul_texture(texture):
    """The Lost Soul: the ember spirit's rock turns a pale blue and its fire a cold mint."""
    rgba = texture.astype(np.float64) / 255.0
    opaque = rgba[..., 3] > 0
    rgb = rgba[..., :3]
    lum = luminance(rgb)
    hsv = rgb_to_hsv(rgb)
    fire = opaque & (hsv[..., 2] > 0.7) & (hsv[..., 1] > 0.3)
    body = opaque & ~fire
    lo, hi = float(lum[body].min()), float(lum[body].max())
    pale = ramp((lum - lo) / max(hi - lo, 1e-6),
                [(0.0, "#26364e"), (0.35, "#6789a8"), (0.75, "#c4dfec"), (1.0, "#f4fbfd")])
    flo, fhi = float(lum[fire].min()), float(lum[fire].max())
    cold = ramp((lum - flo) / max(fhi - flo, 1e-6), [(0.0, "#1f8f6a"), (0.5, "#62f0b4"), (1.0, "#f0fff8")])
    rgba[..., :3] = np.where(fire[..., None], cold, np.where(body[..., None], pale, rgb))
    return rgba


def hollow_ghoul_texture(texture):
    """The Hollow Ghoul: the Ghoul's skin and hair turn ash grey and its cyan eyes a pumpkin glow."""
    rgba = texture.astype(np.float64) / 255.0
    hsv = rgb_to_hsv(rgba[..., :3])
    hue, sat, val = hsv[..., 0] * 360.0, hsv[..., 1], hsv[..., 2]
    cyan = (hue > 140) & (hue < 215)
    eyes = cyan & (sat > 0.45) & (val > 0.6)
    hair = cyan & ~eyes
    skin = (hue >= 35) & (hue <= 110)
    hsv[..., 0] = np.where(eyes, 28.0 / 360.0, np.where(skin, 30.0 / 360.0, hsv[..., 0]))
    hsv[..., 1] = np.where(eyes, np.clip(sat * 1.2, 0, 1), np.where(skin | hair, sat * 0.2, sat))
    hsv[..., 2] = np.where(skin, val * 0.8, val)
    rgba[..., :3] = hsv_to_rgb(hsv)
    return rgba


def geode_wraith_texture(texture):
    """The Geode Wraith: the Wraith's teal soul-fire turns amethyst, its red sash slate and its
    robe a dusty cave grey; the rows grown under it hold the crystals' faces."""
    src = texture.astype(np.float64) / 255.0
    h, w = src.shape[:2]
    rgba = np.zeros((h + WRAITH_TEXTURE_GROWTH, w, 4))
    rgba[:h] = src
    hsv = rgb_to_hsv(src[..., :3])
    hue, sat, val = hsv[..., 0] * 360.0, hsv[..., 1], hsv[..., 2]
    fire = (hue > 150) & (hue < 210) & (sat > 0.25)
    sash = ((hue < 25) | (hue > 340)) & (sat > 0.35)
    robe = (hue >= 210) & (hue <= 300) & ~fire
    hsv[..., 0] = np.where(fire, 285.0 / 360.0, hsv[..., 0])
    hsv[..., 1] = np.where(sash, sat * 0.15, np.where(robe, sat * 0.5, sat))
    hsv[..., 2] = np.where(sash, val * 0.8, np.where(robe, np.clip(val * 1.1, 0, 1), val))
    rgba[:h, :, :3] = hsv_to_rgb(hsv)
    if WRAITH_CRYSTALS:
        paint_crystal(rgba, WRAITH_CRYSTAL_SIDE, WRAITH_CRYSTAL_TOP)
    return rgba


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=9)
    return buffer.getvalue()


# =========================================================================================
# Icon renderer: orthographic, painter-sorted, textured, then trimmed to 64x64
# =========================================================================================

def quat_matrix(q):
    x, y, z, w = (q[a] for a in "xyzw")
    n = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def euler_view(angles):
    """IconProperties.Rotation (degrees): X first, then Y, then Z, about fixed axes."""
    a, b, c = (math.radians(v) for v in angles)
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx


# Unit-box face corners TL, TR, BR, BL as Blockbench maps a face's UV rect onto them, plus
# the outward normal. Hytale names: front +Z, back -Z, right +X, left -X, top +Y, bottom -Y.
FACES = {
    "front": ([(-.5, .5, .5), (.5, .5, .5), (.5, -.5, .5), (-.5, -.5, .5)], (0, 0, 1)),
    "back": ([(.5, .5, -.5), (-.5, .5, -.5), (-.5, -.5, -.5), (.5, -.5, -.5)], (0, 0, -1)),
    "right": ([(.5, .5, .5), (.5, .5, -.5), (.5, -.5, -.5), (.5, -.5, .5)], (1, 0, 0)),
    "left": ([(-.5, .5, -.5), (-.5, .5, .5), (-.5, -.5, .5), (-.5, -.5, -.5)], (-1, 0, 0)),
    "top": ([(-.5, .5, -.5), (.5, .5, -.5), (.5, .5, .5), (-.5, .5, .5)], (0, 1, 0)),
    "bottom": ([(-.5, -.5, .5), (.5, -.5, .5), (.5, -.5, -.5), (-.5, -.5, -.5)], (0, -1, 0)),
}
QUAD_FACE = {"+Z": "front", "-Z": "back", "+X": "right", "-X": "left", "+Y": "top", "-Y": "bottom"}


def face_dims(shape, face):
    size = shape["settings"]["size"]
    if shape["type"] == "quad":
        return size["x"], size["y"]
    if face in ("front", "back"):
        return size["x"], size["y"]
    if face in ("left", "right"):
        return size["z"], size["y"]
    return size["x"], size["z"]


def face_uv(entry, w, h):
    """The UV rect [u1, v1, u2, v2] and rotation, as hytale_plugin.js parses a face."""
    ox, oy = entry["offset"]["x"], entry["offset"]["y"]
    mirror = entry.get("mirror") or {}
    mx = -1 if mirror.get("x") else 1
    my = -1 if mirror.get("y") else 1
    angle = entry.get("angle", 0)
    if angle == 90:
        w, h, mx, my = h, w, -my, mx
        return (ox, oy + h * my, ox + w * mx, oy), angle
    if angle == 270:
        w, h, mx, my = h, w, my, -mx
        return (ox + w * mx, oy, ox, oy + h * my), angle
    if angle == 180:
        return (ox - w * mx, oy - h * my, ox, oy), angle
    return (ox, oy, ox + w * mx, oy + h * my), angle


def corner_uvs(rect, rotation):
    """UV per corner TL, TR, BR, BL, Blockbench-style (rotation turns the texture clockwise)."""
    u1, v1, u2, v2 = rect
    base = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
    steps = (rotation // 90) % 4
    return [base[(i - steps) % 4] for i in range(4)]


def face_rect(entry, w, h):
    rect, _ = face_uv(entry, w, h)
    return min(rect[0], rect[2]), min(rect[1], rect[3]), max(rect[0], rect[2]), max(rect[1], rect[3])


def collect_faces(model):
    """Every textured face as (corners[4][3], normal[3], uv rect, rotation, fullbright, two-sided)."""
    faces = []

    def visit(node, parent_pos, parent_rot):
        shape = node.get("shape") or {}
        if shape.get("visible", True) is False:
            return
        rot = quat_matrix(node.get("orientation") or {"x": 0, "y": 0, "z": 0, "w": 1})
        pos = np.array([node["position"][a] for a in "xyz"], dtype=np.float64)
        off = np.array([shape.get("offset", {}).get(a, 0) for a in "xyz"], dtype=np.float64)
        world_pos = parent_pos + parent_rot @ (pos + rot @ off)
        world_rot = parent_rot @ rot
        kind = shape.get("type")
        if kind in ("box", "quad"):
            size = shape["settings"]["size"]
            stretch = np.array([shape.get("stretch", {}).get(a, 1) for a in "xyz"], dtype=np.float64)
            if kind == "box":
                extent = np.array([size["x"], size["y"], size["z"]], dtype=np.float64)
                names = list(shape.get("textureLayout", {}))
            else:
                normal = shape["settings"].get("normal", "+Z")
                w, h = size["x"], size["y"]
                extent = {"Z": (w, h, 0), "X": (0, h, w), "Y": (w, 0, h)}[normal[1]]
                extent = np.array(extent, dtype=np.float64)
                names = [QUAD_FACE[normal]] if "front" in shape.get("textureLayout", {}) else []
            extent = extent * stretch
            for name in names:
                entry = shape["textureLayout"]["front" if kind == "quad" else name]
                corners_unit, normal = FACES[name]
                corners = [world_pos + world_rot @ (np.array(c) * extent) for c in corners_unit]
                rect, rotation = face_uv(entry, *face_dims(shape, "front" if kind == "quad" else name))
                faces.append((corners, world_rot @ np.array(normal, dtype=np.float64), rect, rotation,
                              shape.get("shadingMode") == "fullbright",
                              kind == "quad" and shape.get("doubleSided", False)))
        for child in node.get("children", []):
            visit(child, world_pos, world_rot)

    for root in model["nodes"]:
        visit(root, np.zeros(3), np.eye(3))
    return faces


LIGHT = np.array([0.35, 0.8, 0.5]) / np.linalg.norm([0.35, 0.8, 0.5])


def render(model, texture_rgba, angles, size=512):
    """Draws the model's visible faces back to front; returns an RGBA float image (0..1).

    Faces are painter-sorted on their mean depth, and each pixel also keeps a depth: the glow
    quad sits 0.1 px behind the carved face, too close for any one sort key to order the two
    at every angle. The seed's alpha is 0 or 255, so a texel either covers a pixel or not.
    """
    view = euler_view(angles)
    tex = texture_rgba.astype(np.float64) / 255.0
    th, tw = tex.shape[:2]
    faces = []
    for corners, normal, rect, rotation, fullbright, two_sided in collect_faces(model):
        pts = np.array([view @ c for c in corners])
        n = view @ normal
        if n[2] <= 1e-6:
            if not two_sided:
                continue
            n = -n
        shade = 1.0 if fullbright else 0.58 + 0.42 * max(0.0, float(n @ LIGHT))
        faces.append((float(pts[:, 2].mean()), pts, rect, rotation, shade))
    faces.sort(key=lambda f: f[0])
    allpts = np.concatenate([f[1] for f in faces])
    lo, hi = allpts[:, :2].min(axis=0), allpts[:, :2].max(axis=0)
    scale = (size - 8) / max(hi - lo)
    canvas = np.zeros((size, size, 4))
    depth = np.full((size, size), -np.inf)
    centre = (lo + hi) / 2
    for _, pts, rect, rotation, shade in faces:
        screen = np.stack([(pts[:, 0] - centre[0]) * scale + size / 2,
                           -(pts[:, 1] - centre[1]) * scale + size / 2], axis=1)
        draw_face(canvas, depth, tex, (tw, th), screen, pts[:, 2], corner_uvs(rect, rotation), rect, shade)
    return canvas


def draw_face(canvas, depth, tex, tex_size, screen, z, uvs, rect, shade):
    p0, p1, p3 = screen[0], screen[1], screen[3]
    e1, e2 = p1 - p0, p3 - p0
    det = e1[0] * e2[1] - e1[1] * e2[0]
    if abs(det) < 1e-9:
        return
    h, w = canvas.shape[:2]
    x0 = max(int(math.floor(screen[:, 0].min())), 0)
    x1 = min(int(math.ceil(screen[:, 0].max())), w)
    y0 = max(int(math.floor(screen[:, 1].min())), 0)
    y1 = min(int(math.ceil(screen[:, 1].max())), h)
    if x0 >= x1 or y0 >= y1:
        return
    gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    dx, dy = gx - p0[0], gy - p0[1]
    s = (dx * e2[1] - dy * e2[0]) / det
    t = (e1[0] * dy - e1[1] * dx) / det
    inside = (s >= 0) & (s < 1) & (t >= 0) & (t < 1)
    if not inside.any():
        return
    uv0, uv1, uv3 = (np.array(uvs[i], dtype=np.float64) for i in (0, 1, 3))
    u = uv0[0] + s * (uv1[0] - uv0[0]) + t * (uv3[0] - uv0[0])
    v = uv0[1] + s * (uv1[1] - uv0[1]) + t * (uv3[1] - uv0[1])
    umin, umax = min(rect[0], rect[2]), max(rect[0], rect[2])
    vmin, vmax = min(rect[1], rect[3]), max(rect[1], rect[3])
    tx = np.clip(np.floor(u), umin, max(umin, umax - 1)).astype(int)
    ty = np.clip(np.floor(v), vmin, max(vmin, vmax - 1)).astype(int)
    tx = np.clip(tx, 0, tex_size[0] - 1)
    ty = np.clip(ty, 0, tex_size[1] - 1)
    texel = tex[ty, tx]
    pixel_z = z[0] + s * (z[1] - z[0]) + t * (z[3] - z[0])
    zone = depth[y0:y1, x0:x1]
    covers = inside & (texel[..., 3] >= 0.5) & (pixel_z > zone)
    region = canvas[y0:y1, x0:x1]
    region[..., :3] = np.where(covers[..., None], texel[..., :3] * shade, region[..., :3])
    region[..., 3] = np.where(covers, 1.0, region[..., 3])
    zone[covers] = pixel_z[covers]


def icon_png(model, texture_rgba, angles, size=64):
    """Renders, trims the alpha bounding box, centres it on a square with a 4% margin, and
    resizes to size x size with LANCZOS (the blockbench-hytale skill's icon recipe)."""
    canvas = render(model, texture_rgba, angles)
    image = Image.fromarray(np.clip(np.rint(canvas * 255), 0, 255).astype(np.uint8))
    image = image.crop(image.getchannel("A").getbbox())
    side = max(image.size)
    side += 2 * round(side * 0.04)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - image.size[0]) // 2, (side - image.size[1]) // 2))
    return png_bytes(square.resize((size, size), Image.LANCZOS))


# =========================================================================================
# Outputs, validation, CLI
# =========================================================================================

ICON_PLAN = [
    # icon folder, icon id, model, texture (Common/-relative), angle, size in px
    *[(ICONS, f"Hallows_Eve_Lantern_Bomb_{t}", f"{HE_ITEMS}/Lantern_Bomb/Lantern_Bomb.blockymodel",
       f"{HE_ITEMS}/Lantern_Bomb/Lantern_Bomb_{t}_Texture.png", ANGLE_BOMB, 64) for t in TIERS],
    (ICONS, "Hallows_Eve_Jack_Helm", f"{HE_ITEMS}/Jack_Helm/Jack_Helm.blockymodel",
     f"{HE_ITEMS}/Jack_Helm/Jack_Helm_Texture.png", ANGLE_HELM, 64),
    (ICONS, "Hallows_Eve_Burning_Jack_Helm", f"{HE_ITEMS}/Jack_Helm/Jack_Helm.blockymodel",
     f"{HE_ITEMS}/Jack_Helm/Burning_Jack_Helm_Texture.png", ANGLE_HELM, 64),
    (ICONS, "Hallows_Eve_Jack_Shield", f"{HE_ITEMS}/Jack_Shield/Jack_Shield.blockymodel",
     f"{HE_ITEMS}/Jack_Shield/Jack_Shield_Texture.png", ANGLE_SHIELD, 64),
    (ICONS, "Hallows_Eve_Flaming_Jack_Shield", f"{HE_ITEMS}/Jack_Shield/Jack_Shield.blockymodel",
     f"{HE_ITEMS}/Jack_Shield/Flaming_Jack_Shield_Texture.png", ANGLE_SHIELD, 64),
    (ICONS, "Hallows_Eve_Jack_Lantern", f"{HE_ITEMS}/Jack_Lantern/Jack_Lantern.blockymodel",
     f"{HE_ITEMS}/Jack_Lantern/Jack_Lantern_Texture.png", ANGLE_BLOCK, 64),
    (ICONS, "Hallows_Eve_Hollow_Lantern", f"{HE_ITEMS}/Jack_Lantern/Jack_Lantern.blockymodel",
     f"{HE_ITEMS}/Jack_Lantern/Hollow_Lantern_Texture.png", ANGLE_BLOCK, 64),
    (ICONS, "Hallows_Eve_Ecto_Lantern", f"{HE_ITEMS}/Jack_Lantern/Jack_Lantern.blockymodel",
     f"{HE_ITEMS}/Jack_Lantern/Ecto_Lantern_Texture.png", ANGLE_BLOCK, 64),
    (ICONS, "Hallows_Eve_Hallowed_Pumpkin", f"{HE_ITEMS}/Hallowed_Pumpkin/Hallowed_Pumpkin.blockymodel",
     f"{HE_ITEMS}/Hallowed_Pumpkin/Hallowed_Pumpkin_Texture.png", ANGLE_BLOCK, 64),
    (ICONS, "Hallows_Eve_Cursed_Geode", f"{HE_ITEMS}/Cursed_Geode/Cursed_Geode.blockymodel",
     f"{HE_ITEMS}/Cursed_Geode/Cursed_Geode_Texture.png", ANGLE_CRYSTAL, 64),
    (ICONS, "Hallows_Eve_Costume_Wand", WAND,
     f"{HE_ITEMS}/Costume_Wand/Costume_Wand_Texture.png", ANGLE_WAND, 64),
    (ICONS, "Hallows_Eve_Ectoplasm", ESSENCE,
     f"{HE_ITEMS}/Ectoplasm/Ectoplasm_Texture.png", ANGLE_ESSENCE, 64),
    (ICONS, "Hallows_Eve_Carving_Bench", f"{HE_BLOCKS}/Carving_Bench/Carving_Bench.blockymodel",
     f"{HE_BLOCKS}/Carving_Bench/Carving_Bench_Texture.png", ANGLE_BLOCK, 64),
    (MODEL_ICONS, "Hallows_Eve_Lost_Soul", f"{HE_NPCS}/Lost_Soul/Lost_Soul.blockymodel",
     f"{HE_NPCS}/Lost_Soul/Lost_Soul_Texture.png", ANGLE_MODEL, 128),
    (MODEL_ICONS, "Hallows_Eve_Geode_Wraith", f"{HE_NPCS}/Geode_Wraith/Geode_Wraith.blockymodel",
     f"{HE_NPCS}/Geode_Wraith/Geode_Wraith_Texture.png", ANGLE_MODEL, 128),
    (MODEL_ICONS, "Hallows_Eve_Hollow_Ghoul", GHOUL,
     f"{HE_NPCS}/Hollow_Ghoul/Hollow_Ghoul_Texture.png", ANGLE_MODEL, 128),
]


def build(seed_dir):
    """Returns ({pack-relative path: bytes}, {Common/-relative model path: model dict, the two
    vanilla rigs an icon renders from included}, {Common/-relative texture path: rgba})."""
    seed_base, seed_texture = load_seed(seed_dir)
    vanilla = load_vanilla(seed_dir)
    models = {
        f"{HE_ITEMS}/Lantern_Bomb/Lantern_Bomb.blockymodel": bomb_model(seed_base, center=False),
        f"{HE_ITEMS}/Lantern_Bomb/Lantern_Bomb_Center.blockymodel": bomb_model(seed_base, center=True),
        f"{HE_ITEMS}/Jack_Helm/Jack_Helm.blockymodel": helm_model(seed_base),
        f"{HE_ITEMS}/Jack_Shield/Jack_Shield.blockymodel": shield_model(seed_base),
        f"{HE_ITEMS}/Jack_Lantern/Jack_Lantern.blockymodel": lantern_model(seed_base),
        f"{HE_ITEMS}/Hallowed_Pumpkin/Hallowed_Pumpkin.blockymodel": pumpkin_model(seed_base),
        f"{HE_ITEMS}/Cursed_Geode/Cursed_Geode.blockymodel": geode_model(),
        f"{HE_BLOCKS}/Carving_Bench/Carving_Bench.blockymodel": bench_model(vanilla[WORKBENCH], seed_base),
        f"{HE_NPCS}/Lost_Soul/Lost_Soul.blockymodel": lost_soul_model(vanilla[SPIRIT]),
        f"{HE_NPCS}/Geode_Wraith/Geode_Wraith.blockymodel": geode_wraith_model(vanilla[WRAITH]),
    }
    images = {f"{HE_ITEMS}/{name}": paint.rgba for name, paint in textures(seed_texture).items()}
    images[f"{HE_ITEMS}/Cursed_Geode/Cursed_Geode_Texture.png"] = geode_texture()
    images[f"{HE_ITEMS}/Costume_Wand/Costume_Wand_Texture.png"] = wand_texture(vanilla[WAND], vanilla[WAND_TEXTURE])
    images[f"{HE_ITEMS}/Ectoplasm/Ectoplasm_Texture.png"] = ectoplasm_texture(vanilla[ESSENCE_TEXTURE])
    images[f"{HE_BLOCKS}/Carving_Bench/Carving_Bench_Texture.png"] = bench_texture(
        vanilla[WORKBENCH_TEXTURE], seed_texture)
    images[f"{HE_NPCS}/Lost_Soul/Lost_Soul_Texture.png"] = soul_texture(vanilla[SPIRIT_TEXTURE])
    images[f"{HE_NPCS}/Geode_Wraith/Geode_Wraith_Texture.png"] = geode_wraith_texture(vanilla[WRAITH_TEXTURE])
    images[f"{HE_NPCS}/Hollow_Ghoul/Hollow_Ghoul_Texture.png"] = hollow_ghoul_texture(vanilla[GHOUL_TEXTURE])
    outputs = {}
    for name, model in models.items():
        outputs[f"Common/{name}"] = (json.dumps(model, indent=2) + "\n").encode("utf-8")
    texture_rgba = {}
    for name, rgba in images.items():
        data = float_png(rgba)
        outputs[f"Common/{name}"] = data
        with Image.open(io.BytesIO(data)) as image:
            texture_rgba[name] = np.array(image.convert("RGBA"))
    rigs = dict(models)
    rigs[WAND] = vanilla[WAND]
    rigs[ESSENCE] = vanilla[ESSENCE]
    rigs[GHOUL] = vanilla[GHOUL]
    for folder, icon, model_name, texture_name, angles, size in ICON_PLAN:
        outputs[f"{folder}/{icon}.png"] = icon_png(rigs[model_name], texture_rgba[texture_name], angles, size)
    return dict(sorted(outputs.items())), rigs, texture_rgba


def validate(models, texture_rgba):
    """The structural rules every derived model, and every vanilla rig worn with one of our
    textures, must keep; returns a list of problems."""
    problems = []
    pairs = {name: sorted({t for _, _, m, t, _, _ in ICON_PLAN if m == name}) for name in models}
    pairs[f"{HE_ITEMS}/Lantern_Bomb/Lantern_Bomb_Center.blockymodel"] = pairs[
        f"{HE_ITEMS}/Lantern_Bomb/Lantern_Bomb.blockymodel"]
    for name, model in models.items():
        nodes = list(walk(model["nodes"]))
        if len(nodes) > 255:
            problems.append(f"{name}: {len(nodes)} nodes (max 255)")
        if not pairs[name]:
            problems.append(f"{name}: no texture is checked against it")
        for node in nodes:
            shape = node.get("shape") or {}
            if shape.get("type") not in ("box", "quad"):
                continue
            size = shape["settings"]["size"]
            for axis in ("xy" if shape["type"] == "quad" else "xyz"):
                if type(size.get(axis)) is not int:
                    problems.append(f"{name} {node['name']}: size.{axis} = {size.get(axis)!r}")
            for texture in pairs[name]:
                th, tw = texture_rgba[texture].shape[:2]
                for face, entry in shape["textureLayout"].items():
                    x0, y0, x1, y1 = face_rect(entry, *face_dims(shape, face))
                    if x0 < 0 or y0 < 0 or x1 > tw or y1 > th:
                        problems.append(f"{name} {node['name']}.{face}: rect {(x0, y0, x1, y1)} "
                                        f"outside {texture} ({tw}x{th})")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate and compare; write nothing")
    parser.add_argument("--out", type=Path, default=PACK, help="output root (default: the pack)")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED, help="folder holding the seed")
    parser.add_argument("--vendor", type=Path, metavar="ZIP",
                        help="copy VANILLA_FILES out of this Assets.zip into SEED/vanilla, then stop")
    args = parser.parse_args(argv)

    if args.vendor:
        count = vendor(args.vendor, args.seed)
        print(f"vendored {count} files from {args.vendor} into {args.seed / 'vanilla'}")
        return 0
    if not (args.seed / SEED_MODEL).is_file() or not (args.seed / SEED_TEXTURE).is_file():
        print(f"seed not found in {args.seed}", file=sys.stderr)
        return 2
    missing = [rel for rel in VANILLA_FILES if not (args.seed / "vanilla" / rel).is_file()]
    if missing:
        print(f"vanilla inputs missing under {args.seed / 'vanilla'}: {', '.join(missing)}; "
              "rerun with --vendor <Assets.zip>", file=sys.stderr)
        return 2
    outputs, models, texture_rgba = build(args.seed)
    problems = validate(models, texture_rgba)

    if args.check:
        for rel, data in outputs.items():
            path = args.out / rel
            if not path.is_file():
                problems.append(f"missing: {rel}")
            elif path.read_bytes() != data:
                problems.append(f"stale: {rel}")
        for problem in problems:
            print(problem)
        print(f"checked {len(outputs)} outputs: " + ("FAIL" if problems else "OK"))
        return 1 if problems else 0

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    written = 0
    for rel, data in outputs.items():
        path = args.out / rel
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written += 1
    print(f"{len(outputs)} outputs, {written} written, {len(outputs) - written} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
