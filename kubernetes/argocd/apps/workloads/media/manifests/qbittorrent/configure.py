"""Keep qBittorrent's cluster-owned settings and categories in place.

Runs next to qBittorrent in the same pod and talks to it on 127.0.0.1 through
the documented Web API. Every INTERVAL seconds it logs in, compares
preferences.json and categories.json with what qBittorrent reports, and sets
only what differs. Anything in those files snaps back if changed in the UI, the
way ArgoCD selfHeal works for manifests; everything else stays editable there.

After each change it reads the settings back and complains about any key that
didn't stick (a misspelled or retired key fails loudly instead of silently),
once, and then leaves that key alone until the pod restarts.
"""

import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080/api/v2/"
CONF = os.environ.get("CONF_DIR", "/etc/qbittorrent")
INTERVAL = int(os.environ.get("INTERVAL", "300"))


class LoginRefused(Exception):
    pass


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%S"), msg, flush=True)


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, path, form=None):
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        with self.opener.open(urllib.request.Request(BASE + path, data=data), timeout=30) as r:
            return r.read().decode()

    def login(self):
        # 5.3 answers 204 with no body on success and 401 on a wrong password;
        # older versions answer 200 with "Ok." or "Fails.". Either way success
        # is the session cookie: SID before 5.x, QBT_SID_<port> since.
        try:
            body = self.call("auth/login", {
                "username": os.environ["WEBUI_USERNAME"],
                "password": os.environ["WEBUI_PASSWORD"],
            }).strip()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise LoginRefused(f"HTTP {e.code}") from None
            raise
        if body not in ("", "Ok.") or not any(
                c.name == "SID" or c.name.startswith("QBT_SID") for c in self.jar):
            raise LoginRefused(body or "no session cookie")


def apply(client, prefs, categories, ignored):
    current = json.loads(client.call("app/preferences"))
    unknown = sorted(k for k in prefs if k not in current and k not in ignored)
    if unknown:
        log(f"WARNING: qBittorrent has no preference named {', '.join(unknown)}; ignoring")
        ignored.update(unknown)
    diff = {k: v for k, v in prefs.items()
            if k in current and k not in ignored and current[k] != v}
    if diff:
        client.call("app/setPreferences", {"json": json.dumps(diff)})
        after = json.loads(client.call("app/preferences"))
        stuck = sorted(k for k, v in diff.items() if after.get(k) != v)
        log("set " + ", ".join(sorted(diff)))
        if stuck:
            log("WARNING: qBittorrent did not accept " + ", ".join(
                f"{k} (wanted {diff[k]!r}, has {after.get(k)!r})" for k in stuck) + "; ignoring")
            ignored.update(stuck)

    have = json.loads(client.call("torrents/categories"))
    for name, path in categories.items():
        if name not in have:
            client.call("torrents/createCategory", {"category": name, "savePath": path})
            log(f"created category {name} -> {path}")
        elif have[name].get("savePath") != path:
            client.call("torrents/editCategory", {"category": name, "savePath": path})
            log(f"moved category {name} -> {path}")


def main():
    with open(os.path.join(CONF, "preferences.json"), encoding="utf-8") as fh:
        prefs = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    with open(os.path.join(CONF, "categories.json"), encoding="utf-8") as fh:
        categories = json.load(fh)

    client, first, ignored = None, True, set()
    while True:
        try:
            if client is None:
                client = Client()
                client.login()
            apply(client, prefs, categories, ignored)
            if first:
                log(f"in sync ({len(prefs)} preferences, {len(categories)} categories); "
                    f"checking every {INTERVAL}s")
                first = False
            delay = INTERVAL
        except LoginRefused as e:
            # Repeated failures get 127.0.0.1 banned, so back off hard.
            log(f"ERROR: login refused ({e}); is the qbittorrent secret out of step "
                "with qBittorrent.conf? retrying in 10 min")
            client, delay = None, 600
        except urllib.error.HTTPError as e:
            # 403 means the session expired (or qBittorrent restarted): log in again.
            log(f"HTTP {e.code} from {e.url}; retrying in 30s")
            client, delay = None, 30
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if not first:
                log(f"qBittorrent not reachable ({e}); retrying in 10s")
            client, delay = None, 10
        time.sleep(delay)


if __name__ == "__main__":
    main()
