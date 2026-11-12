"""Operator-configured retrieval transport; never model-supplied proxies."""
import os
from urllib.parse import urlsplit, unquote


def proxy_url():
    value = os.environ.get('FIN_PUBLIC_HTTPS_PROXY', '').strip()
    if not value:
        return None
    p = urlsplit(value)
    if p.scheme not in {'http', 'https', 'socks5', 'socks5h'} or not p.hostname or not p.port or p.path not in {'','/'} or p.query or p.fragment:
        raise ValueError('public_proxy_configuration_invalid')
    return value


def http_options():
    value = proxy_url()
    return {'proxy': value, 'trust_env': False} if value else {}


def browser_options():
    value = proxy_url()
    if not value:
        return {}
    p = urlsplit(value)
    host = f'[{p.hostname}]' if ':' in p.hostname else p.hostname
    proxy = {'server': f'{p.scheme}://{host}:{p.port}'}
    if p.username:
        proxy['username'] = unquote(p.username)
    if p.password:
        proxy['password'] = unquote(p.password)
    return {'proxy': proxy}


def network_feedback():
    return {'kind':'public_network_route',
        'route':'configured_proxy' if proxy_url() else 'default_network',
        'meaning':'公开 HTTP、DDGS、Playwright 和 DS Search/Fetch 支持宿主配置的代理。连接、DNS、TLS、超时可请求宿主核验代理通道；代理已配置仍失败时需核验代理与目标站。403/验证码/429不等于网络不通，不自动换身份或反复重试。模型不能自行指定代理地址；修复后可沿原查询接续。'}
