import io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import main
from backend.app.tasks import parse_document
from backend.app.citations import locate_quote,resolve_draft

class Citations(unittest.TestCase):
 def test_chapter_scope(self):
  text='# 省赛\n## 视频\n视频须为MP4\n5–8 分钟\n# 国赛\n## 视频\n视频须为MP4\n10 分钟'
  _,segments=parse_document('a.md',text.encode())
  self.assertEqual(locate_quote('视频须为MP4',segments,'省赛'),'行 3 / 视频')
  with self.assertRaises(ValueError):locate_quote('视频须为MP4',segments)
  with self.assertRaises(ValueError):locate_quote('10 分钟',segments,'省赛')
  item=main.RequirementInput(title='视频',description='视频须为MP4',quote='视频须为MP4',source_ref='省赛',constraints=[{'type':'video_duration','value':'10 分钟','quote':'10 分钟'}])
  data=resolve_draft(item,segments)
  self.assertEqual(data['source_ref'],'行 3 / 视频');self.assertEqual(data['constraints'][0]['source_ref'],'');self.assertTrue(data['source_issues'])
 def test_partial_drafts_and_real_replay(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(main,'DB_PATH',Path(folder)/'test.db'),TestClient(main.app) as c:
   p=c.post('/api/projects',json={'name':'引用','kind':'contest'}).json();base='/api/projects/'+p['id']
   c.put(base+'/task',json={'task_source':'paste','task_text':'唯一交付条款\n\n重复条款\n\n重复条款'})
   items=[{'title':'有效','description':'唯一交付条款','quote':'唯一交付条款'},{'title':'待处理','description':'重复条款','quote':'重复条款'}]
   def replay(payload):
    raw={'choices':[{'message':{'content':json.dumps({'requirements':payload})}}]}
    with patch.dict(os.environ,{'LLM_API_KEY':'offline-placeholder'}),patch.object(main,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())):
     return c.post(base+'/extract?replace_ai_drafts=true')
   r=replay(items);self.assertEqual(r.status_code,200)
   rows=r.json();self.assertFalse(rows[0]['source_issues']);self.assertTrue(rows[1]['source_issues'])
   confirmed=c.post(base+'/confirm').json();self.assertTrue(confirmed[0]['confirmed']);self.assertFalse(confirmed[1]['confirmed'])
   if not Path('data/real-extract-response.json').exists():return
   raw=json.loads(Path('data/real-extract-response.json').read_text(encoding='utf-8'))
   path=next(Path('test').glob('*.md'))
   with path.open('rb') as f:c.post(base+'/task-file',files={'file':(path.name,f)})
   real=json.loads(raw['choices'][0]['message']['content'])['requirements']
   r=replay(real);self.assertEqual(r.status_code,200)
   ai=r.json();self.assertEqual(len(ai),5);self.assertTrue(all(x['source_issues'] for x in ai))
   video=next(x for x in ai if x['title']=='演示视频')
   choices=next(x for x in video['source_issues'] if x['field']=='source_ref')['matches']
   video['source_ref']=next(x['ref'] for x in choices if x['section'].startswith('省赛安排'))
   result=c.put(base+'/requirements/'+video['id'],json=video).json()
   self.assertFalse(result['source_issues'])
   self.assertTrue(all(int(x['source_ref'].split()[1])<277 for x in result['constraints']))
   c.post(base+'/confirm')
   rows=c.get(base+'/requirements').json();self.assertTrue(next(x for x in rows if x['id']==video['id'])['confirmed'])
   self.assertFalse(next(x for x in rows if x['title']=='作品整体提交')['confirmed'])
   self.assertEqual(c.get(base).json()['task_text'],path.read_bytes().decode('utf-8-sig'))
   print('Offline real replay: 5 editable drafts; province video resolved without national sources')

if __name__=='__main__':unittest.main()
