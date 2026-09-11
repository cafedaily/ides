"""Read-only syntax/build-source check for the harness validation runner."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("web_build", ROOT / "web/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
parts = [(name, (ROOT / "web/src" / name).read_text(encoding="utf-8")) for name in builder.JS]
collisions = builder.collisions(parts)
if collisions:
    raise SystemExit(str(collisions))
with tempfile.TemporaryDirectory(prefix="ides-js-check-") as temporary:
    output = Path(temporary) / "application.js"
    output.write_text("\n".join(code for name, code in parts), encoding="utf-8")
    subprocess.run(["node", "--check", str(output)], check=True)
print("Web source syntax and top-level symbols passed")
