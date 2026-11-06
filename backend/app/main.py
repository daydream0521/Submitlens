from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import json
import os
from urllib.request import Request, urlopen
from dotenv import load_dotenv
from .tasks import paragraphs, parse_document
from .citations import resolve_sources
from .checks import run_checks, status as check_status
from typing import Literal
from uuid import uuid4
from fastapi.responses import FileResponse

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
        db.execute('''CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL, extension TEXT NOT NULL, bytes INTEGER NOT NULL, uploaded_at TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS requirement_artifacts (
            requirement_id TEXT NOT NULL, artifact_id TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(requirement_id, artifact_id))''')
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
        for artifact in db.execute('SELECT * FROM artifacts WHERE project_id=?', (project_id,)).fetchall():
            remove_artifact(db, dict(artifact))
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
        item['stale'] = True
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
    source_ref: str = ''


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
            db.execute('DELETE FROM requirement_artifacts WHERE requirement_id=?', (rid,))
            db.execute('DELETE FROM requirements WHERE id=? AND project_id=?', (rid, project_id))
        return [insert_requirement(db, project_id, item) for item in body.items]


def requirements(db, project_id):
    project(db, project_id)
    return [dict(json.loads(r['data']), id=r['id']) for r in db.execute('SELECT * FROM requirements WHERE project_id=? ORDER BY rowid', (project_id,))]


def insert_requirement(db, project_id, body, origin="manual"):
    rid = str(uuid4())
    data = dict(body.model_dump(), confirmed=False, stale=False, origin=origin)
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
        data = dict(body.model_dump(), confirmed=False, stale=False, origin="manual")
        db.execute('UPDATE requirements SET data=? WHERE id=?', (json.dumps(data), rid))
        return dict(data, id=rid)


@app.delete('/api/projects/{project_id}/requirements/{rid}', status_code=204)
def delete_requirement(project_id: str, rid: str):
    with connect() as db:
        project(db, project_id)
        if not any(r['id'] == rid for r in requirements(db, project_id)):
            raise HTTPException(404, '要求不存在，请刷新清单')
        db.execute('DELETE FROM requirement_artifacts WHERE requirement_id=?', (rid,))
        db.execute('DELETE FROM requirements WHERE id=? AND project_id=?', (rid, project_id))
    return Response(status_code=204)


@app.post('/api/projects/{project_id}/confirm')
def confirm_requirements(project_id: str):
    with connect() as db:
        for item in requirements(db, project_id):
            rid = item.pop('id')
            if item.get('stale'):
                continue
            item['confirmed'] = True
            item['origin'] = 'reviewed'
            db.execute('UPDATE requirements SET data=? WHERE id=?', (json.dumps(item), rid))
        return requirements(db, project_id)


@app.post('/api/projects/{project_id}/extract')
def extract(project_id: str, replace_ai_drafts: bool = False):
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
        resolve_sources(items, task['task_segments'] or paragraphs(task['task_text']))
    except Exception as error:
        raise HTTPException(502, '整理失败：' + (str(error) if isinstance(error, ValueError) else '接口请求或响应异常，请重试或手动添加要求')) from error
    with connect() as db:
        if project(db, project_id)['task_text'] != task['task_text']:
            raise HTTPException(409, '原文已更新，请重新整理')
        drafts = [r for r in requirements(db, project_id) if r.get('origin') == 'ai' and not r['confirmed']]
        if drafts and not replace_ai_drafts:
            raise HTTPException(409, '已有 AI 草稿，请选择替换未确认 AI 草稿')
        if replace_ai_drafts:
            for draft in drafts:
                db.execute('DELETE FROM requirement_artifacts WHERE requirement_id=?', (draft['id'],))
                db.execute('DELETE FROM requirements WHERE id=?', (draft['id'],))
        return [insert_requirement(db, project_id, item, origin='ai') for item in items]


