"""Reproducible HACS runtime ZIP, no diagnostics or private installation state."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
component = root / "custom_components/camera_cache"
output = root / "release"
output.mkdir(exist_ok=True)
archive = output / "camera_cache.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
    for file in sorted(component.rglob("*")):
        if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc":
            continue
        info = zipfile.ZipInfo(file.relative_to(component).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        zipped.writestr(info, file.read_bytes())
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / "SHA256SUMS.txt").write_text(f"{digest}  camera_cache.zip\n", encoding="utf-8")
print(json.dumps({"version": json.loads((component / "manifest.json").read_text())["version"], "sha256": digest}))
