# FIN SearXNG diagnostic instance

This deployment is a local, loopback-only metasearch diagnostic. It is not a
production search provider and its results cannot enter an Evidence Pack.

The image is pinned to the official SearXNG Linux/amd64 package digest. JSON
output is explicitly enabled because the default SearXNG configuration only
guarantees HTML output.

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
