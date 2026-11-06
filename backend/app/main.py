from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import json
import os
from urllib.request import Request, urlopen
from dotenv import load_dotenv
from .tasks import paragraphs, parse_document
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'submitlens.sqlite3'
load_dotenv(Path(__file__).resolve().parents[2] / '.env')


@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
            task_text TEXT NOT NULL DEFAULT '', task_source TEXT NOT NULL DEFAULT 'paste',
            task_filename TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        if 'task_segments' not in [r['name'] for r in db.execute('PRAGMA table_info(projects)')]:
            db.execute("ALTER TABLE projects ADD COLUMN task_segments TEXT NOT NULL DEFAULT '[]'")
        db.execute('''CREATE TABLE IF NOT EXISTS requirements (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, data TEXT NOT NULL)''')
    yield


app = FastAPI(lifespan=lifespan)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    kind: Literal['contest', 'course']


class ProjectEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    kind: Literal['contest', 'course'] | None = None


class TaskEdit(BaseModel):
    task_source: Literal['paste']
    task_text: str


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def project(db, project_id):
    row = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '项目不存在，请返回项目列表')
    result = dict(row)
    result['task_segments'] = json.loads(result['task_segments'])
    return result


def name_value(name):
    if not name.strip():
        raise HTTPException(422, '请输入项目名称')
    return name.strip()


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/projects')
def projects():
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY updated_at DESC')]


@app.post('/api/projects', status_code=201)
def create(body: ProjectCreate):
    project_id, now = str(uuid4()), timestamp()
    with connect() as db:
        db.execute('INSERT INTO projects (id,name,kind,created_at,updated_at) VALUES (?,?,?,?,?)',
                   (project_id, name_value(body.name), body.kind, now, now))
        return project(db, project_id)


@app.get('/api/projects/{project_id}')
def get(project_id: str):
    with connect() as db:
        return project(db, project_id)


@app.patch('/api/projects/{project_id}')
def edit(project_id: str, body: ProjectEdit):
    with connect() as db:
        old = project(db, project_id)
        db.execute('UPDATE projects SET name=?, kind=?, updated_at=? WHERE id=?',
                   (name_value(body.name) if body.name is not None else old['name'],
                    body.kind or old['kind'], timestamp(), project_id))
        return project(db, project_id)


@app.delete('/api/projects/{project_id}', status_code=204)
def delete(project_id: str):
    with connect() as db:
        project(db, project_id)
        db.execute('DELETE FROM projects WHERE id=?', (project_id,))
        db.execute('DELETE FROM requirements WHERE project_id=?', (project_id,))
    return Response(status_code=204)


@app.put('/api/projects/{project_id}/task')
def save_task(project_id: str, body: TaskEdit):
    with connect() as db:
        old = project(db, project_id)
        segments = old['task_segments'] if body.task_text == old['task_text'] else paragraphs(body.task_text)
        source = old['task_source'] if body.task_text == old['task_text'] else 'paste'
        db.execute('UPDATE projects SET task_text=?, task_source=?, task_filename=?, task_segments=?, updated_at=? WHERE id=?',
                   (body.task_text, source, old['task_filename'] if source == 'file' else None, json.dumps(segments), timestamp(), project_id))
        if body.task_text != old['task_text']:
            unconfirm(db, project_id)
        return project(db, project_id)


def unconfirm(db, project_id):
    for row in db.execute('SELECT id,data FROM requirements WHERE project_id=?', (project_id,)).fetchall():
        item = json.loads(row['data'])
        item['confirmed'] = False
        db.execute('UPDATE requirements SET data=? WHERE id=?', (json.dumps(item), row['id']))


@app.post('/api/projects/{project_id}/task-file')
async def task_file(project_id: str, file: UploadFile):
    with connect() as db:
        project(db, project_id)
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(413, '文件超过 50 MB，请缩小后重试')
    try:
        text, segments = parse_document(file.filename or '', bytes(data))
        if not text.strip():
            raise ValueError('未读取到文字，请粘贴文本或更换可复制文字的文件')
    except Exception as error:
        raise HTTPException(422, f'无法解析文件：{error}。请更换文件或粘贴文本') from error
    with connect() as db:
        project(db, project_id)
        db.execute('UPDATE projects SET task_text=?,task_source=?,task_filename=?,task_segments=?,updated_at=? WHERE id=?',
                   (text, 'file', file.filename, json.dumps(segments), timestamp(), project_id))
        unconfirm(db, project_id)
        return project(db, project_id)


