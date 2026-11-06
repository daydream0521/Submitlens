import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import UploadFile, HTTPException
from fastapi.testclient import TestClient
from backend.app import main

class Phase3(unittest.TestCase):
    def test_process_restart(self):
        from backend.check_phase1 import start, request
        from urllib.request import Request, urlopen
        with tempfile.TemporaryDirectory() as folder:
            server=start(Path(folder)/'restart.db')
            try:
                p=request('/projects','POST',{'name':'重启成果','kind':'contest'})
                base='/projects/'+p['id']
                r=request(base+'/requirements','POST',{'title':'视频','description':'演示视频'})
                body=b'--boundary\r\nContent-Disposition: form-data; name="files"; filename="demo.mp4"\r\nContent-Type: video/mp4\r\n\r\nactual file bytes\r\n--boundary--\r\n'
                with urlopen(Request('http://127.0.0.1:8011/api'+base+'/artifacts?requirement_id='+r['id'],data=body,headers={'Content-Type':'multipart/form-data; boundary=boundary'})) as response:
                    import json
                    a=json.load(response)[0]
                request(base+'/requirements/'+r['id']+'/artifacts/'+a['id'],'PUT',{'selected':True})
                server.terminate();server.wait();server=start(Path(folder)/'restart.db')
                files=request(base+'/artifacts')
                self.assertEqual(files[0]['requirements'],[{'requirement_id':r['id'],'selected':1}])
                with urlopen('http://127.0.0.1:8011/api'+base+'/artifacts/'+a['id']+'/content') as response:self.assertEqual(response.read(),b'actual file bytes')
            finally:server.terminate();server.wait()

    def test_files_and_links(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main,'DB_PATH',Path(folder)/'test.db'):
            with TestClient(main.app) as c:
                p=c.post('/api/projects',json={'name':'成果','kind':'contest'}).json();base='/api/projects/'+p['id']
                def req(title,constraints=[]):return c.post(base+'/requirements',json={'title':title,'description':title,'constraints':constraints}).json()['id']
                r1,r2=req('环境配置说明'),req('复现指南')
                count=req('截图', [{'type':'file_count','value':'2','quote':'2'}])
                c.post(base+'/confirm')
                unchanged_requirements=c.get(base+'/requirements').json()
                def upload(name,body,query=''):
                    response=c.post(base+'/artifacts'+query,files={'files':(name,body)})
                    self.assertEqual(response.status_code,201,response.text)
                    return response.json()[0]['id']
                def bind(rid,aid,selected=False):
                    response=c.put(base+'/requirements/'+rid+'/artifacts/'+aid,json={'selected':selected})
                    self.assertEqual(response.status_code,200)
                shared=upload('README.md',b'doc')
                bind(r1,shared);bind(r1,shared);bind(r2,shared)
                self.assertEqual(len(c.get(base+'/artifacts').json()[0]['requirements']),2)
                c.delete(base+'/requirements/'+r2+'/artifacts/'+shared)
                self.assertEqual(c.get(base+'/artifacts/'+shared+'/content').content,b'doc')
                self.assertEqual(len(c.get(base+'/artifacts').json()[0]['requirements']),1)
                bind(r2,shared)
                old=upload('demo.mp4',b'old','?requirement_id='+r1)
                final=upload('demo.mp4',b'final','?requirement_id='+r1)
                self.assertEqual(c.get(base+'/artifacts/'+old+'/content').content,b'old')
                self.assertEqual(c.get(base+'/artifacts/'+final+'/content').content,b'final')
                bind(r1,old,True);bind(r1,final,True)
                c.put(base+'/requirements/'+r1+'/artifacts/'+final,json={})
                files=c.get(base+'/artifacts').json()
                selected=lambda rows,r:[a['id'] for a in rows if any(l['requirement_id']==r and l['selected'] for l in a['requirements'])]
                self.assertEqual(selected(files,r1),[final])
                bind(count,old,True);bind(count,final,True)
                self.assertEqual(len(selected(c.get(base+'/artifacts').json(),count)),2)
                replaced=upload('new.mp4',b'new','?replace_id='+final)
                self.assertNotEqual(replaced,final)
                self.assertEqual(selected(c.get(base+'/artifacts').json(),r1),[])
                bind(r1,replaced,True)
                c.delete(base+'/artifacts/'+replaced)
                self.assertEqual(selected(c.get(base+'/artifacts').json(),r1),[])
                self.assertEqual(c.get(base+'/artifacts/'+old+'/content').content,b'old')
                with patch.object(main,'artifact_limit',return_value=3):
                    before=len(c.get(base+'/artifacts').json())
                    response=c.post(base+'/artifacts',files=[('files',('small.txt',b'ok')),('files',('large.txt',b'too big'))])
                    self.assertEqual(response.status_code,413)
                    self.assertEqual(len(c.get(base+'/artifacts').json()),before)
                self.assertEqual(len(list((Path(folder)/'artifacts').iterdir())),len(c.get(base+'/artifacts').json()))
                file=UploadFile(file=io.BytesIO(b'broken'),filename='partial.zip')
                original=file.read; calls=0
                async def fail_read(n):
                    nonlocal calls
                    calls+=1
                    if calls==2:raise OSError('interrupted upload')
                    return await original(2)
                file.read=fail_read
                with self.assertRaises(OSError):asyncio.run(main.upload_artifacts(p['id'],[file],r1))
                self.assertEqual(len(list((Path(folder)/'artifacts').iterdir())),len(c.get(base+'/artifacts').json()))
                self.assertEqual(c.get(base+'/requirements').json(),unchanged_requirements)
                self.assertEqual(c.get(base).json()['task_text'],'')
                other=c.post('/api/projects',json={'name':'其他','kind':'course'}).json()['id']
                self.assertEqual(c.put('/api/projects/'+other+'/requirements/'+r1+'/artifacts/'+old,json={'selected':True}).status_code,404)
            with TestClient(main.app) as c:
                self.assertEqual(len(c.get(base+'/artifacts').json()),2)
                self.assertEqual(c.get(base+'/artifacts/'+old+'/content').content,b'old')
                self.assertEqual(len(next(a for a in c.get(base+'/artifacts').json() if a['id']==shared)['requirements']),2)
                c.delete(base)
                self.assertEqual(list((Path(folder)/'artifacts').iterdir()),[])
                with main.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM requirement_artifacts').fetchone()[0],0)

if __name__=='__main__':unittest.main()
