import { useEffect, useState } from 'react'

type Requirement = {id:string;title:string;confirmed:boolean;stale?:boolean;constraints:{type:string;value:string}[]}
type Artifact = {id:string;original_name:string;extension:string;bytes:number;uploaded_at:string;requirements:{requirement_id:string;selected:boolean}[]}
const size=(n:number)=>n<1024?`${n} B`:n<1024*1024?`${(n/1024).toFixed(1)} KB`:`${(n/1024/1024).toFixed(1)} MB`

export function Artifacts({id}:{id:string}) {
  const [requirements,setRequirements]=useState<Requirement[]>([]),[files,setFiles]=useState<Artifact[]>([])
  const [active,setActive]=useState(''),[picker,setPicker]=useState(false),[filter,setFilter]=useState('all')
  const [busy,setBusy]=useState(false),[progress,setProgress]=useState(''),[error,setError]=useState('')
  const root=`/api/projects/${id}`
  async function request(path:string,method='GET',body?:unknown){
    const r=await fetch(root+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
    if(!r.ok){const e=await r.json();throw new Error(typeof e.detail==='string'?e.detail:'操作失败，请重试')}
    return r.status===204?null:r.json()
  }
  async function refresh(){const [r,a]=await Promise.all([request('/requirements'),request('/artifacts')]);setRequirements(r);setFiles(a)}
  async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();await refresh()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  useEffect(()=>{void run(refresh)},[id])
  useEffect(()=>{if(active)document.getElementById('evidence-'+active)?.scrollIntoView({block:'nearest'})},[active])
  async function upload(list:FileList|null,rid?:string,replace?:string){
    if(!list?.length)return
    const body=new FormData();Array.from(list).forEach(f=>body.append('files',f))
    const query=new URLSearchParams();if(rid)query.set('requirement_id',rid);if(replace)query.set('replace_id',replace)
    await run(async()=>{await new Promise<void>((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open('POST',root+'/artifacts?'+query)
      xhr.upload.onprogress=e=>setProgress(e.lengthComputable?`上传中 ${Math.round(e.loaded/e.total*100)}%`:'上传中…')
      xhr.onload=()=>{if(xhr.status>=200&&xhr.status<300){resolve()}else{let message='上传失败，请重试';try{message=JSON.parse(xhr.responseText).detail||message}catch{}reject(new Error(message))}}
      xhr.onerror=()=>reject(new Error('上传中断，请检查连接后重试'))
      setProgress('上传中…');xhr.send(body)
    })});setProgress('')
  }
  const linked=(rid:string)=>files.filter(f=>f.requirements.some(l=>l.requirement_id===rid))
  const selected=(rid:string)=>files.filter(f=>f.requirements.some(l=>l.requirement_id===rid&&l.selected))
  const formal=requirements.filter(r=>r.confirmed&&!r.stale)
  const covered=formal.filter(r=>selected(r.id).length>0)
  const missing=formal.filter(r=>selected(r.id).length===0)
  const item=requirements.find(r=>r.id===active)
  const link=(rid:string,aid:string,chosen?:boolean)=>run(async()=>{await request(`/requirements/${rid}/artifacts/${aid}`,'PUT',chosen===undefined?{}:{selected:chosen})})
  const input=(label:string,rid?:string,replace?:string)=><label className="upload-control">{label}<input aria-label={label} type="file" multiple={!replace} disabled={busy} onChange={e=>{void upload(e.target.files,rid,replace);e.target.value=''}}/></label>
  return <div className="evidence-workspace">
    <section className="requirements"><header><h2>证据覆盖</h2><p>{covered.length} / {formal.length} 项已有选定文件</p></header>
      <label>筛选<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">全部要求</option><option value="missing">缺少证据</option><option value="covered">已有证据</option></select></label>
      {formal.length===0&&<p>请先在任务要求中确认清单</p>}
      {[["已有选定文件",covered,'covered'],["尚未选定文件",missing,'missing']].map(([title,group,key])=>filter!=='all'&&filter!==key?null:<div key={key as string}><h3>{title as string}</h3>{(group as Requirement[]).map(r=><button key={r.id} className="coverage-row" aria-pressed={active===r.id} onClick={()=>{setActive(r.id);setPicker(false)}}><strong>{r.title}</strong><span>{selected(r.id).length?'已有证据':'缺少证据'}{linked(r.id).length?`，${linked(r.id).length} 个候选文件`:''}</span></button>)}</div>)}
      {requirements.some(r=>!r.confirmed||r.stale)&&<details><summary>草稿与待处理要求</summary>{requirements.filter(r=>!r.confirmed||r.stale).map(r=><button className="coverage-row" key={r.id} onClick={()=>setActive(r.id)}>{r.title}（{r.stale?'原文已变，需处理':'草稿'}）</button>)}</details>}
    </section>
    {error&&<p role="alert" className="error">{error}</p>}{progress&&<p role="status">{progress}</p>}
    {item&&<section className="requirements" id={'evidence-'+item.id}><header><h2>{item.title}</h2><span>{item.stale?'原文已变，需处理':item.confirmed?'待验收':'草稿'}</span></header><div className="row-actions">{input('上传成果',item.id)}<button disabled={busy} onClick={()=>setPicker(!picker)}>从文件库选择</button></div>
      {item.constraints.length>0&&<p>{item.constraints.map(c=>c.value).join('；')}</p>}
      {picker&&<div className="library-picker"><h3>选择已有文件</h3>{files.length===0&&<p>文件库暂无文件</p>}{files.map(f=><div key={f.id} className="evidence-file"><span>{f.original_name}</span><button disabled={busy||linked(item.id).some(x=>x.id===f.id)} onClick={()=>void link(item.id,f.id)}>关联文件</button></div>)}</div>}
      {linked(item.id).length===0&&<p>尚未关联文件</p>}
      {linked(item.id).map(f=>{const chosen=f.requirements.some(l=>l.requirement_id===item.id&&l.selected);return <div key={f.id} className="evidence-file"><a href={root+`/artifacts/${f.id}/content`}>{f.original_name}</a><span>{size(f.bytes)}</span><button disabled={busy} onClick={()=>void link(item.id,f.id,!chosen)}>{chosen?'取消选定':'设为提交文件'}</button><button disabled={busy} onClick={()=>void run(async()=>{await request(`/requirements/${item.id}/artifacts/${f.id}`,'DELETE')})}>取消关联</button></div>})}
    </section>}
    <section className="requirements"><header><h2>项目文件库</h2>{input('批量上传成果')}</header>
      {files.length===0&&<p>暂无成果文件</p>}{files.map(f=><details key={f.id} className="library-file"><summary><strong>{f.original_name}</strong><span>{f.extension||'无扩展名'}　{size(f.bytes)}　{new Date(f.uploaded_at).toLocaleString('zh-CN',{hour12:false})}</span></summary><p>对应要求</p>{f.requirements.length===0?<p>尚未关联</p>:f.requirements.map(l=><button key={l.requirement_id} onClick={()=>{setActive(l.requirement_id);setPicker(false)}}>{requirements.find(r=>r.id===l.requirement_id)?.title} {l.selected?'（已选定）':''}</button>)}<div className="row-actions"><a href={root+`/artifacts/${f.id}/content`}>下载文件</a>{input('替换文件',undefined,f.id)}<button className="danger-text" disabled={busy} onClick={()=>{if(confirm(`删除“${f.original_name}”及其关联？`))void run(async()=>{await request('/artifacts/'+f.id,'DELETE')})}}>删除文件</button></div></details>)}
    </section>
  </div>
}
