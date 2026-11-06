import { useEffect, useRef, useState } from 'react'
import { labels, type CheckedRequirement } from './Preflight'
type Requirement=CheckedRequirement & {id:string;title:string;confirmed:boolean;required:boolean;stale?:boolean;source_issues?:unknown[]}
type File={id:string;original_name:string;bytes:number;requirements:{requirement_id:string;selected:boolean}[]}
type Project={last_export_at:string|null;export_outdated:boolean}
const path=(f:File)=>{
 const name=f.original_name.replace(/\\/g,'/').split('/').pop()!.replace(/[\x00-\x1f\x7f]/g,'_')
 return `materials/${f.id}/${['','.','..'].includes(name)?'未命名文件':name}`
}

export function Delivery({id}:{id:string}){
 const [items,setItems]=useState<Requirement[]>([]),[files,setFiles]=useState<File[]>([]),[chosen,setChosen]=useState<string[]>([])
 const [project,setProject]=useState<Project|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const form=useRef<HTMLFormElement>(null),started=useRef(false),previous=useRef<string|null>(null)
 const root=`/api/projects/${id}`
 const goto=(r:Requirement)=>{location.hash=`project=${id}&view=${r.status==='excluded'?'task':'artifacts'}&requirement=${r.id}`}
 async function load(){
  const responses=await Promise.all([fetch(root),fetch(root+'/checks'),fetch(root+'/artifacts')])
  if(responses.some(r=>!r.ok))throw new Error('无法读取交付数据，请刷新重试')
  const [p,c,a]=await Promise.all(responses.map(r=>r.json()))
  setProject(p);setItems(c.items);setFiles(a)
  setChosen(a.filter((f:File)=>f.requirements.some(l=>l.selected)).map((f:File)=>f.id))
 }
 useEffect(()=>{void load().catch(e=>setError(e.message))},[id])
 useEffect(()=>{
  if(!busy)return
  let active=true
  const timer=setInterval(()=>{void fetch(root).then(async r=>{
   if(!r.ok)throw new Error('无法读取导出状态，请检查连接后刷新')
   const p=await r.json();if(active&&p.last_export_at&&p.last_export_at!==previous.current){setProject(p);setBusy(false);started.current=false}
  }).catch(e=>{if(active){setError(e.message);setBusy(false)}})},700)
  return()=>{active=false;clearInterval(timer)}
 },[busy,id])
 const packed=files.filter(f=>chosen.includes(f.id))
 const formal=items.filter(r=>r.confirmed&&!r.stale&&!r.source_issues?.length)
 const pending=items.filter(r=>!formal.includes(r))
 const missing=(r:Requirement)=>r.required&&!files.some(f=>f.requirements.some(l=>l.requirement_id===r.id&&l.selected))
 const omitted=(r:Requirement)=>files.filter(f=>!chosen.includes(f.id)&&f.requirements.some(l=>l.requirement_id===r.id&&l.selected))
 return <div className="delivery"><section className="requirements"><header><h2>交付预览</h2><button className="primary" disabled={!project||busy} onClick={()=>{setError('');previous.current=project!.last_export_at;started.current=true;setBusy(true);form.current?.submit()}}>{busy?'正在导出…':'导出 ZIP'}</button></header>
 {project?.export_outdated&&<p role="status">材料已更新，请重新导出</p>}{error&&<p role="alert" className="error">{error}</p>}
 <p>通过 {formal.filter(r=>r.required&&r.status==='pass').length}　不通过 {formal.filter(r=>r.required&&r.status==='fail').length}　待复核 {formal.filter(r=>r.required&&r.status==='pending').length}　待检查 {formal.filter(r=>r.required&&r.status==='unchecked').length}</p>
 {formal.slice().sort((a,b)=>Number(missing(b))-Number(missing(a))||['fail','pending','unchecked','pass'].indexOf(a.status)-['fail','pending','unchecked','pass'].indexOf(b.status)).map(r=><div className="evidence-file" key={r.id}><span>{r.title}（{r.required?'必交':'建议'}）：{labels[r.status]}{missing(r)?'；缺少选定文件':''}{omitted(r).length>0?'；验收关联证据未包含在本次 ZIP':''}</span><button onClick={()=>goto(r)}>查看验收</button></div>)}
 {pending.length>0&&<><h3>待处理</h3>{pending.map(r=><div className="evidence-file" key={r.id}><span>{r.title}：{r.source_issues?.length?'出处待处理':r.stale?'原文已变':'未确认'}</span><button onClick={()=>goto(r)}>处理要求</button></div>)}</>}
 </section><section className="requirements"><h2>选择文件</h2>{files.map(f=><label className="delivery-file" key={f.id}><input type="checkbox" checked={chosen.includes(f.id)} disabled={busy} onChange={e=>setChosen(e.target.checked?[...chosen,f.id]:chosen.filter(x=>x!==f.id))}/><span>{f.original_name}（{f.bytes} 字节）<small>{f.requirements.map(l=>items.find(r=>r.id===l.requirement_id)?.title).filter(Boolean).join('、')||'尚未关联'}</small></span></label>)}
 {!packed.length&&<p>材料为空，本次仅导出验收报告</p>}<h3>预览目录</h3><pre className="original">{['submission_report.md',...packed.map(path)].join('\n')}</pre></section>
 <form ref={form} method="post" action={root+'/export'} target={'export-'+id} hidden>{chosen.map(aid=><input key={aid} name="artifact_ids" value={aid} readOnly/>)}</form>
 <iframe title="导出响应" name={'export-'+id} hidden onError={()=>{setError('下载中断，请检查连接后重试');setBusy(false)}} onLoad={e=>{
  if(!started.current)return
  try{const text=e.currentTarget.contentDocument?.body?.textContent;if(text){const detail=JSON.parse(text).detail;setError(typeof detail==='string'?detail:'导出失败，请重试');setBusy(false);started.current=false}}
  catch{setError('导出失败，请检查连接后重试');setBusy(false);started.current=false}
 }}/></div>
}
