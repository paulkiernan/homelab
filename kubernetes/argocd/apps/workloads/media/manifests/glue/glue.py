"""media-glue: keep the arrs' settings in git, and add pasted torrents' titles.

Two loops in one process, both stateless (state lives in the apps themselves):

1. Settings, every CONFIG_INTERVAL seconds. For Radarr, Sonarr and Prowlarr it
   applies desired.json through their APIs: the web UI login, root folders,
   config sections (media management, naming), and providers (the qBittorrent
   download client, the Jellyfin connection, Prowlarr's links to Radarr and
   Sonarr). Only the keys listed are compared and set, so everything else stays
   editable in the UI. Secret fields can't be read back (the API masks them),
   so they're sent on create and whenever something else about that provider
   has drifted.

2. Pasted torrents, every POLL_INTERVAL seconds. Radarr and Sonarr only import
   a download whose movie or show is already in their library. When you paste
   a magnet into qBittorrent with category "movies" or "tv", that's usually not
   the case, so this asks the arr to parse the torrent's name, looks the title
   up, and adds it (no search, only the episodes in the torrent monitored).
   Then the arr's own completed-download handling copies it into the library.
   Each torrent gets one qBittorrent tag recording the outcome:
     glue-added    added the movie or show
     glue-known    it was already in the library (or the arr grabbed it)
     needs-import  couldn't match it confidently; use Wanted > Manual Import
                   (Radarr) or Activity > Queue (Sonarr) to finish it by hand
   plus tmdb-<id> / tvdb-<id> naming the title. If the arr then won't import the
   finished download by itself (it can't parse a name like "Sintel"; the queue
   says importBlocked), this imports it through the arr's manual-import API,
   copying, and tags it glue-imported.
"""

import http.cookiejar
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

