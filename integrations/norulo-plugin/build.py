#!/usr/bin/env python3
"""Build the portable Norulo download without private account bindings."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


FILES = (
    "assets/norulo-logo.png",
    "mcp.json",
    "plugin.json",
    "skills/norulo-connect/SKILL.md",
    "skills/norulo-ledger/SKILL.md",
    "skills/norulo-reports/SKILL.md",
)


def build(package):
    manifest = json.loads((package / "plugin.json").read_text())
    mcp = json.loads((package / "mcp.json").read_text())
    interface = manifest["extensions"]["com.openai"]["interface"]
    if manifest["name"] != "norulo" or interface["displayName"] != "Norulo":
        raise ValueError("Unexpected package identity")
    if "apps" in manifest["extensions"]["com.openai"]:
        raise ValueError("Private App bindings must not be distributed")
    if mcp["mcpServers"]["norulo"]["url"] != "https://mcp.norulo.com/mcp":
        raise ValueError("Unexpected MCP endpoint")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            contents = (package / name).read_bytes()
            if name.endswith((".json", ".md")):
                text = contents.decode("utf-8")
                if re.search(r"[\u3400-\u9fff]", text):
                    raise ValueError(f"Non-English package text: {name}")
                if re.search(r"nrk_[A-Za-z0-9_-]{16,}|BEGIN .*PRIVATE KEY", text):
                    raise ValueError(f"Possible credential in {name}")
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, contents, compresslevel=9)
    return output.getvalue(), manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent / "package"
    data, manifest = build(package)
    digest = hashlib.sha256(data).hexdigest()
    destination = (args.output_dir.resolve() if args.output_dir else
                   Path(__file__).resolve().parent / "downloads")
    metadata = {
        "name": "Norulo",
        "label": "Offline plugin",
        "version": manifest["version"],
        "file": "norulo-plugin.zip",
        "bytes": len(data),
        "sha256": digest,
        "publicDirectoryStatus": "not_submitted",
        "requiresInternetForNoruloTools": True,
    }
    outputs = {
        "norulo-plugin.zip": data,
        "norulo-plugin.zip.sha256": f"{digest}  norulo-plugin.zip\n".encode(),
        "package-info.json": (json.dumps(metadata, indent=2) + "\n").encode(),
    }
    for name, contents in outputs.items():
        path = destination / name
        if args.check:
            if not path.is_file() or path.read_bytes() != contents:
                raise SystemExit(f"Download does not match source: {path}")
        else:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
    print(json.dumps({"checked": args.check, **metadata}))


if __name__ == "__main__":
    main()
