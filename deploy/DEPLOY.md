# Deploying Gallop

Same pattern as Cairn: `nginx:alpine` serves `site/`, bound to localhost,
reverse-proxied by the host Caddy.

## First deploy

```
git clone <repo> gallop
cd gallop/deploy
docker compose up -d
curl -s http://127.0.0.1:3642/healthz    # ok
```

Add the site block to the host Caddyfile and reload Caddy. The hostname is
provisional (handover §14, [inference]):

```
gallop.yeomanops.com {
    reverse_proxy 127.0.0.1:3642
}
```

## Update

Replace files under `site/` (a `git pull` is enough) and hard-refresh.
`index.html` is served no-cache, so no container restart is needed. Audio
stems are cached for 30 days; if you change a stem, change its filename in
`cases.json` too.

## Checks before announcing a build

```
python tools/synth_stems.py
python tools/validate_cases.py --weight
```
