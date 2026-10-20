from concurrent.futures import ThreadPoolExecutor
import ssl

from sec_agent.adapters.delegated_http import delegated_ssl_context


def test_concurrent_delegations_share_only_verified_tls_configuration():
    with ThreadPoolExecutor(8) as pool:
        contexts = list(pool.map(lambda _: delegated_ssl_context(), range(16)))
    assert all(context is contexts[0] for context in contexts)
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED
    assert contexts[0].check_hostname
    assert contexts[0].get_ca_certs()
