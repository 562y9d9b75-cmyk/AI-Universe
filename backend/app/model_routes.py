"""Owner-only model controls and an OAuth callback bound by one-shot PKCE state."""
import html,os
from typing import Annotated
from urllib.parse import urlsplit
from fastapi import APIRouter,Body,Depends,HTTPException,Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,ConfigDict,Field
from .security import authenticated
from . import model_auth

router=APIRouter(prefix='/api/model/chatgpt',tags=['ChatGPT plan'])
Auth=Annotated[dict,Depends(authenticated)]
class StartInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    enable_plan:bool=False
    new_profile:bool=False
    profile_id:str|None=Field(default=None,max_length=100)
class ModelInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    model:str=Field(min_length=1,max_length=200)
class ProfileInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    profile_id:str=Field(min_length=1,max_length=100)

def _origin():
    value=os.getenv('AIU_ORIGIN','http://localhost:'+os.getenv('AIU_WEB_PORT','3000'))
    parts=urlsplit(value)
    if parts.scheme!='http' or parts.hostname not in ('localhost','127.0.0.1') or parts.username or parts.password:
        raise HTTPException(409,'ChatGPT 本地计划接入需要在本机回环地址启动')
    port=parts.port or 80
    return f'http://{parts.hostname}:{port}',port

def _call(action,*args,**kwargs):
    try:return action(*args,**kwargs)
    except model_auth.AuthorizationRequired as exc:raise HTTPException(409,str(exc)) from None
    except model_auth.QuotaExhausted as exc:raise HTTPException(429,str(exc)) from None
    except model_auth.ModelConnectionError as exc:raise HTTPException(502,str(exc)) from None
    except ValueError as exc:raise HTTPException(422,str(exc)) from None

@router.post('/start')
def start(auth:Auth,data:StartInput=Body(default=StartInput())):
    _,port=_origin()
    return _call(model_auth.begin_authorization,auth['organization_id'],auth['user_id'],
                 redirect_uri=f'http://127.0.0.1:{port}/api/model/chatgpt/callback',**data.model_dump())

@router.get('/models')
def models(auth:Auth):
    items=_call(model_auth.list_models,auth['organization_id'])
    state=model_auth.connection_status(auth['organization_id'])
    return {'models':items,'selected_model':state.get('selected_model','')}

@router.post('/select')
def select(auth:Auth,data:ModelInput):return _call(model_auth.select_model,auth['organization_id'],data.model)

@router.post('/profile')
def profile(auth:Auth,data:ProfileInput):return _call(model_auth.select_profile,auth['organization_id'],data.profile_id)

@router.post('/disconnect')
def disconnect(auth:Auth):return _call(model_auth.disconnect,auth['organization_id'])

@router.get('/callback',response_class=HTMLResponse)
def callback(request:Request):
    # The external OAuth return cannot carry a SameSite=Strict localhost cookie.
    # complete_authorization validates/consumes state bound to the original owner/org.
    ok=False
    try:
        state=model_auth.complete_authorization(dict(request.query_params))
        ok=bool(state.get('identity_connected') or state.get('status') in ['connected','plan_permission_required'])
        message=state.get('message','授权步骤已结束，请返回模型设置查看状态。')
    except (model_auth.AuthorizationRequired,model_auth.QuotaExhausted,model_auth.ModelConnectionError,ValueError) as exc:
        message=str(exc)
    origin,_=_origin()
    title='ChatGPT 授权已返回' if ok else 'ChatGPT 连接未完成'
    body=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{title}</title><style>body{{background:#f3f5ef;color:#1c342d;font:16px system-ui;max-width:620px;margin:12vh auto;padding:32px}}article{{background:white;border:1px solid #dce6dc;border-radius:18px;padding:32px}}p{{line-height:1.9;color:#5d6e63}}a{{display:inline-block;background:#246b5b;color:white;text-decoration:none;padding:12px 22px;border-radius:8px}}</style><article><h1>{title}</h1><p>{html.escape(message)}</p><p>你可以关闭此窗口，回到原来的 AI Universe 页面。只有账户已授予计划用量并完成真实请求后，系统才会标记推理已验证。</p><a href="{html.escape(origin,quote=True)}">返回 AI Universe</a></article></html>'''
    return HTMLResponse(body,status_code=200 if ok else 400,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})
