"""Write the Web UI login (and two first-boot basics) into qBittorrent.conf.

Runs as an init container before qBittorrent starts, because the API can't be
used to set the first password: since 4.6.1 a fresh qBittorrent makes up a
random one and only prints it to the log. Everything else is set through the
API by configure.py.

Only the lines below are touched. The rest of the file is qBittorrent's own and
is kept byte for byte. The hash is rewritten only when it doesn't already match
the secret, so a restart doesn't churn the file.
"""

import base64
import hashlib
import hmac
import os
import secrets

CONF = "/config/qBittorrent/qBittorrent.conf"
USER = os.environ["WEBUI_USERNAME"]
PASSWORD = os.environ["WEBUI_PASSWORD"].encode()


def pbkdf2(salt: bytes) -> bytes:
    # qBittorrent's format: PBKDF2-HMAC-SHA512, 100000 rounds, 64-byte key.
    return hashlib.pbkdf2_hmac("sha512", PASSWORD, salt, 100_000, 64)


def matches(value: str) -> bool:
    try:
        inner = value.strip('"').removeprefix("@ByteArray(").removesuffix(")")
        salt_b64, key_b64 = inner.split(":")
        return hmac.compare_digest(pbkdf2(base64.b64decode(salt_b64)), base64.b64decode(key_b64))
    except ValueError:
        return False


def read_sections(path):
    """[(header or None, [lines])], in file order."""
    sections = [(None, [])]
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                if line.startswith("[") and line.endswith("]"):
                    sections.append((line, []))
                else:
                    sections[-1][1].append(line)
    return sections


def get(sections, header, key):
    for h, lines in sections:
        if h == header:
            for line in lines:
                if line.startswith(key + "="):
                    return line[len(key) + 1:]
    return None


def put(sections, header, key, value):
    for h, lines in sections:
        if h == header:
            for i, line in enumerate(lines):
                if line.startswith(key + "="):
                    lines[i] = f"{key}={value}"
                    return
            # Insert after the last non-blank line, keeping the blank separator.
            end = len(lines)
            while end and not lines[end - 1].strip():
                end -= 1
            lines.insert(end, f"{key}={value}")
            return
    last = sections[-1][1]
    if last and last[-1].strip():
        last.append("")
    sections.append((header, [f"{key}={value}", ""]))


sections = read_sections(CONF)
changed = []

wanted = {
    # Accepting the legal notice is what --confirm-legal-notice does on the command line.
    ("[LegalNotice]", "Accepted"): "true",
    # So nothing lands inside the container before configure.py has run.
    ("[BitTorrent]", "Session\\DefaultSavePath"): "/media/torrents",
    ("[Preferences]", "WebUI\\Username"): USER,
}
for (header, key), value in wanted.items():
    if get(sections, header, key) != value:
        put(sections, header, key, value)
        changed.append(key)

current = get(sections, "[Preferences]", "WebUI\\Password_PBKDF2")
if current is None or not matches(current):
    salt = secrets.token_bytes(16)
    value = base64.b64encode(salt).decode() + ":" + base64.b64encode(pbkdf2(salt)).decode()
    put(sections, "[Preferences]", "WebUI\\Password_PBKDF2", f'"@ByteArray({value})"')
    changed.append("WebUI\\Password_PBKDF2")

if changed:
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    text = "\n".join(line for h, lines in sections for line in ([h] if h else []) + lines)
    tmp = CONF + ".seed-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text.strip("\n") + "\n")
    os.replace(tmp, CONF)
    print("updated: " + ", ".join(changed))
else:
    print("qBittorrent.conf already up to date")
