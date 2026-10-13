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
  Blocks             [{"Name": <block id>, "At": [x, y, z]}]: blocks set into the arena
                     (an exit pad), replacing whatever the source had in that cell

"At" is a block cell counted from the prefab's anchor (the cell a party arrives above), the way
the dungeon's EntryOffset counts: an entity stands on the floor of that cell, at its centre.
The entities carry no UUID, so every paste of the prefab stages a fresh fight. Their shape is
the dev test arena's (the encounter entity and the spawn marker entity a runtime paste keeps).
A rerun writes byte-identical files.
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
    comps["Nameplate"]["Text"] = ident
    if name_key == "EncounterManager":
        comps["EncounterManager"]["EncounterId"] = ident
    else:
        comps["SpawnMarkerComponent"]["SpawnMarker"] = ident
    return out


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
    prefab["entities"] = entities
    blocks = prefab.get("blocks", [])
    for block in spec.get("Blocks", []):
        x, y, z = (block["At"][0] + ax, block["At"][1] + ay, block["At"][2] + az)
        blocks = [b for b in blocks if (b["x"], b["y"], b["z"]) != (x, y, z)]
        blocks.append({"x": x, "y": y, "z": z, "name": block["Name"]})
    prefab["blocks"] = blocks
    return (json.dumps(prefab, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


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
            elif out.read_bytes() != data:
                problems.append(f"stale: {spec['Output']}")
            continue
        if out.is_file() and out.read_bytes() == data:
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
