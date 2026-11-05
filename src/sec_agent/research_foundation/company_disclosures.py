"""Issuer discovery for dated financial research. Only a read origin can be cited."""

import asyncio
import calendar
import json
import re
from datetime import date, timedelta
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from connectors.sec_edgar_connector import SecEdgarConnector, SecEdgarConnectorError
from .external_sources import (
    ExternalSourceError,
    FetchedPage,
    ProviderHit,
    _host_in_domains,
)

# Navigation roots, not evidence. Keep dated releases and accession IDs out of this directory.
# Other issuers are resolved from the SEC ticker file and their submissions metadata.
_SITES = {
    "PHM": (
        "PulteGroup",
        "https://www.pultegroup.com/investor-relations/investor-overview/default.aspx",
        "pultegroupinc.com",
    ),
    "LEN": ("Lennar", "https://investors.lennar.com/", ""),
    "DHI": ("D.R. Horton", "https://investor.drhorton.com/", ""),
    "TOL": ("Toll Brothers", "https://investors.tollbrothers.com/", ""),
}
_DISCLOSURE = re.compile(
    r"earnings|results|quarter|\bQ[1-4]\b|10[- ]?[QK]|8[- ]?K|investor relations|official website|gross margin|net orders|业绩|财报|季报|年报|官网|公司网站|投资者关系",
    re.I,
)
_WEB = re.compile(
    r"investor relations|official website|company website|官网|公司网站|投资者关系",
    re.I,
)
_SUFFIX = re.compile(
    r"\s+(?:incorporated|inc|corp(?:oration)?|company|plc|ltd|holdings?)\b.*$", re.I
)


