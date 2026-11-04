"""The web API binds owner actions to their workspace and returns no credentials."""
from urllib.parse import parse_qs, urlsplit
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app import model_auth as auth
from app.model_routes import router
from app.security import authenticated


@pytest.fixture
def web(tmp_path, monkeypatch):
    root=tmp_path/'oauth'; root.mkdir()
    monkeypatch.setattr(auth,'_root',lambda:root)
    monkeypatch.setenv('AIU_ORIGIN','http://localhost:3012')
    app=FastAPI(); app.include_router(router)
    app.dependency_overrides[authenticated]=lambda:{'organization_id':'owner-org','user_id':'owner-user'}
    with TestClient(app) as client:
        yield client,app


def test_start_uses_frontend_loopback_port_and_binds_owner(web):
    client,_=web
    response=client.post('/api/model/chatgpt/start',json={'enable_plan':True})
    assert response.status_code==200
    data=response.json(); assert set(data)=={'authorization_url','expires_at'}
    url=urlsplit(data['authorization_url']); q=parse_qs(url.query)
    assert url.scheme=='https' and url.netloc=='auth.openai.com'
    assert q['redirect_uri']==['http://127.0.0.1:3012/api/model/chatgpt/callback']
    pending=auth._load('attempt:'+q['state'][0])
    assert pending['organization_id']=='owner-org' and pending['user_id']=='owner-user'
    assert q['code_challenge_method']==['S256']
    assert client.post('/api/model/chatgpt/start',json={'organization_id':'foreign-org'}).status_code==422


def test_model_controls_use_authenticated_org_only(web,monkeypatch):
    client,_=web; calls=[]
    monkeypatch.setattr(auth,'list_models',lambda org:calls.append(org) or [{'slug':'allowed','display_name':'可用模型'}])
    monkeypatch.setattr(auth,'connection_status',lambda org:{'selected_model':'allowed'})
    monkeypatch.setattr(auth,'select_model',lambda org,slug:calls.append((org,slug)) or {'selected_model':slug})
    assert client.get('/api/model/chatgpt/models').json()['selected_model']=='allowed'
    assert client.post('/api/model/chatgpt/select',json={'model':'allowed'}).status_code==200
    assert calls==['owner-org',('owner-org','allowed')]
    assert client.post('/api/model/chatgpt/select',json={'model':'allowed','organization_id':'foreign-org'}).status_code==422


def test_controls_require_owner_but_callback_uses_one_shot_state(web,monkeypatch):
    client,app=web
    def denied(): raise HTTPException(401,'请先登录')
    app.dependency_overrides[authenticated]=denied
    for method,path in [('GET','models'),('POST','start'),('POST','disconnect')]:
        assert client.request(method,'/api/model/chatgpt/'+path).status_code==401
    seen=[]
    monkeypatch.setattr(auth,'complete_authorization',lambda query:seen.append(query) or {
        'identity_connected':True,'status':'connected','message':'已验证 <script>不执行</script>'})
    response=client.get('/api/model/chatgpt/callback?code=private-code&state=private-state')
    assert response.status_code==200
    assert seen==[{'code':'private-code','state':'private-state'}]
    assert 'private-code' not in response.text and 'private-state' not in response.text
    assert '&lt;script&gt;' in response.text and '<script>' not in response.text
    assert response.headers['cache-control']=='no-store'
    assert response.headers['referrer-policy']=='no-referrer'


def test_unauthorized_and_quota_failures_are_explicit(web,monkeypatch):
    client,_=web
    def unavailable(org):raise auth.AuthorizationRequired('未获得授权')
    monkeypatch.setattr(auth,'list_models',unavailable)
    assert client.get('/api/model/chatgpt/models').status_code==409
    def quota(org):raise auth.QuotaExhausted('额度已用尽，任务暂停')
    monkeypatch.setattr(auth,'list_models',quota)
    assert client.get('/api/model/chatgpt/models').status_code==429
