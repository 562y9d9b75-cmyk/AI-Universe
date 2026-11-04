"""Official local Sign in with ChatGPT / Plan Usage integration.

No ambient API keys, Codex credentials, cookies or alternate inference routes are
read. OAuth is initiated explicitly by the owner. This module performs no model
request until a plan-authorized connection and a selected catalog model exist.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from typing import Mapping
from urllib.parse import urlencode, urlsplit
import uuid

import fcntl
import httpx
import jwt

ISSUER = 'https://auth.openai.com'
DISCOVERY = ISSUER + '/.well-known/openid-configuration'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
JWKS = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'
DYNAMIC_CLIENT = 'dynamic_agent_client'  # Official OSS first-registration entrypoint.
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + PLAN_SCOPE
USAGE_URL = 'https://chatgpt.com/settings/usage'
DOCUMENTATION = [
    'https://developers.openai.com/siwc/quickstart',
    'https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt',
    'https://developers.openai.com/siwc/token-sharing-open-source/sign-in',
    'https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference',
]
VERIFICATION_DATE = '2026-11-04'


class AuthorizationRequired(Exception):
    """The user must sign in, grant plan permission, or select a model."""


class QuotaExhausted(Exception):
    """Pause tasks rather than retrying or switching billing paths."""


class ModelConnectionError(Exception):
    """A bounded, credential-free diagnostic for an official endpoint."""

    def __init__(self, message, *, code='', http_status=None, request_id=''):
        self.code = code
        self.http_status = http_status
        self.request_id = request_id
        suffix = f' [{code}]' if code else ''
        if request_id:
            suffix += f' request_id={request_id}'
        super().__init__(message + suffix)


def _root() -> Path:
    # Import lazily so tests and CLI tools can inject isolated storage before use.
    from .db import DATA
    root = DATA / 'model-auth'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


def _path(key: str) -> Path:
    return _root() / (hashlib.sha256(key.encode()).hexdigest() + '.json')


@contextlib.contextmanager
def _lock(key: str):
    path = _path(key).with_suffix('.lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _load(key: str, default=None):
    path = _path(key)
    if not path.exists():
        return default if default is not None else {}
    # Do not trust unexpectedly symlinked credential records.
    if path.is_symlink():
        raise ModelConnectionError('模型凭据文件路径无效')
    path.chmod(0o600)
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise ModelConnectionError('模型连接记录无法读取，请检查本地数据目录') from exc


def _save(key: str, value: dict):
    target = _path(key)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=_root())
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _organization_key(organization_id: str) -> str:
    if not isinstance(organization_id, str) or not organization_id:
        raise AuthorizationRequired('模型连接缺少当前公司身份，请重新登录')
    return 'organization:' + organization_id


def _host_id() -> str:
    with _lock('installation'):
        record = _load('installation')
        if not record.get('ext_agent_host_id'):
            record = {'ext_agent_host_id': 'urn:uuid:' + str(uuid.uuid4())}
            _save('installation', record)
        return record['ext_agent_host_id']


def _client() -> httpx.Client:
    # Retain managed proxy and CA trust; never turn off TLS verification.
    return httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=False)


def callback_uri(port: int | None = None) -> str:
    origin = urlsplit(os.getenv('AIU_ORIGIN', 'http://localhost:3000'))
    port = int(port if port is not None else origin.port or os.getenv('AIU_WEB_PORT', '3000'))
    if not 1 <= port <= 65535:
        raise ValueError('API 端口无效')
    return f'http://127.0.0.1:{port}/api/model/chatgpt/callback'


def _validate_callback(uri: str):
    parts = urlsplit(uri)
    if (parts.scheme != 'http' or parts.hostname != '127.0.0.1'
            or parts.path != '/api/model/chatgpt/callback' or parts.query or parts.fragment
            or parts.username or parts.password or not parts.port):
        raise ValueError('官方本地授权回调必须使用 http://127.0.0.1:端口/api/model/chatgpt/callback')


def begin_authorization(organization_id: str, user_id: str, *, redirect_uri: str | None = None,
                        new_profile: bool = False, profile_id: str | None = None,
                        enable_plan: bool = False) -> dict:
    """Prepare one explicit owner action; opening this URL requires their browser."""
    key = _organization_key(organization_id)
    uri = redirect_uri or callback_uri()
    _validate_callback(uri)
    if not user_id:
        raise AuthorizationRequired('请先登录个人工作空间')
    with _lock(key):
        store = _load(key)
        profiles = store.get('profiles', {})
        selected_id = profile_id or store.get('active_profile') or next(reversed(profiles), None)
        if profile_id and profile_id not in profiles:
            raise AuthorizationRequired('所选 ChatGPT 连接不存在')
        profile = {} if new_profile else profiles.get(selected_id, {})
        chosen_id = str(uuid.uuid4()) if not profile else selected_id
        epoch = int(store.get('authorization_epoch', 0)) + 1
        store['authorization_epoch'] = epoch
        _save(key, store)
    verifier, state, nonce = (secrets.token_urlsafe(48) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    issued_id = profile.get('client_id')
    params = {
        'client_id': issued_id or DYNAMIC_CLIENT,
        'ext_agent_host_id': _host_id(),
        'response_type': 'code', 'redirect_uri': uri, 'scope': SCOPES,
        'resource': RESOURCE, 'state': state, 'nonce': nonce,
        'code_challenge_method': 'S256', 'code_challenge': challenge,
    }
    if issued_id:
        if profile.get('id_token'):
            params['id_token_hint'] = profile['id_token']
        if profile.get('email'):
            params['login_hint'] = profile['email']
    else:
        params['agent_name_hint'] = 'AI Universe'
    # Explicitly enabling after a declined scope may ask consent, ordinary login does not.
    if enable_plan:
        params['prompt'] = 'consent'
    expires_at = time.time() + 600
    pending = {
        'organization_id': organization_id, 'user_id': user_id, 'profile_id': chosen_id,
        'client_id': issued_id, 'verifier': verifier, 'nonce': nonce,
        'redirect_uri': uri, 'expires_at': expires_at, 'authorization_epoch': epoch,
    }
    _save('attempt:' + state, pending)
    # This URL can contain id_token_hint; API access logs must never log response bodies.
    return {'authorization_url': AUTHORIZE + '?' + urlencode(params), 'expires_at': expires_at}


def _error(response: httpx.Response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    err = body.get('error', {}) if isinstance(body, dict) else {}
    code = err.get('code', '') if isinstance(err, dict) else err if isinstance(err, str) else ''
    code = re.sub(r'[^A-Za-z0-9_.-]', '', str(code))[:100]
    request_id = re.sub(r'[^A-Za-z0-9_.-]', '', response.headers.get('x-request-id', ''))[:160]
    if code == 'subscription_sharing_usage_unavailable':
        raise QuotaExhausted('OpenAI 暂时无法检查 ChatGPT 计划用量，任务已暂停；保留授权，请稍后手动恢复。')
    if code == 'subscription_sharing_usage_limit_exceeded' or response.status_code == 429:
        raise QuotaExhausted('ChatGPT 计划或应用使用额度已达上限；任务已暂停。请在 ChatGPT 用量设置中查看。' + (f' request_id={request_id}' if request_id else ''))
    terminal_refresh = {'invalid_grant', 'invalid_refresh_token', 'token_expired',
                        'refresh_token_expired', 'refresh_token_invalidated', 'refresh_token_reused'}
    if code in terminal_refresh:
        raise AuthorizationRequired('ChatGPT 授权已失效，请重新连接。[' + code + ']')
    if response.status_code == 401:
        raise AuthorizationRequired('ChatGPT 授权未被接受，请重新连接并检查计划用量权限。')
    if code == 'subscription_sharing_user_not_eligible':
        raise AuthorizationRequired('当前 ChatGPT 账户、工作空间或政策不支持计划用量，请检查官方资格限制')
    elif response.status_code == 403:
        message = 'OpenAI 拒绝此次请求，请检查计划权限、地区或工作空间限制'
    elif response.status_code >= 500:
        message = 'OpenAI 服务或计划用量检查暂不可用，请稍后手动重试'
    else:
        message = 'OpenAI 官方接口拒绝请求'
    raise ModelConnectionError(message, code=code, http_status=response.status_code, request_id=request_id)


def _token_request(data: dict) -> dict:
    try:
        with _client() as client:
            response = client.post(TOKEN, data=data, headers={'Accept': 'application/json'})
    except httpx.HTTPError as exc:
        raise ModelConnectionError('无法连接 OpenAI 授权服务，原有授权记录已保留') from exc
    if response.status_code != 200:
        _error(response)
    try:
        result = response.json()
    except ValueError as exc:
        raise ModelConnectionError('OpenAI 授权响应格式无效') from exc
    if not isinstance(result, dict):
        raise ModelConnectionError('OpenAI 授权响应格式无效')
    return result


def _verify_identity(id_token: str, client_id: str, nonce: str, *, refreshing=False) -> dict:
    try:
        with _client() as client:
            discovery_response = client.get(DISCOVERY)
            discovery_response.raise_for_status()
            discovery = discovery_response.json()
            # The OSS production contract is fixed; never follow user-supplied token/JWKS URLs.
            if (discovery.get('issuer') != ISSUER or discovery.get('jwks_uri') != JWKS
                    or discovery.get('authorization_endpoint') != AUTHORIZE
                    or discovery.get('token_endpoint') != TOKEN):
                raise ModelConnectionError('OpenAI OIDC 元数据与官方生产配置不一致')
            jwks_response = client.get(JWKS)
            jwks_response.raise_for_status()
            keys = jwt.PyJWKSet.from_dict(jwks_response.json())
        header = jwt.get_unverified_header(id_token)
        if header.get('alg') not in ('RS256', 'ES256'):
            raise ValueError('unsupported signature algorithm')
        signing_key = next(k for k in keys.keys if k.key_id == header.get('kid') and k.algorithm_name == header.get('alg'))
        claims = jwt.decode(id_token, signing_key.key, algorithms=[header['alg']],
                            audience=client_id, issuer=ISSUER, leeway=5,
                            options={'require': ['sub', 'exp', 'iat'] + ([] if refreshing else ['nonce'])})
        if not isinstance(claims.get('sub'), str) or not claims['sub']:
            raise ValueError('missing subject')
        if (not refreshing or 'nonce' in claims) and (not isinstance(claims.get('nonce'), str) or not hmac.compare_digest(claims['nonce'], nonce)):
            raise ValueError('nonce mismatch')
        if isinstance(claims.get('aud'), list) and len(claims['aud']) > 1 and claims.get('azp') != client_id:
            raise ValueError('authorized party mismatch')
        return claims
    except ModelConnectionError:
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError, StopIteration, jwt.PyJWTError) as exc:
        raise ModelConnectionError('无法验证 OpenAI 身份签名、issuer、audience、有效期或 nonce；未启用此连接') from exc


def _token_fields(data: dict, previous: dict | None = None, *, allow_identity_only=False) -> dict:
    previous = previous or {}
    access = data.get('access_token')
    if allow_identity_only and not access and PLAN_SCOPE not in str(data.get('scope', '')).split():
        return {'id_token': data['id_token'], 'scopes': str(data.get('scope', '')).split(), 'saved_at': time.time()}
    if not isinstance(access, str) or not access or str(data.get('token_type', '')).lower() != 'bearer':
        raise ModelConnectionError('OpenAI 未返回有效的 Bearer 授权')
    expires = data.get('expires_in')
    if not isinstance(expires, (int, float)) or isinstance(expires, bool) or not 0 < expires <= 86400:
        raise ModelConnectionError('OpenAI 授权有效期无效')
    scope = data.get('scope')
    if scope is not None and not isinstance(scope, str):
        raise ModelConnectionError('OpenAI 返回的授权权限格式无效')
    fields = {
        'access_token': access, 'refresh_token': data.get('refresh_token', previous.get('refresh_token', '')),
        'token_type': 'Bearer', 'expires_at': time.time() + expires,
        'scopes': scope.split() if scope is not None else previous.get('scopes', []),
        'saved_at': time.time(),
    }
    if not isinstance(fields['refresh_token'], str):
        raise ModelConnectionError('OpenAI 刷新授权格式无效')
    if isinstance(data.get('id_token'), str):
        fields['id_token'] = data['id_token']
    elif previous.get('id_token'):
        fields['id_token'] = previous['id_token']
    return fields


def complete_authorization(query: Mapping[str, str]) -> dict:
    """One-shot callback; state binds the original owner/org without SameSite cookies."""
    state = query.get('state', '')
    if not isinstance(state, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', state):
        raise ModelConnectionError('授权 state 缺失或无效，请重新从模型设置发起连接')
    attempt_key = 'attempt:' + state
    with _lock(attempt_key):
        attempt = _load(attempt_key)
        if not attempt:
            raise ModelConnectionError('授权已处理或不存在，请重新连接')
        _path(attempt_key).unlink()  # Every callback, including errors, consumes the attempt.
    if attempt.get('expires_at', 0) <= time.time():
        raise ModelConnectionError('本次授权已过期，请重新连接')
    if query.get('error'):
        raise AuthorizationRequired('未获得 ChatGPT 授权。你可以返回模型设置重新连接；未调用任何模型。')
    code = query.get('code', '')
    if not isinstance(code, str) or not code or len(code) > 8192:
        raise ModelConnectionError('OpenAI 未返回有效授权码')
    issued = query.get('client_id') or attempt.get('client_id')
    if not isinstance(issued, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{5,250}', issued) or issued == DYNAMIC_CLIENT:
        raise ModelConnectionError('OpenAI 动态注册未返回应用 client_id，连接尚未完成')
    if attempt.get('client_id') and not hmac.compare_digest(issued, attempt['client_id']):
        raise ModelConnectionError('返回的 client_id 与本次所选 ChatGPT 注册不匹配')
    key = _organization_key(attempt['organization_id'])
    # Preserve registration even if a one-time authorization code expires.
    with _lock(key):
        store = _load(key)
        if store.get('authorization_epoch', 0) != attempt.get('authorization_epoch'):
            raise AuthorizationRequired('本次授权已被退出或新的连接操作作废，请重新连接')
        profiles = store.setdefault('profiles', {})
        profile = profiles.setdefault(attempt['profile_id'], {'client_id': issued})
        if profile.get('client_id') != issued:
            raise ModelConnectionError('此连接的应用注册身份发生变化')
        profile['client_id'] = issued
        _save(key, store)
    data = _token_request({'grant_type': 'authorization_code', 'client_id': issued,
                           'code': code, 'code_verifier': attempt['verifier'],
                           'redirect_uri': attempt['redirect_uri'], 'resource': RESOURCE})
    if not isinstance(data.get('id_token'), str):
        raise ModelConnectionError('OpenAI 未返回可验证的 ID token，未启用连接')
    claims = _verify_identity(data['id_token'], issued, attempt['nonce'])
    fields = _token_fields(data, allow_identity_only=True)
    with _lock(key):
        store = _load(key)
        if store.get('authorization_epoch', 0) != attempt.get('authorization_epoch'):
            raise AuthorizationRequired('本次授权已被退出或新的连接操作作废，未保存返回的授权')
        profile = store['profiles'][attempt['profile_id']]
        if profile.get('subject') and (profile['subject'] != claims['sub'] or profile.get('issuer') != claims['iss']):
            raise ModelConnectionError('重新授权的账户身份与所选连接不符，原连接已保留')
        # An identity-only sign-in must not retain an earlier plan token or proof.
        _clear_tokens(profile)
        profile.update(fields)
        profile.update({'issuer': claims['iss'], 'subject': claims['sub'],
                        'email': claims.get('email', ''), 'name': claims.get('name', ''),
                        'user_id': attempt['user_id'], 'connected_at': time.time(), 'oidc_nonce': attempt['nonce']})
        profile.pop('last_error', None)
        store['active_profile'] = attempt['profile_id']
        _save(key, store)
    return connection_status(attempt['organization_id'])


def _active(store: dict) -> dict:
    return store.get('profiles', {}).get(store.get('active_profile'), {})


def _clear_tokens(profile: dict):
    for field in ('access_token', 'refresh_token', 'id_token', 'expires_at', 'scopes',
                  'inference_completed_at', 'last_inference'):
        profile.pop(field, None)


def _access_token(organization_id: str) -> tuple[str, str]:
    key = _organization_key(organization_id)
    # API and all worker processes share this file lock: rotating refresh tokens cannot race.
    with _lock(key):
        store = _load(key)
        profile = _active(store)
        if not profile.get('access_token') or not profile.get('subject'):
            raise AuthorizationRequired('请先在模型接入页面选择“Continue with ChatGPT”并完成本人授权')
        if PLAN_SCOPE not in profile.get('scopes', []) or 'resource.invoke' not in profile.get('scopes', []):
            raise AuthorizationRequired('已登录 ChatGPT，但未授权使用计划用量；请在模型设置中启用')
        if profile.get('expires_at', 0) <= time.time() + 60:
            if not profile.get('refresh_token'):
                raise AuthorizationRequired('ChatGPT 授权已过期，请重新连接')
            try:
                data = _token_request({'grant_type': 'refresh_token', 'client_id': profile['client_id'],
                                       'refresh_token': profile['refresh_token'], 'resource': RESOURCE})
                if not isinstance(data.get('refresh_token'), str) or not data['refresh_token']:
                    raise ModelConnectionError('OpenAI 未返回轮换的刷新授权；原记录已保留，请重新连接')
                if isinstance(data.get('id_token'), str):
                    identity = _verify_identity(data['id_token'], profile['client_id'], profile['oidc_nonce'], refreshing=True)
                    if identity['sub'] != profile['subject'] or identity['iss'] != profile['issuer']:
                        raise ModelConnectionError('刷新授权的账户身份发生变化，原连接已保留')
                profile.update(_token_fields(data, profile))
                _save(key, store)
            except AuthorizationRequired:
                _clear_tokens(profile)
                _save(key, store)
                raise
        if PLAN_SCOPE not in profile.get('scopes', []) or 'resource.invoke' not in profile.get('scopes', []):
            raise AuthorizationRequired('更新后的授权未包含 ChatGPT 计划用量权限，请重新连接')
        return profile['access_token'], profile.get('selected_model', '')


def connection_status(organization_id: str | None = None) -> dict:
    store = _load(_organization_key(organization_id)) if organization_id else {}
    profile = _active(store)
    credentials = bool((profile.get('access_token') or profile.get('id_token')) and profile.get('subject'))
    permission = credentials and bool(profile.get('access_token')) and PLAN_SCOPE in profile.get('scopes', []) and 'resource.invoke' in profile.get('scopes', [])
    expired = bool(profile.get('access_token')) and profile.get('expires_at', 0) <= time.time() and not profile.get('refresh_token')
    if expired:
        status, message = 'authorization_required', 'ChatGPT 授权已过期，请重新连接'
    elif permission:
        status = 'connected'
        message = 'ChatGPT 计划用量已授权；尚未验证真实任务推理。' if not profile.get('inference_completed_at') else '已使用本人授权的 ChatGPT 计划完成真实模型请求。'
    elif credentials:
        status, message = 'plan_permission_required', 'ChatGPT 身份已验证，但未授权计划用量；不会执行模型请求。'
    else:
        status, message = 'authorization_required', '本地个人项目可使用官方动态注册；请在自己的浏览器登录 Plus/Pro 并授权计划用量。'
    # These fields deliberately contain no credentials or authorization URLs.
    return {
        'status': status, 'official_verification': 'verified_official_documentation',
        'checked_at': VERIFICATION_DATE, 'eligibility': 'open_source_or_personal_local_project',
        'registration_mode': 'official_dynamic_public_client',
        'client_registered': bool(profile.get('client_id') or store.get('profiles')),
        'oauth_enabled': True, 'plan_permission': bool(permission),
        'identity_connected': credentials and not expired, 'plan_usage_approved': bool(permission) and not expired,
        'inference_verified': bool(profile.get('inference_completed_at')),
        'inference_completed_at': profile.get('inference_completed_at'),
        'selected_model': profile.get('selected_model', ''),
        'account': {'email': profile.get('email', ''), 'name': profile.get('name', '')} if credentials else None,
        'active_profile': store.get('active_profile'),
        'profiles': [{'id': pid, 'label': p.get('email') or p.get('name') or f'连接 {i + 1}',
                      'connected': bool(p.get('access_token') or p.get('id_token')), 'active': pid == store.get('active_profile')}
                     for i, (pid, p) in enumerate(store.get('profiles', {}).items())],
        'message': message, 'documentation': DOCUMENTATION, 'manage_usage_url': USAGE_URL,
        'paid_fallback': False,
    }


def _assert_current_token(organization_id: str, token: str):
    key = _organization_key(organization_id)
    with _lock(key):
        profile = _active(_load(key))
        if not hmac.compare_digest(profile.get('access_token', ''), token):
            raise AuthorizationRequired('ChatGPT 连接已退出或已切换，本次请求已停止')


def _discard_rejected_token(organization_id: str, token: str):
    key = _organization_key(organization_id)
    with _lock(key):
        store = _load(key)
        if _active(store).get('access_token') == token:
            _clear_tokens(_active(store))
            _save(key, store)


def list_models(organization_id: str) -> list[dict]:
    token, selected = _access_token(organization_id)
    try:
        with _client() as client:
            _assert_current_token(organization_id, token)
            response = client.get(RESOURCE + '/models', headers={'Authorization': 'Bearer ' + token})
    except httpx.HTTPError as exc:
        raise ModelConnectionError('无法读取当前 ChatGPT 账户的模型列表，请稍后重试') from exc
    if response.status_code != 200:
        if response.status_code == 401:
            _discard_rejected_token(organization_id, token)
        _error(response)
    try:
        catalog = response.json()['models']
        models = [{'slug': m['slug'], 'display_name': m.get('display_name', m['slug'])}
                  for m in catalog if m.get('visibility') == 'list' and isinstance(m.get('slug'), str)]
    except (ValueError, TypeError, KeyError) as exc:
        raise ModelConnectionError('OpenAI 返回的账户模型目录格式无效') from exc
    key = _organization_key(organization_id)
    with _lock(key):
        store = _load(key)
        profile = _active(store)
        # A disconnect/account switch while the network call was in flight must not update another profile.
        if profile.get('access_token') == token:
            profile['models'] = models
            profile['models_checked_at'] = time.time()
            if models and selected not in [m['slug'] for m in models]:
                profile['selected_model'] = models[0]['slug']
            elif not models:
                profile.pop('selected_model', None)
            _save(key, store)
    return models


def select_model(organization_id: str, slug: str) -> dict:
    key = _organization_key(organization_id)
    with _lock(key):
        store = _load(key)
        profile = _active(store)
        if not any(m.get('slug') == slug for m in profile.get('models', [])):
            raise AuthorizationRequired('请选择当前 ChatGPT 账户目录中的模型，或先刷新模型列表')
        profile['selected_model'] = slug
        _save(key, store)
    return connection_status(organization_id)


def select_profile(organization_id: str, profile_id: str) -> dict:
    key = _organization_key(organization_id)
    with _lock(key):
        store = _load(key)
        if profile_id not in store.get('profiles', {}):
            raise AuthorizationRequired('所选 ChatGPT 连接不存在')
        store['active_profile'] = profile_id
        store['authorization_epoch'] = int(store.get('authorization_epoch', 0)) + 1
        _save(key, store)
    return connection_status(organization_id)


def disconnect(organization_id: str) -> dict:
    key = _organization_key(organization_id)
    confirmed = False
    with _lock(key):
        store = _load(key)
        profile = _active(store)
        if profile.get('refresh_token'):
            try:
                with _client() as client:
                    meta = client.get(DISCOVERY)
                    meta.raise_for_status()
                    discovery = meta.json()
                    endpoint = discovery.get('revocation_endpoint', '')
                    target = urlsplit(endpoint)
                    if discovery.get('issuer') != ISSUER or target.scheme != 'https' or target.netloc != 'auth.openai.com' or target.username or target.password or target.fragment:
                        raise ValueError('untrusted revocation endpoint')
                    response = client.post(endpoint, data={'token': profile['refresh_token'],
                                                          'token_type_hint': 'refresh_token',
                                                          'client_id': profile['client_id']})
                    confirmed = response.status_code == 200
            except (httpx.HTTPError, ValueError, TypeError):
                pass
        _clear_tokens(profile)
        store['authorization_epoch'] = int(store.get('authorization_epoch', 0)) + 1
        _save(key, store)
    return {'remote_revocation_confirmed': confirmed, 'message': '已退出，OpenAI 可续期会话已撤销。' if confirmed else '已清除本地授权；远程撤销未确认，请在 ChatGPT 设置中断开本应用。', 'connection': connection_status(organization_id)}


def _stream_error(event: dict, request_id: str = ''):
    error = event.get('error') or event.get('response', {}).get('error') or {}
    code = error.get('code', '') if isinstance(error, dict) else ''
    if code == 'subscription_sharing_usage_unavailable':
        raise QuotaExhausted('OpenAI 暂时无法检查 ChatGPT 计划用量，任务已暂停；保留授权，请稍后手动恢复。')
    if code == 'subscription_sharing_usage_limit_exceeded':
        raise QuotaExhausted('ChatGPT 计划或应用使用额度已达上限，任务已暂停；请查看 ChatGPT 用量设置。')
    if code:
        raise ModelConnectionError('ChatGPT 模型请求未完成', code=re.sub(r'[^A-Za-z0-9_.-]', '', str(code))[:100], http_status=200, request_id=request_id)
    raise ModelConnectionError('ChatGPT 模型请求未完成，未将部分输出当成交付成果')


def execute_response(organization_id: str, *, instructions: str, input_text: str) -> tuple[str, dict]:
    token, model = _access_token(organization_id)
    if not model:
        raise AuthorizationRequired('ChatGPT 计划已授权；请先在模型接入页面刷新并选择账户可用模型')
    body = {'model': model, 'instructions': instructions,
            'input': [{'role': 'user', 'content': input_text}], 'store': False, 'stream': True}
    chunks, terminal, size, request_id, usage, response_id = [], False, 0, '', {}, ''
    try:
        with _client() as client:
            _assert_current_token(organization_id, token)
            with client.stream('POST', RESOURCE + '/responses', json=body,
                               headers={'Authorization': 'Bearer ' + token, 'Accept': 'text/event-stream'}) as response:
                request_id = re.sub(r'[^A-Za-z0-9_.-]', '', response.headers.get('x-request-id', ''))[:160]
                if response.status_code != 200:
                    response.read()
                    if response.status_code == 401:
                        _discard_rejected_token(organization_id, token)
                    _error(response)
                data_lines = []
                for line in response.iter_lines():
                    # An explicit disconnect/account switch stops an in-flight stream
                    # as soon as the next event arrives; no partial result is delivered.
                    _assert_current_token(organization_id, token)
                    if line.startswith('data:'):
                        data_lines.append(line[5:].lstrip())
                        if sum(map(len, data_lines)) > 2_000_000:
                            raise ModelConnectionError('单个模型事件超过本地安全上限')
                    elif not line and data_lines:
                        raw = '\n'.join(data_lines)
                        data_lines = []
                        if raw == '[DONE]':
                            continue
                        try:
                            event = json.loads(raw)
                        except ValueError as exc:
                            raise ModelConnectionError('OpenAI 模型事件格式无效') from exc
                        if not isinstance(event, dict):
                            raise ModelConnectionError('OpenAI 模型事件格式无效')
                        kind = event.get('type')
                        if kind == 'response.output_text.delta':
                            delta = event.get('delta', '')
                            if not isinstance(delta, str):
                                raise ModelConnectionError('OpenAI 文本事件格式无效')
                            size += len(delta)
                            if size > 1_000_000:
                                raise ModelConnectionError('模型输出超过本地文档上限，任务已中断')
                            chunks.append(delta)
                        elif kind in ('response.failed', 'response.incomplete', 'error'):
                            _stream_error(event, request_id)
                        elif kind == 'response.completed':
                            terminal = True
                            usage = event.get('response', {}).get('usage', {})
                            response_id = str(event.get('response', {}).get('id', ''))[:200]
                            break
    except httpx.HTTPError as exc:
        raise ModelConnectionError('OpenAI 模型连接中断；未将部分文本当作完成成果') from exc
    if not terminal:
        raise ModelConnectionError('模型流缺少 response.completed；未交付部分结果')
    _assert_current_token(organization_id, token)
    text = ''.join(chunks).strip()
    if not text:
        raise ModelConnectionError('模型已结束但没有返回文本成果')
    metrics = {'model': model, 'request_id': request_id, 'response_id': response_id, **({k: v for k, v in usage.items() if k in ('input_tokens', 'output_tokens', 'total_tokens') and isinstance(v, int)} if isinstance(usage, dict) else {})}
    key = _organization_key(organization_id)
    with _lock(key):
        store = _load(key)
        profile = _active(store)
        if profile.get('access_token') == token:
            profile['inference_completed_at'] = time.time()
            profile['last_inference'] = metrics
            _save(key, store)
    return text, metrics