def artifact_limit(name, content_type=""):
    ext = Path(name).suffix.lower()
    if content_type.startswith('image/') or ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg', '.tif', '.tiff', '.heic'):
        return 20 * 1024 * 1024
    if content_type.startswith('text/') or ext in ('.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.csv', '.ppt', '.pptx', '.xls', '.xlsx', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml', '.xml', '.html', '.css', '.sh'):
        return 50 * 1024 * 1024
    return 1024 * 1024 * 1024


def artifact_path(item):
    return DB_PATH.parent / 'artifacts' / item['stored_path']


def get_artifact(db, project_id, aid):
    project(db, project_id)
    row = db.execute('SELECT * FROM artifacts WHERE id=? AND project_id=?', (aid, project_id)).fetchone()
    if row is None:
        raise HTTPException(404, '文件不存在，请刷新文件库')
    return dict(row)


def get_requirement(db, project_id, rid):
    item = next((r for r in requirements(db, project_id) if r['id'] == rid), None)
    if item is None:
        raise HTTPException(404, '要求不存在，请刷新清单')
    return item


def remove_artifact(db, item):
    artifact_path(item).unlink(missing_ok=True)
    db.execute('DELETE FROM requirement_artifacts WHERE artifact_id=?', (item['id'],))
    db.execute('DELETE FROM artifacts WHERE id=?', (item['id'],))


@app.get('/api/projects/{project_id}/artifacts')
def list_artifacts(project_id: str):
    with connect() as db:
        project(db, project_id)
        result = []
        for row in db.execute('SELECT * FROM artifacts WHERE project_id=? ORDER BY uploaded_at DESC, rowid DESC', (project_id,)):
            item = dict(row)
            item.pop('stored_path')
            item['requirements'] = [dict(r) for r in db.execute('SELECT requirement_id,selected FROM requirement_artifacts WHERE artifact_id=?', (item['id'],))]
            result.append(item)
        return result


@app.post('/api/projects/{project_id}/artifacts', status_code=201)
async def upload_artifacts(project_id: str, files: list[UploadFile], requirement_id: str | None = None, replace_id: str | None = None):
    with connect() as db:
        project(db, project_id)
        if requirement_id:
            get_requirement(db, project_id, requirement_id)
        if replace_id:
            get_artifact(db, project_id, replace_id)
            if len(files) != 1:
                raise HTTPException(422, '替换时请选择一个文件')
    folder = DB_PATH.parent / 'artifacts'
    folder.mkdir(parents=True, exist_ok=True)
    pending = []
    try:
        for file in files:
            name = (file.filename or '未命名文件').replace('\\', '/').rsplit('/', 1)[-1]
            aid = str(uuid4())
            item = {'id': aid, 'project_id': project_id, 'original_name': name, 'stored_path': aid,
                    'extension': Path(name).suffix.lower(), 'bytes': 0, 'uploaded_at': timestamp()}
            pending.append(item)
            limit = artifact_limit(name, file.content_type or "")
            with artifact_path(item).open('wb') as output:
                while chunk := await file.read(1024 * 1024):
                    item['bytes'] += len(chunk)
                    if item['bytes'] > limit:
                        label = '1 GB' if limit == 1024 * 1024 * 1024 else f'{limit // (1024 * 1024)} MB'
                        raise HTTPException(413, f'{name} 超过 {label}，请缩小文件后重试')
                    output.write(chunk)
            if item['bytes'] == 0:
                raise HTTPException(422, f'{name} 是空文件，请更换文件')
        with connect() as db:
            project(db, project_id)
            if requirement_id:
                get_requirement(db, project_id, requirement_id)
            for item in pending:
                db.execute('INSERT INTO artifacts VALUES (:id,:project_id,:original_name,:stored_path,:extension,:bytes,:uploaded_at)', item)
                if requirement_id:
                    db.execute('INSERT INTO requirement_artifacts VALUES (?,?,0)', (requirement_id, item['id']))
            if replace_id:
                old = get_artifact(db, project_id, replace_id)
                for link in db.execute('SELECT requirement_id FROM requirement_artifacts WHERE artifact_id=?', (replace_id,)).fetchall():
                    db.execute('INSERT OR IGNORE INTO requirement_artifacts VALUES (?,?,0)', (link['requirement_id'], pending[0]['id']))
                remove_artifact(db, old)
        return [{k: v for k, v in item.items() if k != 'stored_path'} for item in pending]
    except BaseException:
        for item in pending:
            artifact_path(item).unlink(missing_ok=True)
        raise
    finally:
        for file in files:
            await file.close()


@app.get('/api/projects/{project_id}/artifacts/{aid}/content')
def download_artifact(project_id: str, aid: str):
    with connect() as db:
        item = get_artifact(db, project_id, aid)
    return FileResponse(artifact_path(item), filename=item['original_name'], media_type='application/octet-stream')


@app.delete('/api/projects/{project_id}/artifacts/{aid}', status_code=204)
def delete_artifact(project_id: str, aid: str):
    with connect() as db:
        remove_artifact(db, get_artifact(db, project_id, aid))
    return Response(status_code=204)


class LinkInput(BaseModel):
    selected: bool | None = None


@app.put('/api/projects/{project_id}/requirements/{rid}/artifacts/{aid}')
def bind_artifact(project_id: str, rid: str, aid: str, body: LinkInput):
    with connect() as db:
        item = get_requirement(db, project_id, rid)
        get_artifact(db, project_id, aid)
        multiple = any(c['type'] == 'file_count' for c in item['constraints'])
        if body.selected and not multiple:
            db.execute('UPDATE requirement_artifacts SET selected=0 WHERE requirement_id=?', (rid,))
        if body.selected is None:
            db.execute('INSERT OR IGNORE INTO requirement_artifacts VALUES (?,?,0)', (rid, aid))
        else:
            db.execute('INSERT INTO requirement_artifacts VALUES (?,?,?) ON CONFLICT(requirement_id,artifact_id) DO UPDATE SET selected=excluded.selected',
                       (rid, aid, int(body.selected)))
        selected = db.execute('SELECT selected FROM requirement_artifacts WHERE requirement_id=? AND artifact_id=?', (rid, aid)).fetchone()[0]
    return {'requirement_id': rid, 'artifact_id': aid, 'selected': bool(selected)}


@app.delete('/api/projects/{project_id}/requirements/{rid}/artifacts/{aid}', status_code=204)
def unbind_artifact(project_id: str, rid: str, aid: str):
    with connect() as db:
        get_requirement(db, project_id, rid)
        get_artifact(db, project_id, aid)
        db.execute('DELETE FROM requirement_artifacts WHERE requirement_id=? AND artifact_id=?', (rid, aid))
    return Response(status_code=204)


def selected_files(db, rid):
    return [dict(r) for r in db.execute('SELECT a.* FROM artifacts a JOIN requirement_artifacts ra ON a.id=ra.artifact_id WHERE ra.requirement_id=? AND ra.selected=1', (rid,))]


def persist_requirement(db, rid, item):
    db.execute('UPDATE requirements SET data=? WHERE id=?', (json.dumps({k:v for k,v in item.items() if k != 'id'}), rid))


def check_requirement(db, item):
    now = timestamp()
    item['last_check_result'] = run_checks(item, selected_files(db, item['id']), artifact_path, now)
    item['last_checked_at'] = now
    persist_requirement(db, item['id'], item)


def check_summary(db, project_id):
    items = requirements(db, project_id)
    for item in items:
        item['status'] = check_status(item)
    formal = [i for i in items if i['status'] != 'excluded']
    required = [i for i in formal if i.get('required', True)]
    overall = 'unchecked' if not required else 'fail' if any(i['status']=='fail' for i in required) else 'pending' if any(i['status'] in ('pending','unchecked') for i in required) else 'pass'
    return {'items':items, 'overall':overall, 'counts':{s:sum(i['status']==s for i in formal) for s in ('pass','fail','pending','unchecked')}}


@app.get('/api/projects/{project_id}/checks')
def get_checks(project_id: str):
    with connect() as db:
        return check_summary(db, project_id)


@app.post('/api/projects/{project_id}/check')
def check_project(project_id: str):
    with connect() as db:
        for item in requirements(db, project_id):
            if item.get('confirmed') and not item.get('stale'):
                check_requirement(db, item)
        return check_summary(db, project_id)
