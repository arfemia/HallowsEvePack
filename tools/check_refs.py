#!/usr/bin/env python3
"""Checks every art path the pack's JSON names, before a boot has to find out.

    python tools/check_refs.py                 # check against the pack and the installed game
    python tools/check_refs.py --assets ZIP    # check vanilla paths against this Assets.zip
    python tools/check_refs.py --orphans       # also list the pack's art no JSON names

A string value in any Server/**/*.json that ends in .png, .blockymodel or .blockyanim names a
file under Common/ (an item's Icon, Model and Texture, a block's CustomModel and
CustomModelTexture, a model's attachments and animations). Each must exist in the pack's own
Common/ or in the game's Assets.zip: the engine refuses an asset whose file is missing
("Common Asset '...' doesn't exist!") and that drops the whole pack at boot. The Assets.zip is
--assets, else HYTALE_ASSETS_ZIP, else the install the workspace's family.properties names
(hytaleHome, patchline, game_build, as every family build reads them; the MMO's gradle.properties,
mmo-skills found through the same file, gives a key it lacks); without one, vanilla paths are
reported as unchecked rather than missing.
"""
import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PACK = TOOLS.parent
SUFFIXES = (".png", ".blockymodel", ".blockyanim")
# The server build keys this reads: family.properties carries them under their gradle.properties
# names, and its value wins over the MMO's (R181), as in the MMO's tools/dev-env.ps1.
SERVER_KEYS = ("hytaleHome", "patchline", "game_build")


def read_properties(path):
    """{key: value} from a .properties file's `key=value` lines, `#` comments skipped."""
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def family_root(start):
    """The nearest folder above `start` holding family.properties (the workspace, or a tree under
    worktrees/); None outside a workspace."""
    return next((p for p in start.parents if (p / "family.properties").is_file()), None)


def mmo_skills(start):
    """The MMO repo: <root>/<repo.mmo-skills>, where root is family_root(start); None outside a
    workspace."""
    root = family_root(start)
    if root is None:
        return None
    rel = read_properties(root / "family.properties").get("repo.mmo-skills")
    return root / rel if rel else None


ROOT = family_root(PACK)
MMO = mmo_skills(PACK)


def installed_assets_zip():
    """HYTALE_ASSETS_ZIP, else <hytaleHome>/<patchline>/package/game/<game_build>/Assets.zip, each
    key from the workspace's family.properties, else from the MMO's gradle.properties (as its
    tools/dev-env.ps1 resolves them), else None."""
    override = os.environ.get("HYTALE_ASSETS_ZIP")
    if override:
        return Path(override)
    values = {}
    if MMO is not None and (MMO / "gradle.properties").is_file():
        values.update(read_properties(MMO / "gradle.properties"))
    if ROOT is not None:
        workspace = read_properties(ROOT / "family.properties")
        values.update({key: workspace[key] for key in SERVER_KEYS if workspace.get(key)})
    if not values.get("hytaleHome"):
        return None
    return (Path(values["hytaleHome"]) / values.get("patchline", "release") / "package" / "game"
            / values.get("game_build", "latest") / "Assets.zip")


def strings(value):
    """Every string inside a parsed JSON value, depth first."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def references(pack):
    """{Common/-relative path: sorted pack-relative JSON files naming it}."""
    found = {}
    for path in sorted((pack / "Server").rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for text in strings(data):
            if text.lower().endswith(SUFFIXES):
                found.setdefault(text.replace("\\", "/"), set()).add(path.relative_to(pack).as_posix())
    return {ref: sorted(files) for ref, files in sorted(found.items())}


def check(pack, assets):
    """Returns (missing, unchecked, orphans): missing and unchecked map a path to the files
    naming it; orphans lists the pack's own Common/ art that no JSON names."""
    refs = references(pack)
    vanilla = None
    if assets is not None and assets.is_file():
        with zipfile.ZipFile(assets) as archive:
            vanilla = {name[len("Common/"):].lower() for name in archive.namelist() if name.startswith("Common/")}
    ours = {p.relative_to(pack / "Common").as_posix().lower(): p.relative_to(pack / "Common").as_posix()
            for p in (pack / "Common").rglob("*") if p.is_file() and p.name.lower().endswith(SUFFIXES)}
    missing, unchecked = {}, {}
    for ref, files in refs.items():
        if ref.lower() in ours:
            continue
        if vanilla is None:
            unchecked[ref] = files
        elif ref.lower() not in vanilla:
            missing[ref] = files
    named = {ref.lower() for ref in refs}
    orphans = sorted(path for key, path in ours.items() if key not in named)
    return missing, unchecked, orphans


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, default=PACK, help="the pack root (default: this pack)")
    parser.add_argument("--assets", type=Path, default=None, help="the game Assets.zip for vanilla paths")
    parser.add_argument("--orphans", action="store_true", help="also list the pack's art no JSON names")
    args = parser.parse_args(argv)
    assets = args.assets or installed_assets_zip()
    missing, unchecked, orphans = check(args.pack, assets)
    refs = references(args.pack)
    for ref, files in missing.items():
        print(f"MISSING {ref}  (named by {', '.join(files)})")
    for ref, files in unchecked.items():
        print(f"UNCHECKED {ref}  (no Assets.zip; named by {', '.join(files)})")
    if args.orphans:
        for path in orphans:
            print(f"ORPHAN Common/{path}")
    print(f"{len(refs)} references, {len(missing)} missing, {len(unchecked)} unchecked"
          + (f", {len(orphans)} orphans" if args.orphans else ""))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
