"""Operator-configured retrieval transport; never model-supplied proxies."""
import os
from urllib.parse import urlsplit, unquote


def proxy_url():
    value = os.environ.get('FIN_PUBLIC_HTTPS_PROXY', '').strip()
    return _validated_proxy(value)


def _validated_proxy(value):
    if not value:
        return None
    p = urlsplit(value)
    if p.scheme not in {'http', 'https', 'socks5', 'socks5h'} or not p.hostname or not p.port or p.path not in {'','/'} or p.query or p.fragment:
        raise ValueError('public_proxy_configuration_invalid')
    return value


def forbidden_retry_options():
    """One alternate transport, only when the initial route was not explicit."""
    if proxy_url():
        return None
    value = os.environ.get('FIN_PUBLIC_403_PROXY', '').strip()
    if not value and os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                enabled = winreg.QueryValueEx(key, 'ProxyEnable')[0]
                server = winreg.QueryValueEx(key, 'ProxyServer')[0]
            if enabled:
                entries = dict(part.split('=', 1) for part in server.split(';') if '=' in part)
                value = entries.get('https', entries.get('http', server if not entries else ''))
                if value and '://' not in value:
                    value = 'http://' + value
        except OSError:
            return None
    value = _validated_proxy(value)
    if not value:
        return None
    # Do not label the same environment proxy as a new route.
    initial = os.environ.get('HTTPS_PROXY', os.environ.get('https_proxy',
        os.environ.get('ALL_PROXY', os.environ.get('all_proxy', ''))))
    if initial.rstrip('/') == value.rstrip('/'):
        return None
    return {'proxy': value, 'trust_env': False}


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
        'meaning':'公开 HTTP、DDGS、Playwright 和 DS Search/Fetch 支持宿主配置的代理。公开网页HTTP 403在尚未使用已配置代理时，自动通过本机代理重试一次；Windows可读取启用的系统代理，容器使用宿主配置。已走代理不重复同一路径；代理后仍403继续返回访问障碍。429不触发该重试。连接、DNS、TLS、超时可请求宿主核验代理通道；模型不能自行指定代理地址。'}
