"""SQL-backed state is authoritative; Redis is a notification transport."""
import os, uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, String, Text, Integer, Float, JSON, ForeignKey, Index, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
ROOT=Path(__file__).resolve().parents[2]
_data_path=Path(os.getenv('AIU_DATA_DIR', str(ROOT/'.data')))
DATA=(_data_path if _data_path.is_absolute() else ROOT/_data_path).resolve()
DATA.mkdir(parents=True,exist_ok=True)
URL=os.getenv('AIU_DATABASE_URL','sqlite:///'+str(DATA/'local.db'))
engine=create_engine(URL,pool_pre_ping=True,connect_args={'check_same_thread':False,'timeout':30} if URL.startswith('sqlite') else {})
if engine.dialect.name=='sqlite':
    @event.listens_for(engine,'connect')
    def configure_sqlite(connection,record):
        connection.isolation_level=None
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=30000')
    @event.listens_for(engine,'begin')
    def serialize_sqlite_transaction(connection):
        # SQLite lacks FOR UPDATE; reserve the writer before admission/control reads.
        connection.exec_driver_sql('BEGIN IMMEDIATE')
Session=sessionmaker(engine,expire_on_commit=False)
def uid():return str(uuid.uuid4())
def now():return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase):pass
class Record(Base):
    __abstract__=True
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    organization_id:Mapped[str]=mapped_column(String(36),index=True)
    created_at:Mapped[str]=mapped_column(String(40),default=now)
class Organization(Base):
    __tablename__='organizations'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name:Mapped[str]=mapped_column(String(200))
    description:Mapped[str]=mapped_column(Text,default='')
    settings:Mapped[dict]=mapped_column(JSON,default=lambda:{'daily_limit':100,'concurrency':3,'max_rounds':5,'timeout':120})
    created_at:Mapped[str]=mapped_column(String(40),default=now)
class User(Record):
    __tablename__='users'
    username:Mapped[str]=mapped_column(String(100),unique=True)
    password_hash:Mapped[str]=mapped_column(Text)
class LoginSession(Record):
    __tablename__='sessions'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    token_hash:Mapped[str]=mapped_column(String(64),unique=True)
    expires_at:Mapped[float]=mapped_column(Float)
class Department(Record):
    __tablename__='departments'
    name:Mapped[str]=mapped_column(String(200))
    description:Mapped[str]=mapped_column(Text,default='')
class Agent(Record):
    __tablename__='agents'
    name:Mapped[str]=mapped_column(String(100))
    role:Mapped[str]=mapped_column(String(200))
    department_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    manager_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    responsibilities:Mapped[str]=mapped_column(Text,default='')
    goals:Mapped[str]=mapped_column(Text,default='')
    skills:Mapped[list]=mapped_column(JSON,default=list)
    permissions:Mapped[list]=mapped_column(JSON,default=lambda:['documents'])
    appearance:Mapped[dict]=mapped_column(JSON,default=dict)
class AgentSkill(Record):
    __tablename__='agent_skills'
    agent_id:Mapped[str]=mapped_column(ForeignKey('agents.id'))
    name:Mapped[str]=mapped_column(String(100))
class AgentPermission(Record):
    __tablename__='agent_permissions'
    agent_id:Mapped[str]=mapped_column(ForeignKey('agents.id'))
    name:Mapped[str]=mapped_column(String(100))
class Project(Record):
    __tablename__='projects'
    name:Mapped[str]=mapped_column(String(200))
    description:Mapped[str]=mapped_column(Text,default='')
class Task(Record):
    __tablename__='tasks'
    title:Mapped[str]=mapped_column(String(300))
    input:Mapped[str]=mapped_column(Text,default='')
    criteria:Mapped[str]=mapped_column(Text,default='交付可打开的文件并由老板审核')
    agent_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    project_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    parent_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    provider:Mapped[str]=mapped_column(String(30),default='local')
    operation:Mapped[str]=mapped_column(String(30),default='document')
    formats:Mapped[list]=mapped_column(JSON,default=lambda:['md'])
    status:Mapped[str]=mapped_column(String(30),default='queued',index=True)
    review_required:Mapped[int]=mapped_column(Integer,default=1)
    max_calls:Mapped[int]=mapped_column(Integer,default=5)
    budget_cents:Mapped[int]=mapped_column(Integer,default=0)
    deadline:Mapped[str|None]=mapped_column(String(40),nullable=True)
    attempts:Mapped[int]=mapped_column(Integer,default=0)
    output:Mapped[str]=mapped_column(Text,default='')
    feedback:Mapped[str]=mapped_column(Text,default='')
    error:Mapped[str]=mapped_column(Text,default='')
    lease_until:Mapped[float]=mapped_column(Float,default=0)
    active_run_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
