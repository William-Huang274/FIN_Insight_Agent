"""Read native identity/metadata without transferring checkpoint values.

Uses the maintained SDK's exact-ID field projection. Authorization remains at
the caller; this is neither a cache nor a substitute for checkpoint validation.
"""


async def thread_header(sdk, thread_id):
    fields = ['thread_id', 'status', 'metadata', 'created_at', 'updated_at']
    rows = await sdk.threads.search(ids=[str(thread_id)], limit=1, select=fields)
    if len(rows) != 1 or rows[0].get('thread_id') != str(thread_id):
        raise ValueError('native_thread_identity_not_found')
    # Do not retain values even if an incompatible server returns extra fields.
    return {key: rows[0][key] for key in fields if key in rows[0]}
