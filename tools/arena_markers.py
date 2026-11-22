#!/usr/bin/env python3
"""Writes a boss arena's shipped prefab from its source prefab and a small spec.

    python tools/arena_markers.py            # write every arena under tools/arenas/*.json
    python tools/arena_markers.py --check    # compare with the pack; writes nothing

A spec (tools/arenas/<Name>.json) names:
  Source             the source prefab, a .prefab.json or a .zip holding one (pack-relative)
  Output             the prefab the pack ships (pack-relative, under Server/Prefabs/)
  StripSpawnMarkers  true to remove every spawn marker entity the source carries (a vanilla
                     arena's own creatures), before ours go in
  Encounter          {"Id": <encounter script id>, "At": [x, y, z]}: the fight's own entity
  Markers            [{"Id": <spawn marker id>, "At": [x, y, z]}]: manual spawn markers
  Blocks             [{"Name": <block id>, "At": [x, y, z], "Rotation": <n>}]: blocks set into
                     the arena (an exit pad, a brazier), replacing whatever the source had in
                     that cell; Rotation, the prefab's own rotation index, is optional
  Points             [{"Name": <label>, "Tags": [<tag>, ...], "At": [x, y, z]}]: tagged points
                     an encounter's Points sensor finds (where a health pack drops)
  Containers         [{"At": [x, y, z], "Droplist": <Server/Drops id>}]: a container block the
                     source already holds in that cell (a chest), stocked from that drop list;
                     with "Block": <block id> (and optional "Capacity", "Rotation") the container
                     is set into that cell first, for a source that holds none there

Three more keys build a cave around a source that was made to be carved into the world's
ground (the game's Yeti camps), which pasted into a dungeon's empty world would float with no
floor, walls or roof. Each is optional; a spec without them writes what it always wrote.
  Crop               {"From": [x, y, z], "To": [x, y, z]}: keep only the source's blocks inside
                     this box, both corners included
  Fills              [{"Block": <block id>, "From": [x, y, z], "To": [x, y, z]}]: solid boxes
                     laid under the source (a snow floor, an ice pillar); the source's own cells
                     win where they meet
  Skin               {"Block": <block id>, "Thickness": <n>, "Air": [{"From": [...], "To": [...]}]}:
                     the open space is every Air box plus the source's own Empty cells (what it
                     carves), less anything a block fills; every other cell within Thickness of
                     it (a cube around each open cell) that holds nothing becomes Block, so the
                     space is walled, floored and roofed the way the ground would wrap it

"At" is a block cell counted from the prefab's anchor (the cell a party arrives above), the way
the dungeon's EntryOffset counts: an entity stands on the floor of that cell, at its centre.
"From" and "To" count the same way.
The entities carry no UUID, so every paste of the prefab stages a fresh fight. Their shape is
the dev test arena's (the encounter entity and the spawn marker entity a runtime paste keeps).
A point is the game's own prefab point (a Transform and a Point component, the shape its
builder tools save): a paste registers it as a live point and places no entity.
A container's drop list is the game's own prefab chest fill, the Droplist key on the block's
ItemContainerBlock component (vanilla's Goblin_Thief_Chest prefab): each paste places a fresh
container, and the game's stash rolls the list into it as it lands, so every paste is restocked.
A rerun writes byte-identical files. A file that differs only by a CRLF line ending, as a Windows
checkout writes it, reads as current and is left alone.
"""
import argparse
import copy
import json
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PACK = TOOLS.parent
ARENAS = TOOLS / "arenas"

