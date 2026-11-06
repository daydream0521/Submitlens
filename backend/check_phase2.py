import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from docx import Document
from pypdf import PdfWriter
from backend.app import main

class Phase2(unittest.TestCase):
    def test_stale_and_ai_replacement(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'DB_PATH', Path(folder)/'test.db'), TestClient(main.app) as client:
            p=client.post('/api/projects',json={'name':'回归','kind':'contest'}).json()
            base='/api/projects/'+p['id']
            client.put(base+'/task',json={'task_source':'paste','task_text':'提交视频'})
            item={'title':'视频','description':'提交视频','source_ref':'段落 1','quote':'提交视频'}
            manual=client.post(base+'/requirements',json=item).json()
            client.post(base+'/confirm')
            client.put(base+'/task',json={'task_source':'paste','task_text':'提交文档'})
            old=client.post(base+'/confirm').json()[0]
            self.assertTrue(old['stale']);self.assertFalse(old['confirmed'])
            client.put(base+'/requirements/'+manual['id'],json=dict(item,title='文档',quote='提交文档'))
            self.assertTrue(client.post(base+'/confirm').json()[0]['confirmed'])
            item=dict(item,quote='提交文档')
            def fake(*a,**kw):return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps({'requirements':[item]})}}]}).encode())
            with patch.dict(os.environ,{'LLM_API_KEY':'test-only'}),patch.object(main,'urlopen',fake):
                first=client.post(base+'/extract').json()[0]
                self.assertEqual(client.post(base+'/extract').status_code,409)
                self.assertEqual(client.post(base+'/extract?replace_ai_drafts=true').status_code,200)
                rows=client.get(base+'/requirements').json()
                self.assertEqual(len(rows),2);self.assertIn(manual['id'],[r['id'] for r in rows]);self.assertNotIn(first['id'],[r['id'] for r in rows])
                ai=next(r for r in rows if r['id']!=manual['id'])
                client.put(base+'/requirements/'+ai['id'],json=item)
                client.post(base+'/extract?replace_ai_drafts=true')
                self.assertIn(ai['id'],[r['id'] for r in client.get(base+'/requirements').json()])
                client.post(base+'/confirm')
                client.put(base+'/task',json={'task_source':'paste','task_text':'提交文档\n'})
                client.post(base+'/extract?replace_ai_drafts=true')
                self.assertIn(ai['id'],[r['id'] for r in client.get(base+'/requirements').json()])

    def test_flow(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'DB_PATH', Path(folder)/'test.db'):
            with TestClient(main.app) as client:
                p=client.post('/api/projects',json={'name':'阶段二','kind':'contest'}).json()
                base='/api/projects/'+p['id']
                def upload(name,data): return client.post(base+'/task-file',files={'file':(name,data)})
                text='MP4 5–8 分钟，至少 2 分钟 AI 协同过程。\n\nPDF ≤30 页，至少 3 组 Prompt 迭代。'
                for name in ['task.txt','task.md']:
                    r=upload(name,text.encode());self.assertEqual(r.status_code,200);self.assertEqual(r.json()['task_text'],text)
                doc=Document();doc.add_paragraph(text);buffer=io.BytesIO();doc.save(buffer)
                self.assertEqual(upload('task.docx',buffer.getvalue()).status_code,200)
                # Minimal PDF text stream, no external fixture or OCR.
                from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
                writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
                font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
                page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
                stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 200 Td (Submit MP4 5-8 minutes) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
                buffer=io.BytesIO();writer.write(buffer)
                r=upload('task.pdf',buffer.getvalue());self.assertEqual(r.status_code,200);self.assertEqual(r.json()['task_segments'][0]['ref'],'第 1 页')
                before=client.get(base).json()['task_text']
                self.assertEqual(upload('bad.pdf',b'broken').status_code,422)
                self.assertEqual(client.get(base).json()['task_text'],before)
                self.assertEqual(upload('huge.txt',b'x'*(50*1024*1024+1)).status_code,413)
                client.put(base+'/task',json={'task_source':'paste','task_text':text})
                with patch.dict(os.environ,{'LLM_API_KEY':''}): self.assertEqual(client.post(base+'/extract').status_code,503)
                item={'title':'视频','description':text,'source_ref':'段落 1','quote':'MP4 5–8 分钟','constraints':[{'type':'video_duration','value':'5–8 分钟','quote':'5–8 分钟'}]}
                response={'choices':[{'message':{'content':json.dumps({'requirements':[item]})}}]}
                def fake(*args,**kwargs):return io.BytesIO(json.dumps(response).encode())
                with patch.dict(os.environ,{'LLM_API_KEY':'test-only'}),patch.object(main,'urlopen',fake):
                    r=client.post(base+'/extract');self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()[0]['confirmed'])
                    response['choices'][0]['message']['content']=json.dumps({'requirements':[dict(item,quote='不存在')]})
                    pending=client.post(base+'/extract?replace_ai_drafts=true');self.assertEqual(pending.status_code,200)
                    self.assertTrue(pending.json()[0]['source_issues'])
                    self.assertFalse(client.post(base+'/confirm').json()[0]['confirmed'])
                    client.delete(base+'/requirements/'+pending.json()[0]['id'])
                    response['choices'][0]['message']['content']=json.dumps({'requirements':[item]})
                    client.post(base+'/extract')
                    response['choices'][0]['message']['content']='{"requirements":[]}'
                    self.assertEqual(client.post(base+'/extract').status_code,502)
                with patch.dict(os.environ,{'LLM_API_KEY':'test-only'}),patch.object(main,'urlopen',side_effect=OSError('offline')):
                    self.assertEqual(client.post(base+'/extract').status_code,502)
                manual=client.post(base+'/requirements',json=dict(item,title='文档')).json()
                self.assertFalse(manual['confirmed'])
                client.post(base+'/confirm')
                self.assertTrue(all(x['confirmed'] for x in client.get(base+'/requirements').json()))
                r=client.put(base+'/requirements/'+manual['id'],json=dict(item,title='改名'))
                self.assertFalse(r.json()['confirmed'])
            with TestClient(main.app) as client:
                self.assertEqual(len(client.get(base+'/requirements').json()),2)
                self.assertEqual(client.get(base).json()['task_text'],text)
                client.delete(base+'/requirements/'+manual['id'])
                self.assertEqual(len(client.get(base+'/requirements').json()),1)
                original=client.get(base+'/requirements').json()[0]
                parts=client.post(base+'/requirements-transform',json={'ids':[original['id']],'items':[item,dict(item,title='拆出要求')]}).json()
                self.assertEqual(len(parts),2)
                self.assertTrue(all(not r['confirmed'] for r in parts))
                merged=client.post(base+'/requirements-transform',json={'ids':[r['id'] for r in parts],'items':[item]})
                self.assertEqual(merged.status_code,200)
                self.assertEqual(len(client.get(base+'/requirements').json()),1)

if __name__=='__main__':unittest.main()
