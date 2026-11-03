import hashlib,hmac,secrets,time
from fastapi import HTTPException,Request
from sqlalchemy import select
from .db import LoginSession,User,Session
def password_hash(password):
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),310000).hex()
def check_password(password,stored):
    salt,digest=stored.split(':')
    return hmac.compare_digest(digest,hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),310000).hex())
def token_hash(t):return hashlib.sha256(t.encode()).hexdigest()
def authenticated(request:Request):
    with Session() as s:
        session=s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(request.cookies.get('aiu_session','')),LoginSession.expires_at>time.time()))
        if not session:raise HTTPException(401,'请先登录个人工作空间')
        user=s.get(User,session.user_id)
        if not user:raise HTTPException(401,'会话无效')
        return {'user_id':user.id,'organization_id':session.organization_id,'username':user.username,'session_id':session.id}
