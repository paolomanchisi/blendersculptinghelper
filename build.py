# SPDX-License-Identifier: GPL-3.0-or-later
"""Package sculpt_helper/ as an installable Blender extension zip."""

import pathlib
import tomllib
import zipfile

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "sculpt_helper"

manifest = tomllib.loads((SRC / "blender_manifest.toml").read_text())
out = ROOT / "dist" / f"{manifest['id']}-{manifest['version']}.zip"
out.parent.mkdir(exist_ok=True)

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(SRC.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            zf.write(path, path.relative_to(SRC))
    zf.write(ROOT / "LICENSE", "LICENSE")

print(out)
