"""Resolve discovered bill identities without fetching challenged HTML or exposing snippets."""
from datetime import date

from .congress_api import CongressAPI, bill_identity
from .external_sources import ExternalSourceError


class LegislationDiscovery:
    def __init__(self, api=None):
        self.api = api or CongressAPI()
        self.records = {}

    async def resolve(self, url, cutoff):
        try:
            identity = bill_identity(url)
        except ValueError:
            return None
        try:
            if identity not in self.records:
                self.records[identity] = await self.api.read(identity, 'record', 0, 20)
            record = self.records[identity]
            introduced = date.fromisoformat(record['bill'].get('introducedDate', ''))
        except ExternalSourceError as exc:
            return exc.code
        except (ValueError, KeyError, TypeError):
            return 'congress_introduction_date_unverified'
        if introduced > cutoff:
            return 'after_cutoff'
        # Introduction admits the identity, not today's title/status or an old text version.
        return {'identity':dict(zip(('congress','type','number'), identity)),
                'discovered_url':url, 'introduced_date':introduced.isoformat(),
                'verification_url':record['source_url'],
                'role':'navigation_only', 'writer_citable':False, 'full_text_read':False,
                'meaning':'Bill identity existed by cutoff. Search title/snippet withheld. Select dated text versions and read full text; metadata alone does not establish enactment.',
                'next_calls':[{'tool':'read_legislation', 'arguments':{'query':url,'operation':op}}
                              for op in ('record','texts','actions')]}