class TaskDependency(Record):
    __tablename__='task_dependencies'
    task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id'))
    depends_on_id:Mapped[str]=mapped_column(ForeignKey('tasks.id'))
    __table_args__=(Index('dependency_unique','task_id','depends_on_id',unique=True),)
class TaskRun(Record):
    __tablename__='task_runs'
    task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id'),index=True)
    agent_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='running')
    input:Mapped[str]=mapped_column(Text,default='')
    output:Mapped[str]=mapped_column(Text,default='')
    finished_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
class AgentMessage(Record):
    __tablename__='agent_messages'
    task_id:Mapped[str]=mapped_column(String(36))
    from_agent_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    to_agent_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    content:Mapped[str]=mapped_column(Text)
    artifact_ids:Mapped[list]=mapped_column(JSON,default=list)
class Artifact(Record):
    __tablename__='artifacts'
    task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id'))
    run_id:Mapped[str]=mapped_column(ForeignKey('task_runs.id'))
    name:Mapped[str]=mapped_column(String(200))
    format:Mapped[str]=mapped_column(String(20))
    path:Mapped[str]=mapped_column(Text)
    preview:Mapped[str]=mapped_column(Text)
    version:Mapped[int]=mapped_column(Integer)
    sha256:Mapped[str]=mapped_column(String(64))
    size:Mapped[int]=mapped_column(Integer)
class Memory(Record):
    __tablename__='memories'
    scope:Mapped[str]=mapped_column(String(20))
    scope_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    content:Mapped[str]=mapped_column(Text)
    source:Mapped[str]=mapped_column(Text)
    confidence:Mapped[float]=mapped_column(Float,default=0.5)
    verified:Mapped[int]=mapped_column(Integer,default=0)
class KnowledgeItem(Record):
    __tablename__='knowledge_items'
    title:Mapped[str]=mapped_column(String(200))
    content:Mapped[str]=mapped_column(Text)
    source:Mapped[str]=mapped_column(Text)
class Approval(Record):
    __tablename__='approvals'
    task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id'))
    run_id:Mapped[str]=mapped_column(String(36))
    status:Mapped[str]=mapped_column(String(30),default='pending')
    feedback:Mapped[str]=mapped_column(Text,default='')
class UsageRecord(Record):
    __tablename__='usage_records'
    task_id:Mapped[str]=mapped_column(String(36))
    agent_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    provider:Mapped[str]=mapped_column(String(30))
    units:Mapped[int]=mapped_column(Integer,default=1)
    cost_cents:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(30))
    # Provider-reported response/model/token counters; never auth credentials.
    metrics:Mapped[dict]=mapped_column(JSON,default=dict)
class AuditLog(Record):
    __tablename__='audit_logs'
    action:Mapped[str]=mapped_column(String(100))
    target_id:Mapped[str]=mapped_column(String(36),default='')
    detail:Mapped[str]=mapped_column(Text,default='')
class OfficeAsset(Record):
    __tablename__='office_assets'
    name:Mapped[str]=mapped_column(String(200))
    uri:Mapped[str]=mapped_column(Text)
    license:Mapped[str]=mapped_column(Text)
class EmployeeAnimation(Record):
    __tablename__='employee_animations'
    agent_id:Mapped[str]=mapped_column(ForeignKey('agents.id'))
    state:Mapped[str]=mapped_column(String(40),default='idle')
    changed_at:Mapped[str]=mapped_column(String(40),default=now)
RESOURCES={'departments':Department,'agents':Agent,'projects':Project,'tasks':Task,'task_dependencies':TaskDependency,'task_runs':TaskRun,'agent_messages':AgentMessage,'artifacts':Artifact,'memories':Memory,'knowledge_items':KnowledgeItem,'approvals':Approval,'usage_records':UsageRecord,'audit_logs':AuditLog,'office_assets':OfficeAsset,'employee_animations':EmployeeAnimation}
def serialize(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in ['password_hash','token_hash','path']}
def audit(s,org,action,target='',detail=''):s.add(AuditLog(organization_id=org,action=action,target_id=target,detail=detail))
