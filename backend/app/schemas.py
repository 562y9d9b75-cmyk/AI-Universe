from typing import Literal
from pydantic import BaseModel,Field
class Credentials(BaseModel):
    username:str=Field(min_length=2,max_length=80)
    password:str=Field(min_length=12,max_length=200)
    company:str=Field(default='AI Universe',min_length=1,max_length=200)
class TaskInput(BaseModel):
    title:str=Field(min_length=1,max_length=300)
    input:str=Field(default='',max_length=80000)
    criteria:str=Field(default='交付可打开的文件，并由老板审核',min_length=1,max_length=4000)
    agent_id:str|None=None
    project_id:str|None=None
    provider:Literal['local','chatgpt_plan']='local'
    operation:Literal['document','analysis']='document'
    formats:list[Literal['md','docx','xlsx','pptx','pdf','py','html','zip']]=Field(default_factory=lambda:['md'],min_length=1,max_length=8)
    review_required:bool=True
    max_calls:int=Field(default=5,ge=0,le=100)
    budget_cents:int=Field(default=0,ge=0,le=100000)
    deadline:str|None=None
    dependencies:list[str]=Field(default_factory=list,max_length=100)
    mode:Literal['direct','autonomous']='direct'
class ReviewInput(BaseModel):
    decision:Literal['approve','reject']
    feedback:str=Field(default='',max_length=4000)
class MemoryInput(BaseModel):
    scope:Literal['company','department','employee','project']='company'
    scope_id:str|None=None
    content:str=Field(min_length=1,max_length=20000)
    source:str=Field(min_length=1,max_length=1000)
    confidence:float=Field(default=0.5,ge=0,le=1)
    verified:bool=False
