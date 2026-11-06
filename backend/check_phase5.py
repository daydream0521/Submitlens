import asyncio,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import main

class Export(unittest.TestCase):
 def test_zip_report_freshness(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'DB_PATH',Path(folder)/'test.db'):
   with TestClient(main.app) as c:
    p=c.post('/api/projects',json={'name':'交付','kind':'contest'}).json();base='/api/projects/'+p['id']
    c.put(base+'/task',json={'task_source':'paste','task_text':'提交说明'})
    body={'title':'说明','description':'提交说明','quote':'提交说明','needs_manual_review':True,'constraints':[{'type':'extension','value':'MD','quote':'MD'}]}
    r=c.post(base+'/requirements',json=body).json()['id'];r2=c.post(base+'/requirements',json=dict(body,title='复现')).json()['id']
    c.post(base+'/confirm')
    def upload(name,data):return c.post(base+'/artifacts',files={'files':(name,data)}).json()[0]['id']
    a,b=upload('README.md',b'first'),upload('README.md',b'second')
    for rid in (r,r2):c.put(base+'/requirements/'+rid+'/artifacts/'+a,json={'selected':True})
    c.post(base+'/check');c.put(base+'/requirements/'+r+'/review',json={'decision':'pass','note':'已检查说明'})
    c.post(base+'/requirements',json={'title':'未确认','description':'草稿'})
    def export(ids):
     response=c.post(base+'/export',json={'artifact_ids':ids});self.assertEqual(response.status_code,200,response.text if response.status_code!=200 else '')
     return zipfile.ZipFile(io.BytesIO(response.content))
    def current():return c.get(base).json()
    with export([a,a,b]) as z:
     self.assertEqual(len(z.namelist()),3)
     self.assertEqual(z.read('materials/'+a+'/README.md'),b'first');self.assertEqual(z.read('materials/'+b+'/README.md'),b'second')
     report=z.read('submission_report.md').decode()
     for text in ('人工确认符合','已检查说明','待复核','未确认','实际打包文件','验收选定文件','未解决项','系统检查'):self.assertIn(text,report)
    self.assertTrue(current()['last_export_at']);self.assertFalse(current()['export_outdated'])
    upload('candidate.txt',b'not selected');self.assertFalse(current()['export_outdated'])
    c.put(base+'/requirements/'+r+'/review',json={'decision':'fail'})
    self.assertTrue(current()['export_outdated'])
    with export([b]) as z:self.assertIn('验收关联证据未包含在本次 ZIP',z.read('submission_report.md').decode())
    self.assertFalse(current()['export_outdated'])
    c.post(base+'/check');self.assertTrue(current()['export_outdated'])
    with export([]) as z:self.assertEqual(z.namelist(),['submission_report.md'])
    self.assertFalse(current()['export_outdated'])
    other=c.post('/api/projects',json={'name':'其他','kind':'course'}).json()['id']
    self.assertEqual(c.post('/api/projects/'+other+'/export',json={'artifact_ids':[a]}).status_code,404)
    self.assertEqual(c.post(base+'/export',json={'artifact_ids':['missing']}).status_code,404)
    with main.connect() as db:item=main.get_artifact(db,p['id'],b)
    main.artifact_path(item).unlink()
    self.assertEqual(c.post(base+'/export',json={'artifact_ids':[b]}).status_code,409)
    old=current()['last_export_at']
    with patch.object(main.zipfile.ZipFile,'write',side_effect=OSError('disk full')):
     self.assertEqual(c.post(base+'/export',json={'artifact_ids':[a]}).status_code,500)
    self.assertEqual(current()['last_export_at'],old)
    self.assertEqual(list((Path(folder)/'export-temp').iterdir()),[])
    c.put(base+'/requirements/'+r,json=body);self.assertTrue(current()['export_outdated'])
    export([]).close();self.assertFalse(current()['export_outdated'])
    replaced=c.post(base+'/artifacts?replace_id='+a,files={'files':('replacement.md',b'new evidence')})
    self.assertEqual(replaced.status_code,201);self.assertTrue(current()['export_outdated'])
   with TestClient(main.app) as c:self.assertTrue(c.get(base).json()['export_outdated'])
 def test_restart_freshness(self):
  from backend.check_phase1 import start,request
  from urllib.request import Request,urlopen
  with tempfile.TemporaryDirectory() as folder:
   server=start(Path(folder)/'restart.db')
   try:
    p=request('/projects','POST',{'name':'导出重启','kind':'course'});base='/projects/'+p['id']
    def download():
     with urlopen(Request('http://127.0.0.1:8011/api'+base+'/export',data=b'{"artifact_ids":[]}',headers={'Content-Type':'application/json'})) as response:
      with zipfile.ZipFile(io.BytesIO(response.read())) as z:self.assertEqual(z.namelist(),['submission_report.md'])
    download();server.terminate();server.wait();server=start(Path(folder)/'restart.db')
    self.assertIsNotNone(request(base)['last_export_at']);self.assertFalse(request(base)['export_outdated'])
    request(base,'PATCH',{'name':'报告项目名已变'})
    server.terminate();server.wait();server=start(Path(folder)/'restart.db')
    self.assertTrue(request(base)['export_outdated'])
    download();self.assertFalse(request(base)['export_outdated'])
    self.assertEqual(list((Path(folder)/'export-temp').iterdir()),[])
   finally:server.terminate();server.wait()

 def test_disconnect_cleanup(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'DB_PATH',Path(folder)/'test.db'),TestClient(main.app) as c:
   p=c.post('/api/projects',json={'name':'中断','kind':'course'}).json()
   response=main.export_project(p['id'],main.ExportInput())
   async def receive():return {'type':'http.request','body':b'','more_body':False}
   async def send(message):raise OSError('client disconnected')
   with self.assertRaises(OSError):asyncio.run(response({'type':'http','method':'GET','headers':[]},receive,send))
   self.assertFalse(Path(response.path).exists());self.assertIsNone(c.get('/api/projects/'+p['id']).json()['last_export_at'])
   base='/api/projects/'+p['id']
   c.post(base+'/export',json={'artifact_ids':[]})
   old=c.get(base).json()['last_export_at']
   response=main.export_project(p['id'],main.ExportInput())
   async def fail_last(message):
    if message['type']=='http.response.body' and not message.get('more_body',False):raise OSError('final send failed')
   with self.assertRaises(OSError):asyncio.run(response({'type':'http','method':'GET','headers':[]},receive,fail_last))
   self.assertEqual(c.get(base).json()['last_export_at'],old)
   self.assertFalse(Path(response.path).exists())
   response=main.export_project(p['id'],main.ExportInput())
   async def change_while_sending(message):
    if message['type']=='http.response.start':
     with main.connect() as db:
      db.execute('UPDATE projects SET name=? WHERE id=?',('导出期间已修改',p['id']))
      main.mark_export_changed(db,p['id'])
   asyncio.run(response({'type':'http','method':'GET','headers':[]},receive,change_while_sending))
   self.assertTrue(c.get(base).json()['export_outdated'])


if __name__=='__main__':unittest.main()
