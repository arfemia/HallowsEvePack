# Common/

- The art here is generated: change `tools/derive_art.py` and rerun it (`python -I tools/derive_art.py`; `--check` compares), never hand-edit a file it writes. It reads byte copies of the vanilla files it needs from `tools/seed/vanilla/`, vendored locally and gitignored (refresh with `--vendor <Assets.zip>`), and `python -I tools/check_refs.py` checks every art path the pack's JSON names.
