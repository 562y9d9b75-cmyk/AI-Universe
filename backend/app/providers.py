"""No paid API adapter is installed; ambient API credentials are never consumed."""
import csv,io,re,hashlib
from dataclasses import dataclass
class AuthorizationRequired(Exception):pass
class QuotaExhausted(Exception):pass
@dataclass
class Context:
    title:str
    source:str
    criteria:str
    role:str
    feedback:str=''
class LocalProvider:
    name='local'
    def execute(self,c:Context,operation:str):
        source=c.source.strip() or '未提供来源材料。请补充输入后重做。'
        words=re.findall(r'\w+',source)
        stats=f'字符数：{len(source)}；词项数：{len(words)}；非空行：{sum(bool(x.strip()) for x in source.splitlines())}'
        if operation=='analysis':
            try:
                rows=list(csv.reader(io.StringIO(source)))
                numeric=[float(v) for row in rows for v in row if re.fullmatch(r'-?\d+(\.\d+)?',v.strip())]
                stats+=f'\nCSV 行数：{len(rows)}；数值项：{len(numeric)}；数值合计：{sum(numeric):g}'
            except (ValueError,csv.Error):pass
        return f'''# {c.title}

> 本地规则执行结果 · 未使用语言模型 · 不构成已核实的市场结论

## 执行岗位
{c.role}

## 输入与上游交接
{source[:80000]}

## 可复核统计
{stats}
SHA-256：{hashlib.sha256(source.encode()).hexdigest()}

## 验收要求
{c.criteria}

## 修改意见
{c.feedback or '无'}

## 交付说明
本文由本地工具整理提供的材料。未进行外部调研或智能推理；缺失信息需要用户提供或等待模型授权。
'''
class ChatGPTPlanProvider:
    name='chatgpt_plan'
    def execute(self,c,operation):raise AuthorizationRequired('等待官方集成资格、应用注册及 Responses 授权核验；未调用任何模型，也不会切换付费 API。')
PROVIDERS={'local':LocalProvider(),'chatgpt_plan':ChatGPTPlanProvider()}
def connection_status():
    return {'active':'local','paid_fallback':False,'chatgpt_plan':{'status':'authorization_required','official_verification':'blocked_by_environment_network_policy','checked_at':'2026-11-03','client_registered':False,'oauth_enabled':False,'message':'尚未确认官方最新开放资格和注册流程。Plus 不自动等于本应用已获授权。','documentation':['https://developers.openai.com/siwc/quickstart','https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt']},'local':{'status':'ready','message':'确定性文件整理/文本与 CSV 统计，不是 AI 模型'}}