CONF = os.environ.get("CONF_DIR", "/etc/media-glue")
CONFIG_INTERVAL = int(os.environ.get("CONFIG_INTERVAL", "600"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
QBT = os.environ.get("QBT_URL", "http://qbittorrent.media.svc.cluster.local:8080")
TAGS = ("glue-added", "glue-known", "needs-import")  # outcome of the first look


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%S"), msg, flush=True)


SECRETS = os.environ.get("SECRETS_DIR", "/etc/media-glue-secrets")


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


def norm(title):
    """Compare titles on letters and digits only: 'Shōgun' == 'Shogun', '&' == 'and'."""
    t = unicodedata.normalize("NFKD", title or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower().replace("&", "and"))


YEAR = re.compile(r"(?<!\d)(19\d\d|20\d\d)(?!\d)")
JUNK = re.compile(r"(?i)\b(\d{3,4}p|4k|uhd|bluray|blu-ray|bdrip|brrip|web(-?dl|rip)?|hdtv|dvdrip|"
                  r"remux|x26[45]|h\.?26[45]|hevc|xvid|aac|ac3|dts|proper|repack)\b")


def guess_title(name):
    """Fallback for names the arr can't parse, e.g. 'Big Buck Bunny' with no year:
    drop the extension, bracketed bits and anything from the first quality tag on."""
    base = re.sub(r"(?i)\.(mkv|mp4|avi|m4v|ts)$", "", name)
    paren = re.search(r"[\[(]((?:19|20)\d\d)[\])]", base)  # "Arrival (2016)"
    base = re.sub(r"[\[(].*?[\])]", " ", base)
    base = re.sub(r"[._]+", " ", base)
    m = JUNK.search(base)
    if m:
        base = base[:m.start()]
    if paren:  # the year was in brackets; any bare number left is part of the title
        title, year = base, int(paren.group(1))
    else:      # the last year-like number, never one the title starts with ("2001 ...")
        ys = [y for y in YEAR.finditer(base) if base[:y.start()].strip()]
        title, year = (base[:ys[-1].start()], int(ys[-1].group(1))) if ys else (base, 0)
    return " ".join(title.split()), year


# --------------------------------------------------------------------- clients

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


class Qbt:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.logged_in = False

    def call(self, path, form=None, **query):
        if not self.logged_in:
            self._login()
        url = QBT + "/api/v2/" + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        try:
            with self.opener.open(urllib.request.Request(url, data=data), timeout=30) as r:
                raw = r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 403:  # session expired
                self.logged_in = False
            raise
        return json.loads(raw) if raw.startswith(("[", "{")) else raw

    def _login(self):
        # qBittorrent 5.3: 204 + QBT_SID_<port> cookie on success, 401 otherwise.
        form = urllib.parse.urlencode({"username": os.environ["QBT_USERNAME"],
                                       "password": os.environ["QBT_PASSWORD"]}).encode()
        with self.opener.open(urllib.request.Request(QBT + "/api/v2/auth/login", data=form),
                              timeout=30) as r:
            r.read()
        if not any(c.name == "SID" or c.name.startswith("QBT_SID") for c in self.jar):
            raise RuntimeError("qBittorrent login gave no session cookie")
        self.logged_in = True


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


# ------------------------------------------------------------- pasted torrents

def profile_id(arr, name):
    for p in arr.get("qualityprofile"):
        if p["name"] == name:
            return p["id"]
    raise RuntimeError(f"{arr.name} has no quality profile {name!r}")


def pick(candidates, titles, year, title_keys):
    """The one lookup result whose title matches exactly (and year, if known).
    A result's own title may carry its year, e.g. 'Doctor Who (2005)'."""
    want = {norm(t) for t in titles if t}

    def names(c):
        for k in title_keys:
            v = c.get(k) or ""
            yield v
            yield re.sub(r"\s*\(\d{4}\)$", "", v)
        for a in c.get("alternateTitles", []):
            yield a.get("title")

    hits = [c for c in candidates if any(norm(n) in want for n in names(c))]
    if year:
        exact = [c for c in hits if c.get("year") == year]
        hits = exact or [c for c in hits if abs((c.get("year") or 0) - year) <= 1]
    return hits[0] if len(hits) == 1 else None


def add_movie(radarr, name, want):
    """-> (outcome tag, what happened, id tag or None)"""
    parsed = radarr.get("parse", title=name)
    if parsed.get("movie"):
        m = parsed["movie"]
        return "glue-known", m["title"], f"tmdb-{m['tmdbId']}"
    info = parsed.get("parsedMovieInfo") or {}
    title = info.get("primaryMovieTitle") or info.get("movieTitle") or \
        (info.get("movieTitles") or [None])[0]
    year = info.get("year") or 0
    if not title:
        title, year = guess_title(name)
        if not title:
            return "needs-import", "couldn't make a title out of the name", None
    found = radarr.get("movie/lookup", term=f"{title} {year}" if year else title)
    movie = pick(found, [title], year, ("title", "originalTitle"))
    if movie is None:
        return "needs-import", f"no single match for {title!r} ({year or 'no year'})", None
    idtag = f"tmdb-{movie['tmdbId']}"
    if movie.get("id"):
        return "glue-known", movie["title"], idtag
    radarr.post("movie", dict(movie, qualityProfileId=profile_id(radarr, want["quality_profile"]),
                              rootFolderPath=want["root_folders"][0], monitored=True,
                              minimumAvailability="released",
                              addOptions={"searchForMovie": False}))
    return "glue-added", f"{movie['title']} ({movie.get('year')})", idtag


def add_series(sonarr, name, want):
    """-> (outcome tag, what happened, id tag or None)"""
    parsed = sonarr.get("parse", title=name)
    series = parsed.get("series")
    tag = "glue-known"
    if not series:
        info = parsed.get("parsedEpisodeInfo") or {}
        tinfo = info.get("seriesTitleInfo") or {}
        # "Shogun.2024.S01E01": title "Shogun 2024", titleWithoutYear "Shogun", year 2024
        title = tinfo.get("titleWithoutYear") or tinfo.get("title") or info.get("seriesTitle")
        year = tinfo.get("year") or 0
        if not title:
            return "needs-import", "Sonarr couldn't parse a series", None
        show = pick(sonarr.get("series/lookup", term=title), [title, info.get("seriesTitle")],
                    year, ("title", "sortTitle"))
        if show is None:
            return "needs-import", f"no single match for {title!r}", None
        if not show.get("id"):
            # monitor "none", then monitor just the episodes in this torrent, so
            # adding a show never makes Sonarr go after the rest of it.
            sonarr.post("series", dict(show, qualityProfileId=profile_id(sonarr, want["quality_profile"]),
                                       rootFolderPath=want["root_folders"][0], seasonFolder=True,
                                       monitored=True, addOptions={
                                           "monitor": "none", "searchForMissingEpisodes": False,
                                           "searchForCutoffUnmetEpisodes": False}))
            tag = "glue-added"
        parsed = sonarr.get("parse", title=name)
        series = parsed.get("series") or show
    ids = [e["id"] for e in parsed.get("episodes") or [] if not e.get("monitored")]
    if ids:
        sonarr.put("episode/monitor", {"episodeIds": ids, "monitored": True})
    return tag, f"{series['title']} ({len(parsed.get('episodes') or [])} episodes)", \
        f"tvdb-{series['tvdbId']}"


PARSE_REJECTIONS = {"Unable to parse file"}


def guess_quality(arr, owner, filename):
    """The arr couldn't parse the file name, so it has no quality for it. Parse
    the name again with the title and year in front, which the parser does
    understand; quality tags in the name (1080p, WEB-DL) still count, and a bare
    name comes back as 'Unknown'."""
    p = arr.get("parse", title=f"{owner['title']} {owner.get('year') or ''} {filename}")
    info = p.get("parsedMovieInfo") or p.get("parsedEpisodeInfo") or {}
    unknown = {"quality": {"id": 0, "name": "Unknown"},
               "revision": {"version": 1, "real": 0, "isRepack": False}}
    return info.get("quality") or unknown, info.get("languages") or [{"id": 0, "name": "Unknown"}]


def tagset(t):
    return {x.strip() for x in (t.get("tags") or "").split(",") if x.strip()}


def finish_blocked(qbt, arr, app, torrents):
    """Import what the arr refuses to on its own.

    Radarr/Sonarr match a finished download to a title by parsing its name. A
    name like "Sintel" (no year) can't be parsed, so even with the movie in the
    library the queue says "Unable to parse download" (importBlocked). For our
    own torrents we know the title (the tmdb-/tvdb- tag), so do what the UI's
    Manual Import button does: list the files the arr would accept and import
    them, copying.
    """
    unknown = "includeUnknownMovieItems" if app == "radarr" else "includeUnknownSeriesItems"
    queue = arr.get("queue", pageSize=200, **{unknown: "true"})
    for rec in queue.get("records", []):
        if rec.get("trackedDownloadState") != "importBlocked":
            continue
        t = torrents.get((rec.get("downloadId") or "").lower())
        if t is None:
            continue
        tags = tagset(t)
        idtag = next((x for x in tags if x.startswith(("tmdb-", "tvdb-"))), None)
        if idtag is None or tags & {"glue-imported", "needs-import"}:
            continue
        ext_id = int(idtag.split("-", 1)[1])
        if app == "radarr":
            owner = (arr.get("movie", tmdbId=ext_id) or [None])[0]
            key = "movieId"
        else:
            owner = (arr.get("series", tvdbId=ext_id) or [None])[0]
            key = "seriesId"
        if owner is None:
            continue
        items = arr.get("manualimport", folder=rec["outputPath"], downloadId=rec["downloadId"],
                        filterExistingFiles="true", **{key: owner["id"]})
        # The only rejection we override is the arr not being able to parse the
        # file name; we know the title. Samples, non-upgrades, duplicates and
        # the rest still stop the import.
        files = [i for i in items
                 if all(r.get("reason") in PARSE_REJECTIONS for r in i.get("rejections", []))]
        if app == "radarr":
            files = sorted(files, key=lambda i: i.get("size", 0), reverse=True)[:1]  # one movie file
        else:
            files = [i for i in files if i.get("episodes")]  # needs episode numbers to place it
        for i in files:
            if not i.get("quality"):
                i["quality"], i["languages"] = guess_quality(arr, owner, i["name"])
        if not files:
            why = sorted({r.get("reason", "?") for i in items for r in i.get("rejections", [])})
            qbt.call("torrents/addTags", {"hashes": t["hash"], "tags": "needs-import"})
            log(f"{app}: {t['name']!r} -> needs-import: nothing importable ({'; '.join(why) or 'no files'})")
            continue
        body = [{"path": i["path"], key: owner["id"], "quality": i["quality"],
                 "languages": i.get("languages", []), "releaseGroup": i.get("releaseGroup"),
                 "downloadId": rec["downloadId"], "indexerFlags": i.get("indexerFlags", 0),
                 **({"episodeIds": [e["id"] for e in i["episodes"]],
                     "releaseType": i.get("releaseType", "unknown")} if app == "sonarr" else {})}
                for i in files]
        arr.post("command", {"name": "ManualImport", "importMode": "copy", "files": body})
        qbt.call("torrents/addTags", {"hashes": t["hash"], "tags": "glue-imported"})
        log(f"{app}: {t['name']!r} -> glue-imported: {len(body)} file(s) into {owner['title']}")


def handle_pasted(qbt, arrs, desired):
    routes = {"movies": ("radarr", add_movie), "tv": ("sonarr", add_series)}
    for category, (app, add) in routes.items():
        if app not in arrs:
            continue
        torrents = {}
        for t in qbt.call("torrents/info", category=category):
            torrents[t["hash"].lower()] = t
            if tagset(t) & set(TAGS):
                continue
            if t["state"] in ("metaDL", "forcedMetaDL") or t["name"] == t["hash"]:
                continue  # no real name until the magnet's metadata arrives
            try:
                tag, what, idtag = add(arrs[app], t["name"], desired[app])
            except urllib.error.HTTPError as e:
                tag, what, idtag = "needs-import", f"{app} said HTTP {e.code}: {e.read()[:200]!r}", None
            qbt.call("torrents/addTags", {"hashes": t["hash"],
                                          "tags": ",".join(x for x in (tag, idtag) if x)})
            t["tags"] = ",".join(x for x in (tag, idtag) if x)
            log(f"{category}: {t['name']!r} -> {tag}: {what}")
            if tag == "glue-added":
                # Have the arr look at the queue now rather than in a minute.
                arrs[app].post("command", {"name": "RefreshMonitoredDownloads"})
        if torrents:
            finish_blocked(qbt, arrs[app], app, torrents)


# ------------------------------------------------------------------------ main

def main():
    with open(os.path.join(CONF, "desired.json"), encoding="utf-8") as fh:
        desired = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    arrs = {name: Arr(name, d["url"], d["api"], os.environ.get(d["api_key_env"], ""))
            for name, d in desired.items()}
    qbt = Qbt()
    next_config = 0.0
    while True:
        if time.monotonic() >= next_config:
            failed = False
            for name, arr in arrs.items():
                try:
                    ensure_settings(arr, desired[name])
                except Exception as e:  # one app being down mustn't stop the others
                    detail = e.read()[:300] if isinstance(e, urllib.error.HTTPError) else ""
                    log(f"{name}: settings not applied ({type(e).__name__}: {e} {detail!r}); retrying")
                    failed = True
            next_config = time.monotonic() + (60 if failed else CONFIG_INTERVAL)
        try:
            handle_pasted(qbt, arrs, desired)
        except Exception as e:
            log(f"pasted torrents: {type(e).__name__}: {e}")
            qbt.logged_in = False
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
