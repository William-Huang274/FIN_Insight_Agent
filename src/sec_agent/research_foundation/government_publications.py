"""Use GovInfo MODS to bind a bill rendition to its issue date, not its policy status."""
from datetime import date
import re
from urllib.parse import urlsplit

from lxml import etree

from .external_sources import ExternalSourceError
from sec_agent.research.reviewed_evidence_pack import canonical_digest


def bill_package(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.govinfo.gov' or parsed.query:
        return None
    match = re.fullmatch(r'/(?:content/pkg|app/details)/(BILLS-\d+[a-z]+\d+[a-z]+)(?:/[^?#]*)?', parsed.path)
    return match[1] if match else None


def mods_bill_record(xml, package, original_url):
    try:
        root = etree.fromstring(xml.encode(), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ExternalSourceError('govinfo_metadata_invalid') from exc
    ns = {'m':'http://www.loc.gov/mods/v3'}
    details = 'https://www.govinfo.gov/app/details/' + package
    identities = root.xpath('./m:identifier[@type="uri"]/text()', namespaces=ns)
    urls = root.xpath('./m:location/m:url/text()', namespaces=ns)
    days = root.xpath('./m:originInfo/m:dateIssued[@encoding="w3cdtf"]/text()', namespaces=ns)
    if details not in identities or len(set(days)) != 1 or original_url not in urls + [details]:
        raise ExternalSourceError('govinfo_metadata_identity_mismatch')
    try:
        day = date.fromisoformat(days[0])
    except ValueError as exc:
        raise ExternalSourceError('govinfo_issue_date_invalid') from exc
    target = original_url
    if target == details:
        choices = root.xpath('./m:location/m:url[@displayLabel="HTML rendition"]/text()', namespaces=ns)
        if len(choices) != 1 or bill_package(choices[0]) != package:
            raise ExternalSourceError('govinfo_readable_rendition_unresolved')
        target = choices[0]
    title = ' '.join(root.xpath('./m:titleInfo/m:title/text()', namespaces=ns))
    return target, day, title


async def resolve_bill(candidate, fetcher):
    package = bill_package(candidate.canonical_url)
    metadata_url = f'https://www.govinfo.gov/metadata/pkg/{package}/mods.xml'
    page = await fetcher.fetch(metadata_url, timeout_seconds=15)
    if page.final_url != metadata_url or not page.html:
        raise ExternalSourceError('govinfo_metadata_unavailable')
    target, day, title = mods_bill_record(page.html, package, candidate.canonical_url)
    fields = {'published_at':day.isoformat(), 'snippet':''}
    if title:
        fields['title'] = title[:512]
    if target != candidate.canonical_url:
        fields.update(canonical_url=target, candidate_id=canonical_digest({
            'discovered_candidate':candidate.candidate_id, 'official_rendition':target}))
    return candidate.model_copy(update=fields), day