def words(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def issuer_match(rows, query):
    normalized = " " + words(query) + " "
    matches = []
    for row in rows:
        name = _SUFFIX.sub("", words(row["title"])).strip()
        ticker = row["ticker"]
        if name and len(name) >= 3 and " " + name + " " in normalized:
            matches.append((len(name), row))
        elif (
            query.strip().upper() == ticker
            or re.search(r"\$" + re.escape(ticker) + r"(?![A-Za-z0-9])", query)
            or (
                len(ticker) >= 2
                and ticker not in {"IR", "SEC", "EPS", "FY", "US", "CEO", "CFO", "GAAP"}
                and re.search(
                    r"(?<![A-Za-z0-9])" + re.escape(ticker) + r"(?![A-Za-z0-9])", query
                )
            )
        ):
            matches.append((len(ticker), row))
    if not matches:
        return None
    # Never silently choose among multiple companies/share classes with different CIKs.
    if len({row["cik_str"] for _, row in matches}) != 1:
        return None
    return max(matches, key=lambda hit: hit[0])[1]


def edgar_text(html):
    """SEC financial statements use tables and inline XBRL. Preserve rows and
    adjacent inline text, exclude hidden XBRL, scripts, and styling from quotes."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["head", "script", "style", "noscript", "ix:hidden", "ix:header"]):
        node.decompose()
    for node in soup.find_all(style=True):
        if re.search(
            r"(?:^|;)\s*display\s*:\s*none(?:\s*!important)?\s*(?:;|$)",
            (node.attrs or {}).get("style", ""),
            re.I,
        ):
            node.decompose()
    for cell in soup.find_all(["th", "td"]):
        cell.append(" ")
    for block in soup.find_all(["div", "p", "tr", "br", "li", "h1", "h2", "h3"]):
        block.append("\n")
    return "\n".join(
        line for raw in soup.get_text().splitlines() if (line := " ".join(raw.split()))
    )


class CompanySources:
    def __init__(self, user_agent, origin):
        self.sec = SecEdgarConnector(user_agent=user_agent) if user_agent else None
        self.origin = origin
        self.tickers = None
        self.submissions = {}
        self.disclosed_sites = {}
        self.annual_checked = set()

    async def get(self, url, timeout=10):
        if self.sec is None:
            raise ExternalSourceError("sec_contact_not_configured")
        try:
            return await asyncio.to_thread(
                self.sec.read_public_resource, url, timeout=timeout
            )
        except SecEdgarConnectorError as exc:
            raise ExternalSourceError(exc.reason_code or "sec_transport_error") from exc

    async def fetch(self, url, *, timeout_seconds):
        if (
            urlsplit(url).netloc == "www.sec.gov"
            and urlsplit(url).path.startswith("/Archives/edgar/data/")
            and self.sec
        ):
            body = await self.get(url, timeout_seconds)
            html = body.decode("utf-8", errors="replace")
            return FetchedPage(
                final_url=url,
                html=html,
                extracted_text=edgar_text(html),
                extraction_method="sec_edgar_html",
                status_code=200,
                content_type="text/html",
            )
        return await self.origin.fetch(url, timeout_seconds=timeout_seconds)

    async def lookup(self, request):
        if not (
            _DISCLOSURE.search(request.query)
            or re.fullmatch(r"[A-Za-z0-9. -]{2,45}", request.query)
            and len(request.query.split()) <= 3
        ):
            return None
        error = None
        try:
            if self.tickers is None:
                self.tickers = list(
                    json.loads(
                        await self.get(SecEdgarConnector.COMPANY_TICKERS_URL)
                    ).values()
                )
            row = issuer_match(self.tickers, request.query)
        except (ExternalSourceError, ValueError) as exc:
            error = getattr(exc, "code", "sec_directory_invalid")
            row = None
        if not row and (
            error or any(words(request.query) == words(v[0]) for v in _SITES.values())
        ):
            local = issuer_match(
                [dict(title=v[0], ticker=k, cik_str=k) for k, v in _SITES.items()],
                request.query,
            )
            if not local:
                return None
            row = dict(local, cik_str=None)
        if not row:
            return None
        ticker = row["ticker"]
        site = _SITES.get(ticker)
        data = {}
        if row["cik_str"]:
            cik = str(row["cik_str"]).zfill(10)
            try:
                if cik not in self.submissions:
                    url = SecEdgarConnector.SUBMISSIONS_URL_TEMPLATE.format(cik=cik)
                    data = json.loads(await self.get(url))
                    if int(data["cik"]) != int(cik):
                        raise ExternalSourceError("sec_submissions_identity_mismatch")
                    self.submissions[cik] = data
                data = self.submissions[cik]
            except (ExternalSourceError, ValueError, KeyError) as exc:
                data = {}
                error = getattr(exc, "code", "sec_submissions_invalid")
        roots = [site[1]] if site else []
        for key in ("investorWebsite", "website"):
            u = data.get(key, "")
            if u and "://" not in u:
                u = "https://" + u
            if (
                u
                and urlsplit(u).scheme == "https"
                and urlsplit(u).hostname
                and not urlsplit(u).username
            ):
                roots.append("https://" + urlsplit(u).netloc + "/")
        evidence = {
            root: "host_issuer_directory"
            if site and root == site[1]
            else "sec_submissions_metadata"
            for root in roots
        }
        for root, filing in self.disclosed_sites.get(ticker, {}).items():
            roots.append(root)
            evidence[root] = filing
        issuer = Issuer(
            ticker, data, list(dict.fromkeys(roots)), site[2] if site else "", error
        )
        issuer.evidence = evidence
        if not roots and data and ticker not in self.annual_checked:
            # An issuer's dated 10-K often identifies its corporate and IR sites even
            # when the corresponding SEC submissions metadata fields are blank.
            recent = data.get("filings", {}).get("recent", {})
            cutoff = request.run_scope.research_as_of.date().isoformat()
            row = next(
                (
                    i
                    for i, form in enumerate(recent.get("form", []))
                    if form == "10-K" and recent["filingDate"][i] <= cutoff
                ),
                None,
            )
            if row is not None:
                url = SecEdgarConnector._build_filing_url(
                    data["cik"],
                    recent["accessionNumber"][row],
                    recent["primaryDocument"][row],
                )
                try:
                    html = await self.get(url)
                    self.learn_websites(issuer, html, url)
                    self.annual_checked.add(ticker)
                except ExternalSourceError:
                    pass  # General web discovery still works without verified corporate domains.
        return issuer

    def learn_websites(self, issuer, html, filing_url):
        # Only an explicit self-identification in a dated SEC original counts.
        # Emails, suppliers, analysts and generic investor-hosting domains do not.
        text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)
        pattern = (
            r"(?:our|company['’]s|corporate|investor relations) (?:website|web site)(?: address)?"
            r"(?: (?:is at|at|is))?[,: ]+((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,})"
        )
        for value in re.findall(pattern, text, re.I):
            host = urlsplit(value if "://" in value else "https://" + value).hostname
            if not host or not re.fullmatch(
                r"[a-z0-9.-]+\.[a-z]{2,}", host.rstrip("."), re.I
            ):
                continue
            host = host.rstrip(".")
            root = "https://" + host + "/"
            if host.removeprefix("www.") not in issuer.domains:
                issuer.roots.append(root)
                issuer.domains += (host.removeprefix("www."),)
                issuer.evidence[root] = filing_url
                self.disclosed_sites.setdefault(issuer.ticker, {})[root] = filing_url


class Issuer:
    def __init__(self, ticker, data, roots, alias, error):
        self.ticker, self.data, self.roots, self.error = ticker, data, roots, error
        self.evidence = {}
        self.domains = tuple(
            dict.fromkeys(
                [urlsplit(u).hostname.removeprefix("www.") for u in roots]
                + ([alias] if alias else [])
            )
        )

    def filings(self, request):
        recent = self.data.get("filings", {}).get("recent", {})
        cutoff = request.run_scope.research_as_of.date()
        q = request.query
        quarter = re.search(
            r"\bQ([1-4])\b|\b(first|second|third|fourth)\s+(?:fiscal\s+)?quarter|([一二三四1234])季",
            q,
            re.I,
        )
        number = None
        if quarter:
            token = next(s for s in quarter.groups() if s).lower()
            number = {
                "first": 1,
                "second": 2,
                "third": 3,
                "fourth": 4,
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
            }.get(token)
            if number is None:
                number = int(token)
        year_match = re.search(r"(?<!\d)(20\d{2})(?!\d)", q)
        year = int(year_match[1]) if year_match else cutoff.year
        end = self.data.get("fiscalYearEnd", "")
        period = None
        if number and re.fullmatch(r"\d{4}", end):
            month = int(end[:2])
            if 1 <= month <= 12:
                ordinal = year * 12 + month - 1 - (4 - number) * 3
                y, m = divmod(ordinal, 12)
                period = date(y, m + 1, calendar.monthrange(y, m + 1)[1])
        required_forms = {
            form.upper()
            for form in re.findall(
                r"(?<![A-Za-z0-9])(10-K|10-Q|8-K)(?![A-Za-z0-9])", q, re.I
            )
        }
        rows = []
        for i, form in enumerate(recent.get("form", [])):
            if form not in (required_forms or {"8-K", "10-K", "10-Q"}):
                continue
            filed = date.fromisoformat(recent["filingDate"][i])
            if filed > cutoff or not recent["reportDate"][i]:
                continue
            report = date.fromisoformat(recent["reportDate"][i])
            if request.start_published_date and filed < request.start_published_date:
                continue
            if request.end_published_date and filed > request.end_published_date:
                continue
            if period:
                if form == "8-K" and not period <= filed <= period + timedelta(
                    days=100
                ):
                    continue
                if form != "8-K" and abs((report - period).days) > 8:
                    continue
            elif year_match and report.year != year:
                continue
            if form == "8-K" and "2.02" not in [
                item.strip() for item in recent["items"][i].split(",")
            ]:
                continue
            rows.append(
                (
                    form,
                    filed,
                    report,
                    recent["accessionNumber"][i],
                    recent["primaryDocument"][i],
                )
            )
        return sorted(rows, key=lambda r: (r[1], r[0] == "8-K"), reverse=True)


class FilingSearch:
    provider_id = "sec_edgar_filings"

    def __init__(self, issuer, sources):
        self.issuer, self.sources = issuer, sources
        self.dates = {}
        self.failures = []

    async def search(self, request):
        if self.issuer.error:
            raise ExternalSourceError(self.issuer.error)
        hits = []
        cik = str(int(self.issuer.data["cik"]))
        for form, filed, report, accession, doc in self.issuer.filings(request)[:4]:
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not re.fullmatch(
                r"[\w.-]+", doc
            ):
                continue
            url = SecEdgarConnector._build_filing_url(cik, accession, doc)

            def add(target, title):
                self.dates[target] = filed
                hits.append(
                    ProviderHit(
                        url=target,
                        title=f"{self.issuer.ticker} {title} · {filed}",
                        published_at=filed.isoformat(),
                    )
                )

            if form == "8-K":
                index = urljoin(url, accession + "-index.htm")
                try:
                    html = await self.sources.get(index)
                    soup = BeautifulSoup(html, "html.parser")
                    for tr in soup.select("table.tableFile tr"):
                        cells = tr.find_all("td")
                        if len(cells) < 4 or not re.fullmatch(
                            r"EX-99(?:\.1|\.01)?", cells[3].get_text(strip=True), re.I
                        ):
                            continue
                        anchor = cells[2].find("a", href=True)
                        if anchor:
                            href = urljoin(index, anchor["href"])
                            if href.startswith(
                                url.rsplit("/", 1)[0] + "/"
                            ) and href.lower().endswith((".htm", ".html")):
                                add(
                                    href,
                                    "8-K "
                                    + cells[3].get_text(strip=True)
                                    + " (Item 2.02)",
                                )
                except ExternalSourceError as exc:
                    self.failures.append(
                        {"stage": "filing_index", "url": index, "reason": exc.code}
                    )
            add(url, form + " · report date " + report.isoformat())
        return hits


class WebsiteSearch:
    """Keep the provider's result order, but enforce the issuer domain locally."""

    def __init__(self, provider, domains):
        self.provider = provider
        self.domains = domains
        self.provider_id = "issuer_site_" + provider.provider_id

    async def search(self, request):
        scoped = request.model_copy(update={"include_domains": self.domains})
        if (
            self.provider.provider_id != "exa_hosted_mcp_web_search"
            and "site:" not in request.query
        ):
            # Keep the query intact. Use the primary corporate domain for engines
            # which accept only text operators rather than a domain field.
            scoped = scoped.model_copy(
                update={"query": request.query + " site:" + self.domains[0]}
            )
        hits = await self.provider.search(scoped)
        return [
            h
            for h in hits
            if _host_in_domains(urlsplit(h.url).hostname or "", self.domains)
        ]
