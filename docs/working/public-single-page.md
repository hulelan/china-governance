# Exposing one page publicly without exposing the corpus

Asked 2026-11-06: can one page be made public while the rest of the site stays
behind Basic Auth, without creating a path to the database? Yes. The mechanism is
already in use on this server, and there is a version with no database
reachability at all.

## What the live config actually does

Read from `/etc/nginx/sites-enabled/chinagovernance`, not from memory:

* `auth_basic "Private archive"` sits at **server** level (line 7), so it covers
  every location by default.
* It is already overridden per-location: `location ^~ /.well-known/acme-challenge/`
  sets `auth_basic off` so certbot can renew.
* `location /` and `location /raw_html/` both `proxy_pass http://127.0.0.1:8001`
  (uvicorn, 2 workers) under `limit_req` zones `perip` 10r/s, `rawhtml` 2r/s and a
  `harvester` geo-zone at 1r/s.
* `location = /robots.txt` serves `alias /var/www/robots.txt` — and does **not**
  set `auth_basic off`, so robots.txt currently returns 401 and no crawler can read
  the Disallow rules. Moot while everything is private; it stops being moot the
  moment one path goes public.

So the per-location exemption is proven on this box. The only question is what sits
behind the exempted location.

## Two architectures, and they are not close

### A. Static file served by nginx (recommended)

```nginx
location = /dossier/agent-terminals {
    auth_basic off;
    limit_req zone=perip burst=5 nodelay;
    default_type text/html;
    alias /var/www/public/agent-terminals.html;
    add_header X-Content-Type-Options nosniff;
    add_header Cache-Control "public, max-age=300";
}
```

The decisive property: **nginx never contacts uvicorn on this path.** No route
handler runs, no SQL executes, no query string is interpreted, and the
`documents.db` handle is not in the request path at all. The public surface is one
file served by the same nginx code path that already serves `robots.txt`. A bug in
the web app — in a service, a template, a filter — is not reachable from the public
URL, because the public URL does not enter the app.

Four details that matter:

* **The file must live under `/var/www`.** nginx runs as `www-data`, which cannot
  traverse into `/root`, so an `alias` into `/root/china-governance/...` returns
  **403**. CLAUDE.md already records this for `robots.txt` and the `/static/` alias;
  it applies here identically.
* **`location =` (exact match), never a prefix.** A prefix location plus a
  directory invites path walking. Exact match exposes exactly one URL, and
  `autoindex` is never involved.
* **The page must not link into the private app.** Every such link 401s for a
  public reader. The dossier built today already links to primary sources
  (miit.gov.cn, gov.cn, the three publishers) rather than to `/document/<id>`, so it
  is publicly coherent as written.
* **Make `robots.txt` public too**, with `auth_basic off` on its existing location,
  and allow that one path while disallowing the rest. A Disallow rule behind a 401
  is not a rule.

### B. An app-rendered route with `auth_basic off`

Weaker on every axis. The route executes inside the same uvicorn process that holds
the read-only DB connection; any parameter it accepts is public input surface; the
1-hour per-worker cache and the `limit_req` zones become the only thing between a
public scraper and the app; and the page's internal links break anyway because
everything they point at is still 401. The only thing it buys is that the page
refreshes itself.

A middle option exists if freshness matters: keep architecture A and regenerate the
file from the corpus on a schedule (a script that writes `/var/www/public/*.html`,
run from `daily_sync.sh` Phase 3 after publish). The page is then current to the
last nightly and still served as a static file. Generation reads the DB; serving
never does.

## Residual risks, stated plainly

* `:443` is already the public attack surface, and nginx already terminates TLS
  there. Architecture A adds one static `location` to an existing listener. It does
  **not** open a new port, a new service, or a new process.
* A static file leaks exactly what is in it. Today's dossier shows internal document
  ids (`900210802`, `12694498`). They are not secrets, but they do reveal the id
  space and the corpus's size. Strip them if that is unwanted — the page is just as
  readable without them.
* Government texts are reproduced in full, which is correct: PRC official documents
  carry no copyright. **Press bodies must not be**, and the dossier links the three
  media reports rather than republishing them. Keep that rule for any public page.
* Every guarantee above is a property of *not running the app*. If the page later
  becomes dynamic, all of it resets and architecture B's analysis applies instead.

## What this does not protect against

Someone scraping the one public page. There is no defence against that and none is
wanted — the point is to show the work. The defence is that there is exactly one
page to scrape and nothing links deeper.

## Not implemented

This is an outward-facing change to a live site, so nothing has been applied.
Implementing architecture A is: create `/var/www/public/`, copy the rendered file,
add the two `location` blocks (the page, and `auth_basic off` on `robots.txt`),
`nginx -t`, reload.
