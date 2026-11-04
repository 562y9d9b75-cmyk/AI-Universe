"""Official OAuth contract integration against a mock authority, never paid APIs."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import stat
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest

from app import model_auth as auth
from app.providers import ChatGPTPlanProvider, Context, connection_status


@pytest.fixture
def authority(tmp_path, monkeypatch):
    root = tmp_path / 'model-auth'
    root.mkdir(mode=0o700)
    monkeypatch.setattr(auth, '_root', lambda: root)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({'kid': 'test-signing-key', 'alg': 'RS256', 'use': 'sig'})
    calls, settings = [], {'scope': auth.SCOPES, 'events': None, 'refreshes': 0}

    def signed(nonce, **overrides):
        claims = {'iss': auth.ISSUER, 'sub': 'verified-subject', 'aud': 'oaiapp_aiu_test',
                  'iat': int(time.time()), 'exp': int(time.time()) + 3600,
                  'nonce': nonce, 'email': 'owner@example.test', 'name': '测试用户'}
        claims.update(overrides)
        if nonce is None: claims.pop('nonce',None)
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'test-signing-key'})

    def handle(request):
        calls.append(request)
        url = str(request.url)
        if url == auth.DISCOVERY:
            return httpx.Response(200, json={'issuer': auth.ISSUER, 'authorization_endpoint': auth.AUTHORIZE,
                                            'token_endpoint': auth.TOKEN, 'jwks_uri': auth.JWKS,
                                            'revocation_endpoint': auth.ISSUER + '/oauth/revoke'})
        if url == auth.JWKS:
            return httpx.Response(200, json={'keys': [jwk]})
        if url == auth.TOKEN:
            data = parse_qs(request.content.decode())
            if data['grant_type'] == ['refresh_token']:
                settings['refreshes'] += 1
                if settings.get('refresh_error'):
                    return httpx.Response(settings.get('refresh_status', 400), json={'error': settings['refresh_error']})
                return httpx.Response(200, json={'access_token': 'fresh-access', 'refresh_token': 'rotated-refresh',
                                                'token_type': 'Bearer', 'expires_in': 3600, 'scope': settings['scope']})
            if settings.get('exchange_error'):
                return httpx.Response(400, json={'error': settings['exchange_error']})
            token = settings.get('id_token') or signed(settings['nonce'])
            data = {'access_token': 'test-access', 'refresh_token': 'test-refresh', 'token_type': 'Bearer',
                    'expires_in': 3600, 'scope': settings['scope'], 'id_token': token}
            if settings.get('identity_only'):
                data = {'id_token': token, 'scope': 'openid profile email'}
            return httpx.Response(200, json=data)
        if url == auth.RESOURCE + '/models':
            assert request.headers['authorization'].startswith('Bearer ')
            return httpx.Response(200, json={'models': [
                {'slug': 'test-visible', 'display_name': '测试模型', 'visibility': 'list'},
                {'slug': 'test-hidden', 'visibility': 'hidden'}]})
        if url == auth.RESOURCE + '/responses':
            if settings.get('response_status'):
                return httpx.Response(settings['response_status'], json={'error': {'code': settings['response_error']}}, headers={'x-request-id': 'req-limit'})
            events = settings['events'] or [
                {'type': 'response.output_text.delta', 'delta': '# 真实模型测试成果'},
                {'type': 'response.completed', 'response': {'id': 'resp-test', 'usage': {'input_tokens': 12, 'output_tokens': 7, 'total_tokens': 19}}}]
            return httpx.Response(200, headers={'x-request-id': 'req-test'},
                                  text=''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events))
        if url == auth.ISSUER + '/oauth/revoke':
            return httpx.Response(settings.get('revoke_status', 200))
        raise AssertionError('Unexpected or non-official request: ' + url)

    monkeypatch.setattr(auth, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handle)))
    return {'settings': settings, 'calls': calls, 'root': root, 'signed': signed}


def start(authority, **kwargs):
    result = auth.begin_authorization('org-a', 'owner-a', **kwargs)
    query = {k: v[0] for k, v in parse_qs(urlsplit(result['authorization_url']).query).items()}
    authority['settings']['nonce'] = query['nonce']
    return result, query


def connect(authority, **kwargs):
    _, q = start(authority, **kwargs)
    return auth.complete_authorization({'state': q['state'], 'code': 'test-one-time-code', 'client_id': 'oaiapp_aiu_test'})


def test_official_dynamic_pkce_persistent_host_and_protected_storage(authority):
    first, q = start(authority)
    assert q['client_id'] == auth.DYNAMIC_CLIENT
    assert q['agent_name_hint'] == 'AI Universe'
    assert q['resource'] == auth.RESOURCE
    assert q['redirect_uri'].startswith('http://127.0.0.1:')
    pending = auth._load('attempt:' + q['state'])
    digest = hashlib.sha256(pending['verifier'].encode()).digest()
    assert q['code_challenge'] == base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    _, again = start(authority)
    assert q['ext_agent_host_id'] == again['ext_agent_host_id']
    assert q['state'] != again['state'] and q['nonce'] != again['nonce']
    assert not authority['calls']  # Preparing OAuth never makes an inference or HTTP request.
    for p in authority['root'].iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_callback_identity_scopes_catalog_and_completed_response(authority):
    status = connect(authority)
    assert status['status'] == 'connected' and status['identity_connected'] and status['plan_usage_approved']
    assert not status['inference_verified']
    assert 'test-access' not in json.dumps(status)
    assert 'test-refresh' not in json.dumps(status)
    models = auth.list_models('org-a')
    assert models == [{'slug': 'test-visible', 'display_name': '测试模型'}]
    provider = ChatGPTPlanProvider()
    output = provider.execute(Context('任务', '输入材料', '可验收', '市场研究员', organization_id='org-a'), 'document')
    assert '成果' in output
    request = next(r for r in authority['calls'] if str(r.url).endswith('/responses'))
    data = json.loads(request.content)
    assert data['store'] is False and data['stream'] is True and isinstance(data['input'], list)
    assert set(data) == {'model', 'instructions', 'input', 'store', 'stream'}
    assert provider.last_usage == {'model': 'test-visible', 'request_id': 'req-test', 'response_id': 'resp-test',
                                   'input_tokens': 12, 'output_tokens': 7, 'total_tokens': 19}
    assert auth.connection_status('org-a')['inference_verified']
    wrapper = connection_status('org-a')
    assert wrapper['paid_fallback'] is False and wrapper['local']['status'] == 'ready'
    assert auth.connection_status('org-b')['status'] == 'authorization_required'


def test_state_expiry_denial_and_replay_cannot_exchange(authority):
    _, q = start(authority)
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': 'wrong' * 12, 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    with pytest.raises(auth.AuthorizationRequired):
        auth.complete_authorization({'state': q['state'], 'error': 'access_denied'})
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    _, q = start(authority)
    pending = auth._load('attempt:' + q['state']);pending['expires_at'] = 1;auth._save('attempt:' + q['state'], pending)
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    assert not authority['calls']


@pytest.mark.parametrize('claim,value', [('nonce', 'different'), ('aud', 'other-client'), ('iss', 'https://attacker.example'), ('exp', 1)])
def test_signed_id_token_claims_are_verified(authority, claim, value):
    _, q = start(authority)
    authority['settings']['id_token'] = authority['signed'](q['nonce'], **{claim: value}) if claim != 'nonce' else authority['signed'](value)
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    assert not auth.connection_status('org-a')['identity_connected']


def test_invalid_signature_is_rejected(authority):
    _, q = start(authority)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    payload = {'iss': auth.ISSUER, 'sub': 'forged', 'aud': 'oaiapp_aiu_test', 'nonce': q['nonce'],
               'iat': int(time.time()), 'exp': int(time.time()) + 3600}
    authority['settings']['id_token'] = jwt.encode(payload, other_key, algorithm='RS256', headers={'kid': 'test-signing-key'})
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    assert not auth.connection_status('org-a')['identity_connected']


def test_identity_without_plan_permission_never_invokes_model(authority):
    authority['settings']['identity_only'] = True
    status = connect(authority)
    assert status['identity_connected'] and not status['plan_usage_approved']
    assert status['status'] == 'plan_permission_required'
    with pytest.raises(auth.AuthorizationRequired):
        auth.execute_response('org-a', instructions='test', input_text='test')
    assert not any(str(r.url).endswith('/responses') for r in authority['calls'])


def test_issued_registration_retained_after_exchange_failure_and_signout(authority):
    authority['settings']['exchange_error'] = 'invalid_grant'
    with pytest.raises(auth.AuthorizationRequired):
        connect(authority)
    _, q = start(authority)
    assert q['client_id'] == 'oaiapp_aiu_test' and 'agent_name_hint' not in q
    assert 'client_secret' not in q
    authority['settings'].pop('exchange_error')
    connect(authority)
    result = auth.disconnect('org-a')
    assert result['remote_revocation_confirmed']
    _, q = start(authority)
    assert q['client_id'] == 'oaiapp_aiu_test' and 'id_token_hint' not in q
    assert not auth.connection_status('org-a')['identity_connected']


def test_refresh_is_serialized_across_workers_and_rotates_credentials(authority):
    connect(authority)
    key = auth._organization_key('org-a');store = auth._load(key)
    auth._active(store)['expires_at'] = 1;auth._save(key, store)
    with ThreadPoolExecutor(max_workers=4) as executor:
        tokens = list(executor.map(lambda _: auth._access_token('org-a')[0], range(4)))
    assert tokens == ['fresh-access'] * 4 and authority['settings']['refreshes'] == 1
    assert auth._active(auth._load(key))['refresh_token'] == 'rotated-refresh'
    request = next(r for r in authority['calls'] if str(r.url) == auth.TOKEN and b'refresh_token' in r.content)
    data = parse_qs(request.content.decode())
    assert data['client_id'] == ['oaiapp_aiu_test'] and 'scope' not in data


def test_temporary_refresh_preserves_session_terminal_error_clears_tokens(authority):
    connect(authority)
    key = auth._organization_key('org-a');store = auth._load(key)
    auth._active(store)['expires_at'] = 1;auth._save(key, store)
    authority['settings'].update(refresh_error='temporarily_unavailable', refresh_status=503)
    with pytest.raises(auth.ModelConnectionError):auth._access_token('org-a')
    assert auth._active(auth._load(key))['refresh_token'] == 'test-refresh'
    authority['settings'].update(refresh_error='invalid_grant', refresh_status=400)
    with pytest.raises(auth.AuthorizationRequired):auth._access_token('org-a')
    assert 'access_token' not in auth._active(auth._load(key))
    assert auth._active(auth._load(key))['client_id'] == 'oaiapp_aiu_test'


def test_returning_client_and_account_mismatch_are_rejected(authority):
    connect(authority)
    _, q = start(authority)
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'another-client'})
    _, q = start(authority)
    authority['settings']['id_token'] = authority['signed'](q['nonce'], sub='different-account')
    with pytest.raises(auth.ModelConnectionError):
        auth.complete_authorization({'state': q['state'], 'code': 'code'})
    assert auth._active(auth._load(auth._organization_key('org-a')))['subject'] == 'verified-subject'


@pytest.mark.parametrize('events,exception', [
    ([{'type': 'response.output_text.delta', 'delta': 'partial'}], auth.ModelConnectionError),
    ([{'type': 'response.output_text.delta', 'delta': 'partial'}, {'type': 'response.incomplete'}], auth.ModelConnectionError),
    ([{'type': 'response.output_text.delta', 'delta': 'partial'}, {'type': 'response.failed', 'response': {'error': {'code': 'subscription_sharing_usage_limit_exceeded'}}}], auth.QuotaExhausted),
    ([{'type': 'response.failed', 'response': {'error': {'code': 'subscription_sharing_usage_unavailable'}}}], auth.QuotaExhausted),
])
def test_partial_or_failed_stream_is_not_a_successful_delivery(authority, events, exception):
    connect(authority);auth.list_models('org-a')
    authority['settings']['events'] = events
    provider = ChatGPTPlanProvider();provider.last_usage = {'previous': 'must-clear'}
    with pytest.raises(exception):
        provider.execute(Context('任务', '材料', '标准', '研究员', organization_id='org-a'), 'document')
    assert provider.last_usage == {} and not auth.connection_status('org-a')['inference_verified']


def test_quota_http_error_and_no_ambient_paid_fallback(authority, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'never-use-this-paid-key')
    monkeypatch.setenv('ACCESS_TOKEN', 'never-use-ambient-token')
    with pytest.raises(auth.AuthorizationRequired):
        auth.execute_response('org-a', instructions='test', input_text='test')
    assert not authority['calls']
    connect(authority);auth.list_models('org-a')
    authority['settings'].update(response_status=429, response_error='subscription_sharing_usage_limit_exceeded')
    with pytest.raises(auth.QuotaExhausted):
        auth.execute_response('org-a', instructions='test', input_text='test')
    assert all(r.headers.get('authorization') != 'Bearer never-use-this-paid-key' for r in authority['calls'])


def test_plan_prompt_requires_real_named_employee_dag(authority):
    connect(authority);auth.list_models('org-a')
    ChatGPTPlanProvider().execute(Context('目标', '材料', '标准', 'CEO', organization_id='org-a',
                                        collaborators=[{'id': 'a1', 'role': '研究员'}, {'id': 'a2', 'role': '分析师'}],
                                        role_instructions='如实汇报'), 'plan')
    body = json.loads(next(r for r in reversed(authority['calls']) if str(r.url).endswith('/responses')).content)
    assert 'depends_on' in body['instructions'] and '至少使用两个不同员工' in body['instructions']
    assert 'a1' in body['input'][0]['content'] and '如实汇报' in body['instructions']


def test_untrusted_redirect_and_model_are_rejected(authority):
    for uri in ('http://localhost:3000/api/model/chatgpt/callback', 'https://evil.example/callback',
                'http://127.0.0.1:3000/other-path', 'http://127.0.0.1:3000/api/model/chatgpt/callback?x=1'):
        with pytest.raises(ValueError):auth.begin_authorization('org-a', 'owner-a', redirect_uri=uri)
    connect(authority);auth.list_models('org-a')
    with pytest.raises(auth.AuthorizationRequired):auth.select_model('org-a', 'not-a-catalog-model')


def test_disconnect_invalidates_pending_and_inflight_authorization(authority, monkeypatch):
    _, q = start(authority)
    auth.disconnect('org-a')
    with pytest.raises(auth.AuthorizationRequired):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    assert not authority['calls']
    _, q = start(authority)
    original = auth._token_request
    def disconnect_during_exchange(data):
        response = original(data)
        auth.disconnect('org-a')
        return response
    monkeypatch.setattr(auth, '_token_request', disconnect_during_exchange)
    with pytest.raises(auth.AuthorizationRequired):
        auth.complete_authorization({'state': q['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    assert not auth.connection_status('org-a')['identity_connected']


def test_latest_authorization_attempt_supersedes_previous(authority):
    _, first = start(authority)
    _, second = start(authority)
    with pytest.raises(auth.AuthorizationRequired):
        auth.complete_authorization({'state': first['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    auth.complete_authorization({'state': second['state'], 'code': 'code', 'client_id': 'oaiapp_aiu_test'})
    assert auth.connection_status('org-a')['identity_connected']


def test_refresh_id_token_may_omit_nonce_but_cannot_change_identity(authority):
    connect(authority)
    token=authority['signed'](None)
    claims=auth._verify_identity(token,'oaiapp_aiu_test','original-nonce',refreshing=True)
    assert claims['sub']=='verified-subject'
    with pytest.raises(auth.ModelConnectionError):
        auth._verify_identity(token,'oaiapp_aiu_test','original-nonce')
    with pytest.raises(auth.ModelConnectionError):
        auth._verify_identity(authority['signed']('wrong-nonce'),'oaiapp_aiu_test','expected',refreshing=True)


def test_disconnected_token_is_not_admitted_to_new_requests(authority):
    connect(authority)
    token, _ = auth._access_token('org-a')
    auth.disconnect('org-a')
    with pytest.raises(auth.AuthorizationRequired):auth._assert_current_token('org-a', token)


def test_reauthorization_without_plan_removes_old_tokens_and_proof(authority):
    connect(authority)
    auth.list_models('org-a')
    auth.execute_response('org-a',instructions='岗位职责',input_text='测试材料')
    assert auth.connection_status('org-a')['inference_verified']
    authority['settings']['identity_only']=True
    state=connect(authority)
    assert state['identity_connected'] and not state['plan_usage_approved']
    assert not state['inference_verified']
    stored=auth._active(auth._load('organization:org-a'))
    assert 'access_token' not in stored and 'refresh_token' not in stored
    with pytest.raises(auth.AuthorizationRequired):
        auth.execute_response('org-a',instructions='岗位职责',input_text='不可调用')


def test_server_revocation_blocks_later_requests_until_reauthorization(authority):
    connect(authority);auth.list_models('org-a')
    authority['settings'].update(response_status=401,response_error='invalid_token')
    with pytest.raises(auth.AuthorizationRequired):
        auth.execute_response('org-a',instructions='岗位',input_text='材料')
    assert not auth.connection_status('org-a')['identity_connected']
    count=len(authority['calls'])
    with pytest.raises(auth.AuthorizationRequired):
        auth.execute_response('org-a',instructions='岗位',input_text='材料')
    assert len(authority['calls'])==count
