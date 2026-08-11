# FIN SearXNG diagnostic instance

This deployment is a local, loopback-only metasearch diagnostic. It is not a
production search provider and its results cannot enter an Evidence Pack.

The image is pinned to the official SearXNG Linux/amd64 package digest. JSON
output is explicitly enabled because the default SearXNG configuration only
guarantees HTML output.

The diagnostic profile keeps only Bing, Brave, DuckDuckGo, and Google. One FIN
adapter query can therefore fan out to as many as four upstream engine
requests. FIN can enforce the number of calls into SearXNG, but cannot prove an
exact upstream HTTP-request count inside SearXNG. This is one reason the route
remains diagnostic-only.

The healthcheck loads only the local homepage. It must never call `/search`,
because a search-based healthcheck would create ungoverned periodic upstream
queries.

From the repository root in PowerShell:

```powershell
./scripts/dev/start_searxng_diagnostic.ps1
```

The launcher generates an ephemeral process-only `SEARXNG_SECRET`; it is not
written to Git or to a repository `.env` file. The service binds only to
`127.0.0.1:8888`.

Stop the diagnostic service with:

```powershell
docker compose -f deploy/searxng-diagnostic/docker-compose.yml down
```

Do not replace the loopback URL with a public SearXNG instance. A future paid
search API must receive its own provider profile, credential gate, admission,
and evaluation before it may be considered for production use.
