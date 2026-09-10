# Deploying Gallop

Same pattern as Cairn: `nginx:alpine` serves `site/`, joined to the shared
`caddy_net` Docker network, where the Caddy container reaches it by name on
port 80. No host port is published.

## First deploy

```
git clone <repo> gallop
cd gallop/deploy
docker compose up -d
docker exec caddy curl -s http://gallop/healthz    # ok
```

Add the site block to the Caddyfile and reload Caddy:

```
gallop.yeomanops.com {
    reverse_proxy gallop:80
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
