# Deploying Gallop

Same pattern as Cairn: `nginx:alpine` serves `site/`, joined to the shared
`caddy_net` Docker network, where the Caddy container reaches it by name on
port 80. No host port is published.

## First deploy

```
git clone <repo> gallop
cd gallop/deploy
cp .env.example .env && sed -i "s/change-me/$(openssl rand -hex 24)/" .env   # review-collector token
docker compose up -d
docker exec caddy curl -s http://gallop/healthz                 # ok
docker exec caddy curl -s http://gallop/api/reviews/health      # ok
```

Two containers: `gallop` (nginx, the site) and `gallop-reviews` (a stdlib
Python collector). Reviews submitted in reviewer mode are POSTed to
`/api/reviews` and appended to `reviews.jsonl` on the `gallop_reviews`
volume. Nothing else is ever sent to the server.

## Collecting reviews

```
source .env
curl -s "https://gallop.yeomanops.com/api/reviews?token=$REVIEWS_TOKEN" > reviews.jsonl
python ../tools/reviews_report.py reviews.jsonl
```

Or read the file straight off the volume: `docker exec gallop-reviews cat
/data/reviews.jsonl`. The report script also accepts a reviewer's "Export
all reviews" JSON and deduplicates across files.

Add the site block to the Caddyfile and reload Caddy:

```
gallop.yeomanops.com {
    reverse_proxy gallop:80
}
```

## Update

Replace files under `site/` (a `git pull` is enough) and hard-refresh.
`index.html` is served no-cache, so no container restart is needed. If
`deploy/` changed, `docker compose up -d` again. Audio
stems are cached for 30 days; if you change a stem, change its filename in
`cases.json` too.

## Checks before announcing a build

```
python tools/synth_stems.py
python tools/validate_cases.py --weight
```
