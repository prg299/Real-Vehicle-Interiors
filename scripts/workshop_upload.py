"""Real Vehicle Interiors: prepare/upload with SteamCMD, preserving an existing item's visibility.

    python scripts/workshop_upload.py            prepare only (stage + upload configuration), no login
    python scripts/workshop_upload.py --upload   prepare, then log in interactively and upload

The stage is project-local (build/rv/workshop/RealVehicleInteriors: Contents/mods/RealVehicleInteriors and
the selected zombie-attack cover GIF), so it never shadows anything in the player's own Zomboid folder. The description and change notes
come from release/workshop and keep real line breaks (games/project-zomboid/tools/steam_workshop.py: SteamCMD shows
an escaped backslash-n literally). The account name is asked here; SteamCMD itself asks for the password and the
Steam Guard code, typed by the user: no credential goes into arguments, files or logs. The Workshop ID Steam assigns
is kept in release/workshop/steamcmd-identity.json, so later runs update the same item.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
from steam_workshop import make_vdf, reconcile_ids, vdf_field, quote  # noqa: E402

MOD_ID = "RealVehicleInteriors"
TITLE = "Real Vehicle Interiors [B42/MP/BETA]"
TAGS = "Build 42;Vehicles;Interface;Multiplayer"
PACKAGE = ROOT / "build/rv/package" / MOD_ID
RELEASE = ROOT / "release/workshop"
DEFAULT_PREVIEW = RELEASE / "preview.png"
STAGE = ROOT / "build/rv/workshop" / MOD_ID
VDF = RELEASE / "steamcmd-item.vdf"
IDENTITY = RELEASE / "steamcmd-identity.json"
STEAMCMD = Path(os.environ.get("RVI_STEAMCMD", str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GameMods/SteamCMD/steamcmd.exe")))
FIELDS = ["appid", "publishedfileid", "contentfolder", "previewfile", "visibility", "title", "description", "changenote",
          "tags"]
TEXT_LIMIT = 4000        # bytes of description or change notes in the build file (see prepare)


def plain_quotes(text):
    """SteamCMD reads the build file without escapes: a double quote always ends a value, and the backslash that
    games/project-zomboid/tools/steam_workshop.quote puts before it stays as text. "Use nearby furniture" cut the 2.0.0
    description short there, and a second quoted phrase in the 2.0.1 change notes broke the file ("got } in key",
    exit code 9, nothing uploaded; 2026-10-04/05). Double quotes become typographic ones."""
    out, opening = [], True
    for ch in text:
        if ch == '"':
            out.append("“" if opening else "”")
            opening = not opening
        else:
            out.append(ch)
    return "".join(out)


def read_as_steamcmd(text):
    """The top-level keys and values of a build file as SteamCMD sees them: a quoted value ends at the next double
    quote, a backslash is plain text. {key: value}, with the tags block as a dict."""
    pos, n, tokens = 0, len(text), []
    while pos < n:
        ch = text[pos]
        if ch in " \t\r\n":
            pos += 1
        elif ch in "{}":
            tokens.append(ch)
            pos += 1
        elif ch == '"':
            end = text.find('"', pos + 1)
            if end < 0:
                raise ValueError("unterminated value in the build file")
            tokens.append(("s", text[pos + 1:end]))
            pos = end + 1
        else:
            end = pos
            while end < n and text[end] not in ' \t\r\n"{}':
                end += 1
            tokens.append(("s", text[pos:end]))
            pos = end

    def block(i):
        out = {}
        while i < len(tokens):
            if tokens[i] == "}":
                return out, i + 1
            if tokens[i] == "{" or i + 1 >= len(tokens):
                raise ValueError("the build file does not read as key and value pairs")
            key, value = tokens[i][1], tokens[i + 1]
            if value == "{":
                out[key], i = block(i + 2)
            elif value == "}":
                raise ValueError(f"key {key[:40]!r} has no value")
            else:
                out[key] = value[1]
                i += 2
        raise ValueError("the build file ends inside a block")

    if len(tokens) < 2 or tokens[0] != ("s", "workshopitem") or tokens[1] != "{":
        raise ValueError("the build file does not start with workshopitem {")
    fields, end = block(2)
    if end != len(tokens):
        raise ValueError("the build file has something after its last }")
    return fields


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}


def saved_id():
    saved = json.loads(IDENTITY.read_text()).get("workshopId") if IDENTITY.exists() else None
    return reconcile_ids(vdf_field(VDF, "publishedfileid"), saved)


def keep_id(published_id):
    if published_id:
        IDENTITY.write_text(json.dumps({"workshopId": published_id, "appid": "108600", "modId": MOD_ID,
                                        "note": "Kept so later uploads update this item."}, indent=2))


def prepare(metadata_only=False, preview=None, preserve_page=False):
    if preserve_page and metadata_only:
        raise ValueError("Preserving page metadata cannot be combined with a metadata-only update")
    jar = PACKAGE / "42.21/media/java" / (MOD_ID + ".jar")
    if not jar.is_file():
        raise FileNotFoundError("Build first: scripts/build.ps1")
    if not STEAMCMD.is_file():
        raise FileNotFoundError("SteamCMD missing: install SteamCMD and set RVI_STEAMCMD to steamcmd.exe")
    if not STAGE.resolve().is_relative_to((ROOT / "build/rv/workshop").resolve()):
        raise ValueError("Workshop stage is outside the project's build directory")
    preview = Path(preview).resolve() if preview else DEFAULT_PREVIEW
    if not metadata_only and not preview.is_file():
        raise FileNotFoundError(f"Workshop cover missing: {preview}")
    if STAGE.exists() and not metadata_only:
        shutil.rmtree(STAGE)
    if not metadata_only:
        (STAGE / "Contents/mods").mkdir(parents=True)
        shutil.copytree(PACKAGE, STAGE / "Contents/mods" / MOD_ID)
        shutil.copyfile(preview, STAGE / preview.name)
        assert hashes(STAGE / "Contents/mods" / MOD_ID) == hashes(PACKAGE), "stage differs from the build"
    description = plain_quotes((RELEASE / "description.txt").read_text(encoding="utf-8").strip())
    changenote = plain_quotes((RELEASE / "changenote.txt").read_text(encoding="utf-8").strip())
    for name, text in (("description", description), ("change notes", changenote)):
        if "\\" in text:
            # (steam_workshop.quote doubles it and SteamCMD shows both; a backslash-n would show as text)
            raise ValueError(name + " contains a backslash: SteamCMD would show it doubled")
        # Valve's public KeyValues reader keeps one quoted value in a 4096-byte buffer; SteamCMD's own limit is not
        # known (the 2.0.0 upload only ever sent 2.6 KB of description), so a text stays below it, line breaks
        # counted as written in the file (two bytes each).
        size = len(text.encode("utf-8")) + text.count("\n")
        if size > TEXT_LIMIT:
            raise ValueError(f"{name} is {size} bytes as written for SteamCMD; keep it under {TEXT_LIMIT} "
                             "(a longer page text is edited on the Workshop page itself)")
    published_id = saved_id()
    visibility = "preserve" if published_id else "unlisted"
    info = {"title": plain_quotes(TITLE), "description": description, "tags": TAGS, "visibility": visibility}
    configuration = RELEASE / "steamcmd-page.vdf" if metadata_only else VDF
    fields = FIELDS if visibility == "unlisted" else [key for key in FIELDS if key != "visibility"]
    expected = (("title", info["title"]), ("description", description), ("changenote", changenote))
    if metadata_only:
        if not published_id: raise ValueError("Metadata updates require an existing item")
        page = {"appid": "108600", "publishedfileid": published_id, "title": info["title"], "description": description}
        fields = list(page)
        expected = expected[:2]
        configuration.write_text('"workshopitem"\n{\n' + '\n'.join('    ' + quote(k) + ' ' + quote(v) for k, v in page.items()) + '\n}\n', encoding="utf-8")
    else:
        configuration.write_text(make_vdf("108600", info, STAGE / "Contents", STAGE / preview.name, published_id, changenote), encoding="utf-8")
        if preserve_page:
            if not published_id:
                raise ValueError("Preserving page metadata requires an existing item")
            fields = [key for key in fields if key not in ("title", "description", "tags")]
            values = read_as_steamcmd(configuration.read_text(encoding="utf-8"))
            configuration.write_text('"workshopitem"\n{\n' + '\n'.join(
                '    ' + quote(key) + ' ' + quote(values[key]) for key in fields) + '\n}\n', encoding="utf-8")
            expected = (("changenote", changenote),)
    # what SteamCMD will read: every field once, and the texts whole
    seen = read_as_steamcmd(configuration.read_text(encoding="utf-8"))
    if list(seen) != fields:
        raise ValueError("SteamCMD would read these fields instead: " + ", ".join(k[:30] for k in seen))
    for key, want in expected:
        if seen[key].replace("\r\n", "\n") != want.replace("\r\n", "\n"):
            raise ValueError(f"SteamCMD would read the {key} differently from release/workshop")
    record = {
        "preparedUtc": datetime.now(timezone.utc).isoformat(), "stage": str(STAGE), "configuration": str(configuration),
        "payloadFiles": 0 if metadata_only else len(hashes(PACKAGE)), "jarSha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "visibility": visibility, "workshopId": published_id, "credentialsStoredInProject": False, "metadataOnly": metadata_only,
        "pageMetadata": "preserve" if preserve_page else "update",
    }
    if not metadata_only:
        record.update(previewFile=str(preview), previewSha256=hashlib.sha256(preview.read_bytes()).hexdigest())
    print(f"Ready: {TITLE}, {record['payloadFiles']} files; visibility: {visibility}.")
    print("Workshop item: " + (published_id or "new item (Steam assigns its ID on upload)"))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true", help="log in interactively and upload")
    parser.add_argument("--metadata-only", action="store_true", help="update only the existing title/description")
    parser.add_argument("--preview", type=Path, help="primary preview override (defaults to the blurred zombie-attack GIF)")
    parser.add_argument("--preserve-page", action="store_true", help="upload content and cover without changing title, description, tags, gallery, dependencies or visibility")
    args = parser.parse_args()
    record = prepare(args.metadata_only, args.preview, args.preserve_page)
    if not args.upload:
        return
    print("\nThis updates Real Vehicle Interiors; an existing item's visibility is preserved.")
    print("Type your password and Steam Guard code only when SteamCMD asks for them.")
    username = input("Steam account name (blank cancels): ").strip()
    if not username:
        print("Cancelled before login.")
        return
    if not username.isascii() or any(c.isspace() or c in "\"'\\/;+" for c in username):
        raise ValueError("Enter the Steam login account name, not a profile display name.")
    configuration = Path(record["configuration"])
    process = subprocess.run([str(STEAMCMD), "+login", username, "+workshop_build_item", str(configuration), "+quit"],
                             cwd=STEAMCMD.parent)
    published_id = reconcile_ids(vdf_field(configuration, "publishedfileid"), record["workshopId"])
    keep_id(published_id)
    record.update({"uploadAttempted": True, "steamcmdExitCode": process.returncode, "workshopId": published_id})
    receipt = "steamcmd-page-last-attempt.json" if args.metadata_only else "steamcmd-last-attempt.json"
    (RELEASE / receipt).write_text(json.dumps(record, indent=2))
    if published_id:
        print("\nWorkshop item: https://steamcommunity.com/sharedfiles/filedetails/?id=" + published_id)
        print("Check the item page and any Workshop agreement to accept.")
    else:
        print("No Workshop ID came back. Check the SteamCMD messages above.")
    if process.returncode != 0 or not published_id:
        raise SystemExit(process.returncode or 1)


if __name__ == "__main__":
    main()
