from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'submitlens.sqlite3'


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
    return dict(row)


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
    return Response(status_code=204)


@app.put('/api/projects/{project_id}/task')
def save_task(project_id: str, body: TaskEdit):
    with connect() as db:
        project(db, project_id)
        db.execute('UPDATE projects SET task_text=?, task_source=?, updated_at=? WHERE id=?',
                   (body.task_text, body.task_source, timestamp(), project_id))
        return project(db, project_id)
