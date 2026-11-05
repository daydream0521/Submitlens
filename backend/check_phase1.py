"""阶段 1 HTTP 与进程重启检查，使用临时数据库，不修改用户项目。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(path, method='GET', body=None):
    data = None if body is None else json.dumps(body).encode()
    with urlopen(Request('http://127.0.0.1:8011/api' + path, data=data, method=method,
                         headers={'Content-Type': 'application/json'}), timeout=3) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def start(path):
    code = ('from pathlib import Path; from backend.app import main; '
            f'main.DB_PATH=Path({str(path)!r}); '
            'import uvicorn; uvicorn.run(main.app, host="127.0.0.1", port=8011)')
    process = subprocess.Popen([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1])
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('后端启动失败')
        try:
            request('/health')
            return process
        except (URLError, TimeoutError):
            time.sleep(.1)
    process.terminate()
    process.wait()
    raise RuntimeError('后端启动超时')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'projects.sqlite3'
        server = start(path)
        try:
            contest = request('/projects', 'POST', {'name': '竞赛项目', 'kind': 'contest'})
            course = request('/projects', 'POST', {'name': '课程项目', 'kind': 'course'})
            text = '第一段\n\n第二段\n  保留缩进\n'
            endpoint = '/projects/' + contest['id']
            request(endpoint + '/task', 'PUT', {'task_source': 'paste', 'task_text': text})
            server.terminate()
            server.wait()
            server = start(path)
            assert request(endpoint)['task_text'] == text
            assert {(p['name'], p['kind']) for p in request('/projects')} == {('竞赛项目', 'contest'), ('课程项目', 'course')}
            assert request(endpoint, 'PATCH', {'name': '竞赛改名'})['name'] == '竞赛改名'
            request(endpoint, 'DELETE')
            try:
                request(endpoint)
                raise AssertionError('删除后仍能读取详情')
            except HTTPError as error:
                assert error.code == 404
            assert [p['id'] for p in request('/projects')] == [course['id']]
            print('PASS: 两类项目、重启持久化、换行原文、重命名、删除与 404')
        finally:
            server.terminate()
            server.wait()