class Constraint(BaseModel):
    type: Literal['extension', 'file_count', 'pdf_pages', 'video_duration', 'content']
    value: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class RequirementInput(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = True
    source_ref: str = ''
    quote: str = ''
    constraints: list[Constraint] = []
    needs_manual_review: bool = True


class TransformInput(BaseModel):
    ids: list[str] = Field(min_length=1)
    items: list[RequirementInput] = Field(min_length=1)


@app.post('/api/projects/{project_id}/requirements-transform')
def transform_requirements(project_id: str, body: TransformInput):
    with connect() as db:
        existing = {r['id'] for r in requirements(db, project_id)}
        if not set(body.ids) <= existing:
            raise HTTPException(409, '要求已更改，请刷新后重试')
        for rid in body.ids:
            db.execute('DELETE FROM requirements WHERE id=? AND project_id=?', (rid, project_id))
        return [insert_requirement(db, project_id, item) for item in body.items]


def requirements(db, project_id):
    project(db, project_id)
    return [dict(json.loads(r['data']), id=r['id']) for r in db.execute('SELECT * FROM requirements WHERE project_id=? ORDER BY rowid', (project_id,))]


def insert_requirement(db, project_id, body):
    rid = str(uuid4())
    data = dict(body.model_dump(), confirmed=False)
    db.execute('INSERT INTO requirements VALUES (?,?,?)', (rid, project_id, json.dumps(data)))
    return dict(data, id=rid)


@app.get('/api/projects/{project_id}/requirements')
def list_requirements(project_id: str):
    with connect() as db:
        return requirements(db, project_id)


@app.post('/api/projects/{project_id}/requirements', status_code=201)
def add_requirement(project_id: str, body: RequirementInput):
    with connect() as db:
        project(db, project_id)
        return insert_requirement(db, project_id, body)


@app.put('/api/projects/{project_id}/requirements/{rid}')
def edit_requirement(project_id: str, rid: str, body: RequirementInput):
    with connect() as db:
        if not any(r['id'] == rid for r in requirements(db, project_id)):
            raise HTTPException(404, '要求不存在，请刷新清单')
        data = dict(body.model_dump(), confirmed=False)
        db.execute('UPDATE requirements SET data=? WHERE id=?', (json.dumps(data), rid))
        return dict(data, id=rid)


@app.delete('/api/projects/{project_id}/requirements/{rid}', status_code=204)
def delete_requirement(project_id: str, rid: str):
    with connect() as db:
        project(db, project_id)
        db.execute('DELETE FROM requirements WHERE id=? AND project_id=?', (rid, project_id))
    return Response(status_code=204)


@app.post('/api/projects/{project_id}/confirm')
def confirm_requirements(project_id: str):
    with connect() as db:
        for item in requirements(db, project_id):
            rid = item.pop('id')
            item['confirmed'] = True
            db.execute('UPDATE requirements SET data=? WHERE id=?', (json.dumps(item), rid))
        return requirements(db, project_id)


@app.post('/api/projects/{project_id}/extract')
def extract(project_id: str):
    with connect() as db:
        task = project(db, project_id)
    if not task['task_text'].strip():
        raise HTTPException(422, '请先保存任务说明')
    key = os.getenv('LLM_API_KEY')
    if not key:
        raise HTTPException(503, '未配置 API Key，请手动添加要求')
    schema = RequirementInput.model_json_schema()
    prompt = ('仅提取明确交付要求，按交付物合并。推荐选题、背景、评分不得变成必交。'
              '不要补充常识阈值。出处必须使用给定 ref，quote 必须逐字引用该片段。'
              '每个约束 quote 也必须逐字来自原文；value 保留原文单位，不执行检查。'
              '语义内容需人工复核。仅返回 JSON {"requirements":[...]}，单项结构：' + json.dumps(schema, ensure_ascii=False))
    payload = {'model': os.getenv('LLM_MODEL', 'gpt-4o-mini'), 'messages': [
        {'role': 'system', 'content': prompt}, {'role': 'user', 'content': json.dumps(task['task_segments'] or paragraphs(task['task_text']), ensure_ascii=False)}],
        'response_format': {'type': 'json_object'}}
    try:
        url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/') + '/chat/completions'
        with urlopen(Request(url, data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}), timeout=60) as response:
            raw = json.load(response)
        items = [RequirementInput.model_validate(x) for x in json.loads(raw['choices'][0]['message']['content'])['requirements']]
        if not items:
            raise ValueError('未提取到要求')
        sources = {s['ref']: s['text'] for s in (task['task_segments'] or paragraphs(task['task_text']))}
        for item in items:
            source = sources.get(item.source_ref, '')
            if not item.quote or item.quote not in source or any(c.quote not in source for c in item.constraints):
                raise ValueError('返回要求缺少可定位的原文依据')
    except Exception as error:
        raise HTTPException(502, '整理失败：' + ('返回要求缺少可定位的原文依据' if isinstance(error, ValueError) else '接口请求或响应异常') + '，请重试或手动添加要求') from error
    with connect() as db:
        if project(db, project_id)['task_text'] != task['task_text']:
            raise HTTPException(409, '原文已更新，请重新整理')
        return [insert_requirement(db, project_id, item) for item in items]