ENCOUNTER_ENTITY = {
    "Components": {
        "Nameplate": {"Text": ""},
        "HiddenFromAdventurePlayer": {},
        "MarkedEntitySupport": {},
        "Transform": {"Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}},
        "Intangible": {},
        "PrefabCopyable": {},
        "Model": {"Model": {"Id": "Encounter_Marker", "Scale": 1.0, "Static": False}},
        "EncounterManager": {"EncounterId": ""},
    }
}

MARKER_ENTITY = {
    "Components": {
        "SpawnMarkerComponent": {"SpawnMarker": "", "RespawnTime": 0.0, "SpawnCount": 0,
                                 "NPCReferences": [], "PersistedFlock": {},
                                 "SpawnPosition": {"X": 0.0, "Y": 0.0, "Z": 0.0}},
        "Transform": {"Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}},
        "Intangible": {},
        "Nameplate": {"Text": ""},
        "HiddenFromAdventurePlayer": {},
        "PrefabCopyable": {},
        "Model": {"Model": {"Id": "NPC_Spawn_Marker", "Scale": 1.0, "Static": False}},
    }
}

POINT_ENTITY = {
    "Components": {
        "Transform": {"Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}},
        "Point": {"Name": "", "Tags": {}},
    }
}


def load_source(path):
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".prefab.json")]
            if len(names) != 1:
                raise ValueError(f"{path}: expected one .prefab.json, found {names}")
            return json.loads(archive.read(names[0]).decode("utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def anchor(prefab):
    return prefab["anchorX"], prefab["anchorY"], prefab["anchorZ"]


def place(entity, name_key, ident, at, prefab):
    """A copy of `entity` named `ident`, standing on the floor of cell `at` (counted from the anchor)."""
    out = copy.deepcopy(entity)
    comps = out["Components"]
    ax, ay, az = anchor(prefab)
    comps["Transform"]["Position"] = {"X": at[0] + ax + 0.5, "Y": float(at[1] + ay), "Z": at[2] + az + 0.5}
    if name_key == "Point":
        comps["Point"]["Name"] = ident["Name"]
        comps["Point"]["Tags"] = {tag: "Empty" for tag in ident["Tags"]}
        return out
    comps["Nameplate"]["Text"] = ident
    if name_key == "EncounterManager":
        comps["EncounterManager"]["EncounterId"] = ident
    else:
        comps["SpawnMarkerComponent"]["SpawnMarker"] = ident
    return out


def box_cells(box, prefab):
    """Every file cell of `box` ({"From": [...], "To": [...]}, counted from the anchor), corners included."""
    ax, ay, az = anchor(prefab)
    lo = [min(a, b) for a, b in zip(box["From"], box["To"])]
    hi = [max(a, b) for a, b in zip(box["From"], box["To"])]
    for y in range(lo[1] + ay, hi[1] + ay + 1):
        for z in range(lo[2] + az, hi[2] + az + 1):
            for x in range(lo[0] + ax, hi[0] + ax + 1):
                yield (x, y, z)


def crop(blocks, box, prefab):
    """The source's blocks inside `box`, in the source's order."""
    keep = set(box_cells(box, prefab))
    return [b for b in blocks if (b["x"], b["y"], b["z"]) in keep]


def cave(blocks, spec, prefab):
    """The source's blocks with the spec's Fills laid under them and its Skin wrapped around the open
    space: the source's own blocks first, in their order, then every generated cell sorted by y, z, x."""
    held = {(b["x"], b["y"], b["z"]): b["name"] for b in blocks}
    made = {}
    for fill in spec.get("Fills", []):
        for cell in box_cells(fill, prefab):
            if cell not in held:
                made[cell] = fill["Block"]
    skin = spec.get("Skin")
    if skin:
        open_cells = {cell for cell, name in held.items() if name == "Empty"}
        for box in skin.get("Air", []):
            open_cells.update(c for c in box_cells(box, prefab) if c not in made and held.get(c, "Empty") == "Empty")
        n = skin["Thickness"]
        reach = [(dx, dy, dz) for dy in range(-n, n + 1) for dz in range(-n, n + 1) for dx in range(-n, n + 1)]
        for (x, y, z) in open_cells:
            for dx, dy, dz in reach:
                cell = (x + dx, y + dy, z + dz)
                if cell not in held and cell not in made and cell not in open_cells:
                    made[cell] = skin["Block"]
    extra = [{"x": x, "y": y, "z": z, "name": made[(x, y, z)]}
             for (x, y, z) in sorted(made, key=lambda c: (c[1], c[2], c[0]))]
    return blocks + extra


def stock(blocks, container, prefab):
    """Name a drop list on the container block in cell `container["At"]` (counted from the anchor)."""
    ax, ay, az = anchor(prefab)
    at = container["At"]
    cell = (at[0] + ax, at[1] + ay, at[2] + az)
    if "Block" in container:
        capacity = container.get("Capacity", 18)
        blocks[:] = [b for b in blocks if (b["x"], b["y"], b["z"]) != cell]
        placed = {"x": cell[0], "y": cell[1], "z": cell[2], "name": container["Block"],
                  "components": {"Components": {"ItemContainerBlock": {
                      "ItemContainer": {"Capacity": capacity, "Items": {}}, "Capacity": capacity}}}}
        if "Rotation" in container:
            placed["rotation"] = container["Rotation"]
        blocks.append(placed)
    for block in blocks:
        if (block["x"], block["y"], block["z"]) != cell:
            continue
        state = block.get("components", {}).get("Components", {}).get("ItemContainerBlock")
        if state is None:
            break
        rest = {k: v for k, v in state.items() if k != "Droplist"}
        block["components"]["Components"]["ItemContainerBlock"] = {"Droplist": container["Droplist"], **rest}
        return
    raise ValueError(f"Containers: no container block at cell {at} (source cell {list(cell)})")


def build(spec):
    prefab = load_source(PACK / spec["Source"])
    ax, ay, az = anchor(prefab)
    entities = prefab.get("entities", [])
    if spec.get("StripSpawnMarkers"):
        entities = [e for e in entities if "SpawnMarkerComponent" not in e.get("Components", {})]
    encounter = spec["Encounter"]
    entities.append(place(ENCOUNTER_ENTITY, "EncounterManager", encounter["Id"], encounter["At"], prefab))
    for marker in spec.get("Markers", []):
        entities.append(place(MARKER_ENTITY, "SpawnMarker", marker["Id"], marker["At"], prefab))
    for point in spec.get("Points", []):
        entities.append(place(POINT_ENTITY, "Point", point, point["At"], prefab))
    prefab["entities"] = entities
    blocks = prefab.get("blocks", [])
    if "Crop" in spec:
        blocks = crop(blocks, spec["Crop"], prefab)
    if "Fills" in spec or "Skin" in spec:
        blocks = cave(blocks, spec, prefab)
    for block in spec.get("Blocks", []):
        x, y, z = (block["At"][0] + ax, block["At"][1] + ay, block["At"][2] + az)
        blocks = [b for b in blocks if (b["x"], b["y"], b["z"]) != (x, y, z)]
        placed = {"x": x, "y": y, "z": z, "name": block["Name"]}
        if "Rotation" in block:
            placed["rotation"] = block["Rotation"]
        blocks.append(placed)
    for container in spec.get("Containers", []):
        stock(blocks, container, prefab)
    prefab["blocks"] = blocks
    return (json.dumps(prefab, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def same(out, data):
    """True when the file on disk holds `data`, reading a CRLF line ending (a Windows checkout's) as LF."""
    return out.read_bytes().replace(b"\r\n", b"\n") == data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the pack; write nothing")
    args = parser.parse_args(argv)
    problems, written = [], 0
    specs = sorted(ARENAS.glob("*.json"))
    for spec_path in specs:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        data = build(spec)
        out = PACK / spec["Output"]
        if args.check:
            if not out.is_file():
                problems.append(f"missing: {spec['Output']}")
            elif not same(out, data):
                problems.append(f"stale: {spec['Output']}")
            continue
        if out.is_file() and same(out, data):
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        written += 1
    for problem in problems:
        print(problem)
    if args.check:
        print(f"checked {len(specs)} arenas: " + ("FAIL" if problems else "OK"))
        return 1 if problems else 0
    print(f"{len(specs)} arenas, {written} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
