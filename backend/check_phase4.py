import io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from backend.app import main
from backend.app import checks
from backend.app.citations import locate_quote,resolve_sources

class Phase4(unittest.TestCase):
 def test_citations(self):
  segments=[{'ref':'段落 1','text':'演示视频'},{'ref':'段落 2','text':'5–8 分钟'}]
  item=main.RequirementInput(title='视频',description='视频',quote='演示视频',source_ref='伪造',constraints=[{'type':'video_duration','value':'5–8 分钟','quote':'5–8 分钟'}])
  resolve_sources([item],segments)
  self.assertEqual(item.source_ref,'段落 1');self.assertEqual(item.constraints[0].source_ref,'段落 2')
  with self.assertRaises(ValueError):locate_quote('不存在',segments)
  with self.assertRaises(ValueError):locate_quote('视频',segments+[{'ref':'段落 3','text':'视频'}])
  if Path('data/real-extract-response.json').exists():
   raw=json.loads(Path('data/real-extract-response.json').read_text(encoding='utf-8'))
   request=json.loads(Path('data/real-extract-request.json').read_text(encoding='utf-8'))
   source=json.loads(request['messages'][1]['content'])
   items=json.loads(raw['choices'][0]['message']['content'])['requirements']
   unique=ambiguous=0
   for x in items:
    for c in x['constraints']:
     matches=[s for s in source if c['quote'] in s['text']]
     if len(matches)==1:
      self.assertEqual(locate_quote(c['quote'],source),matches[0]['ref']);unique+=1
     elif len(matches)>1:
      with self.assertRaises(ValueError):locate_quote(c['quote'],source)
      ambiguous+=1
   self.assertGreater(unique,0);self.assertGreater(ambiguous,0)
 def test_source_api(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'DB_PATH',Path(folder)/'source.db'),TestClient(main.app) as c:
   p=c.post('/api/projects',json={'name':'出处修复','kind':'contest'}).json();base='/api/projects/'+p['id']
   c.put(base+'/task',json={'task_source':'paste','task_text':'演示视频\n\n5–8 分钟'})
   item={'title':'视频','description':'演示视频','quote':'演示视频','source_ref':'虚构行号','constraints':[{'type':'video_duration','value':'5–8 分钟','quote':'5–8 分钟','source_ref':'虚构页码'}]}
   response={'choices':[{'message':{'content':json.dumps({'requirements':[item]})}}]}
   with patch.dict(os.environ,{'LLM_API_KEY':'local-placeholder'}),patch.object(main,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
    result=c.post(base+'/extract').json()[0]
   self.assertEqual(result['source_ref'],'段落 1');self.assertEqual(result['constraints'][0]['source_ref'],'段落 2')
   with self.assertRaises(ValueError):checks.bounds('5分8秒','video_duration')

 def test_review_process_restart(self):
  from backend.check_phase1 import start,request
  from urllib.request import Request,urlopen
  with tempfile.TemporaryDirectory() as folder:
   server=start(Path(folder)/'restart.db')
   try:
    p=request('/projects','POST',{'name':'复核重启','kind':'course'});base='/projects/'+p['id']
    r=request(base+'/requirements','POST',{'title':'文本','description':'核对内容','needs_manual_review':True})
    request(base+'/confirm','POST')
    body=b'--b\r\nContent-Disposition: form-data; name="files"; filename="readme.txt"\r\n\r\ntext\r\n--b--\r\n'
    with urlopen(Request('http://127.0.0.1:8011/api'+base+'/artifacts',data=body,headers={'Content-Type':'multipart/form-data; boundary=b'})) as response:a=json.load(response)[0]
    request(base+'/requirements/'+r['id']+'/artifacts/'+a['id'],'PUT',{'selected':True})
    request(base+'/check','POST');request(base+'/requirements/'+r['id']+'/review','PUT',{'decision':'pass','note':'已阅读'})
    server.terminate();server.wait();server=start(Path(folder)/'restart.db')
    result=request(base+'/checks');self.assertEqual(result['overall'],'pass');self.assertEqual(result['items'][0]['review_note'],'已阅读')
    request(base+'/artifacts/'+a['id'],'DELETE')
    self.assertEqual(request(base+'/checks')['overall'],'fail')
   finally:server.terminate();server.wait()

 def test_checks_and_mutations(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'DB_PATH',Path(folder)/'test.db'):
   with TestClient(main.app) as c:
    p=c.post('/api/projects',json={'name':'预检','kind':'contest'}).json();base='/api/projects/'+p['id']
    def add(kind,value,manual=False,required=True):
     item={'title':kind,'description':value,'needs_manual_review':manual,'required':required,'constraints':[{'type':kind,'value':value,'quote':value}]}
     r=c.post(base+'/requirements',json=item).json();c.post(base+'/confirm');return r['id'],item
    def upload(rid,name,data):return c.post(base+'/artifacts?requirement_id='+rid,files={'files':(name,data)}).json()[0]['id']
    def choose(rid,aid):c.put(base+'/requirements/'+rid+'/artifacts/'+aid,json={'selected':True})
    def get(rid):return next(x for x in c.get(base+'/checks').json()['items'] if x['id']==rid)
    def run(rid):c.post(base+'/check');return get(rid)
    def pdf(n):
     w=PdfWriter()
     for _ in range(n):w.add_blank_page(width=100,height=100)
     f=io.BytesIO();w.write(f);return f.getvalue()
    rid,body=add('pdf_pages','不超过 30 页')
    self.assertEqual(get(rid)['status'],'unchecked')
    a=upload(rid,'report.pdf',pdf(31));choose(rid,a)
    self.assertEqual(run(rid)['status'],'fail')
    b=upload(rid,'report.pdf',pdf(30));choose(rid,b)
    self.assertEqual(get(rid)['status'],'pass')
    bad=upload(rid,'bad.pdf',b'broken');choose(rid,bad)
    self.assertEqual(get(rid)['status'],'pending')
    c.put(base+'/requirements/'+rid+'/review',json={'decision':'pass'})
    self.assertEqual(get(rid)['status'],'pending')
    choose(rid,b)
    self.assertEqual(get(rid)['status'],'pass')
    c.delete(base+'/requirements/'+rid+'/artifacts/'+b)
    self.assertEqual(get(rid)['status'],'fail')
    vid,video=add('video_duration','5–8 分钟',True)
    video['constraints'].append({'type':'extension','value':'MP4','quote':'MP4格式'})
    c.put(base+'/requirements/'+vid,json=video);c.post(base+'/confirm')
    old=upload(vid,'old.mp4',b'old');new=upload(vid,'new.mp4',b'new')
    with patch.object(checks,'duration',side_effect=lambda path:561 if path.name==old else 432):
     choose(vid,old);self.assertEqual(run(vid)['status'],'fail')
     c.put(base+'/requirements/'+vid+'/review',json={'decision':'pass'})
     self.assertEqual(get(vid)['status'],'fail')
     choose(vid,new);self.assertEqual(get(vid)['status'],'pending')
     c.put(base+'/requirements/'+vid+'/review',json={'decision':'pass','note':'核对内容'})
     self.assertEqual(get(vid)['status'],'pass')
     replaced=c.post(base+'/artifacts?replace_id='+new,files={'files':('replacement.mp4',b'new')}).json()[0]['id']
     self.assertEqual(get(vid)['review_decision'],'pending');self.assertEqual(get(vid)['status'],'fail')
     choose(vid,replaced);self.assertEqual(get(vid)['status'],'pending')
     c.delete(base+'/artifacts/'+replaced);self.assertEqual(get(vid)['status'],'fail')
    count,_=add('file_count','至少 3 组 Prompt 链')
    for n in range(3):choose(count,upload(count,f'{n}.txt',b'content'))
    result=run(count)
    self.assertEqual(result['status'],'pending');self.assertEqual(result['last_check_result'][-1]['status'],'pending')
    valid,_=add('file_count','至少三份文件')
    choose(valid,upload(valid,'a.txt',b'a'))
    self.assertEqual(run(valid)['status'],'fail')
    suggested,_=add('extension','PDF',False,False)
    self.assertNotEqual(run(suggested)['status'],'fail')
    c.put(base+'/requirements/'+vid,json=video)
    self.assertEqual(get(vid)['status'],'excluded')
    c.post(base+'/confirm');self.assertEqual(get(vid)['status'],'unchecked')
   with TestClient(main.app) as c:
    self.assertEqual(get(count)['status'],'pending')
    self.assertEqual(get(vid)['status'],'unchecked')

if __name__=='__main__':unittest.main()
