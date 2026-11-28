"""arr-config: keep Radarr's, Sonarr's and Prowlarr's settings in git.

Every INTERVAL seconds it applies desired.json through each app's own API: the
web UI login, root folders, config sections (media management, naming), and
providers (the qBittorrent download client, the Jellyfin connection, Prowlarr's
links to Radarr and Sonarr). Only the keys listed are compared and set, and
only when they differ, so everything else stays editable in the UI and a
quiet log means nothing drifted. Secret fields can't be read back (the API
masks them), so they're sent on create and whenever something else about that
provider has drifted.

If an app is down or an upgrade renames a field, it logs and retries; the app
keeps the settings it already has.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

CONF = os.environ.get("CONF_DIR", "/etc/arr-config")
INTERVAL = int(os.environ.get("INTERVAL", "600"))


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%S"), msg, flush=True)


SECRETS = os.environ.get("SECRETS_DIR", "/etc/arr-config-secrets")


def secret(name):
    """An environment variable, or else a file of that name in SECRETS_DIR. Files
    come from secrets mounted as volumes, which the kubelet refreshes in place,
    so a key created later (Jellyfin's) is picked up without a restart."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(os.path.join(SECRETS, name), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def expand(value):
    """"$NAME" means secret("NAME"), so secrets stay out of git."""
    if isinstance(value, str) and value.startswith("$"):
        return secret(value[1:])
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v) for v in value]
    return value


# --------------------------------------------------------------------- client

class Arr:
    def __init__(self, name, url, api, key):
        self.name, self.base, self.key = name, url.rstrip("/") + api + "/", key

    def call(self, method, path, body=None, **query):
        url = self.base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "X-Api-Key": self.key, "Content-Type": "application/json", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
        return json.loads(raw) if raw else None

    def get(self, path, **q):
        return self.call("GET", path, **q)

    def post(self, path, body, **q):
        return self.call("POST", path, body, **q)

    def put(self, path, body, **q):
        return self.call("PUT", path, body, **q)


# -------------------------------------------------------------------- settings

def field_map(item):
    return {f["name"]: f for f in item.get("fields", [])}


def ensure_provider(arr, kind, want):
    """Create or correct one download client / notification / application."""
    want = expand(want)
    if any(v == "" for v in want.get("fields", {}).values()) and want.get("skip_if_unset"):
        return  # e.g. the Jellyfin API key isn't in the secret yet
    items = arr.get(kind)
    cur = next((i for i in items if i["name"] == want["name"]), None)
    if cur is None:
        schema = next((s for s in arr.get(kind + "/schema")
                       if s["implementation"] == want["implementation"]), None)
        if schema is None:
            log(f"WARNING {arr.name}: no {kind} implementation {want['implementation']}")
            return
        body = dict(schema, name=want["name"], **want.get("props", {}))
        fields = field_map(body)
        for k, v in want.get("fields", {}).items():
            if k not in fields:
                log(f"WARNING {arr.name}: {want['name']} has no field {k}; skipped")
                continue
            fields[k]["value"] = v
        arr.post(kind, body, forceSave="true")
        log(f"{arr.name}: created {kind} {want['name']}")
        return
    fields = field_map(cur)
    drift = [k for k, v in want.get("props", {}).items() if cur.get(k) != v]
    for k, v in want.get("fields", {}).items():
        f = fields.get(k)
        if f is None:
            continue
        if f.get("privacy") in ("password", "apiKey"):
            continue  # masked on read; sent below if anything else changed
        if f.get("value") != v:
            drift.append(k)
    if not drift:
        return
    body = dict(cur, **want.get("props", {}))
    fields = field_map(body)
    for k, v in want.get("fields", {}).items():
        if k in fields:
            fields[k]["value"] = v
    arr.put(f"{kind}/{cur['id']}", body, forceSave="true")
    log(f"{arr.name}: updated {kind} {want['name']} ({', '.join(drift)})")


def ensure_settings(arr, want):
    # Web UI login. The API can't tell us the password, so only the username is
    # checked; set it again by changing the username or clearing it in the UI.
    host = arr.get("config/host")
    user = os.environ.get("ARR_UI_USERNAME", "")
    if user and host.get("username") != user:
        host.update(username=user, password=os.environ["ARR_UI_PASSWORD"],
                    passwordConfirmation=os.environ["ARR_UI_PASSWORD"],
                    authenticationMethod="forms", authenticationRequired="enabled")
        arr.put(f"config/host/{host['id']}", host)
        log(f"{arr.name}: set the web UI login")

    if "root_folders" in want:
        have = {r["path"].rstrip("/") for r in arr.get("rootfolder")}
        for path in want["root_folders"]:
            if path.rstrip("/") not in have:
                arr.post("rootfolder", {"path": path})
                log(f"{arr.name}: added root folder {path}")

    for section, values in want.get("config", {}).items():
        if section.startswith("_"):
            continue  # a note
        cur = arr.get(section)
        drift = sorted(k for k, v in values.items() if cur.get(k) != v)
        unknown = [k for k in values if k not in cur]
        if unknown:
            log(f"WARNING {arr.name}: {section} has no {', '.join(unknown)}")
        drift = [k for k in drift if k not in unknown]
        if drift:
            arr.put(f"{section}/{cur['id']}", dict(cur, **{k: values[k] for k in drift}))
            log(f"{arr.name}: set {section} {', '.join(drift)}")

    for p in want.get("providers", []):
        ensure_provider(arr, p["kind"], {k: v for k, v in p.items() if not k.startswith("_")})


def main():
    with open(os.path.join(CONF, "desired.json"), encoding="utf-8") as fh:
        desired = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    arrs = {name: Arr(name, d["url"], d["api"], secret(d["api_key_env"]))
            for name, d in desired.items()}
    while True:
        failed = False
        for name, arr in arrs.items():
            try:
                ensure_settings(arr, desired[name])
            except Exception as e:  # one app being down mustn't stop the others
                detail = e.read()[:300] if isinstance(e, urllib.error.HTTPError) else ""
                log(f"{name}: settings not applied ({type(e).__name__}: {e} {detail!r}); retrying")
                failed = True
        time.sleep(60 if failed else INTERVAL)


if __name__ == "__main__":
    main()
