import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import { Requirements } from './Requirements'
import { Artifacts } from './Artifacts'
import { Delivery } from './Delivery'

type Project = { id: string; name: string; kind: 'contest' | 'course'; task_text: string; task_filename?: string; task_segments?: {ref:string;text:string}[]; updated_at: string }
async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try { response = await fetch('/api' + path, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }) }
  catch { throw new Error('无法连接服务，请启动后端后重试') }
  if (!response.ok) { const error = await response.json(); throw new Error(typeof error.detail === 'string' ? error.detail : '操作失败，请重试') }
  return response.status === 204 ? undefined as T : response.json()
}

function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [view,setView] = useState('task')
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [modal, setModal] = useState<'create' | 'rename' | 'delete' | null>(null)
  const [target, setTarget] = useState<Project | null>(null)
  const [name, setName] = useState('')
  const [kind, setKind] = useState<Project['kind']>('contest')
  const [formError, setFormError] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  const dirty = selected !== null && text !== selected.task_text
  async function load() {
    setLoading(true); setError('')
    try {
      const list = await api<Project[]>('/projects'); setProjects(list)
      setView(new URLSearchParams(location.hash.slice(1)).get('view') || 'task')
      const id = new URLSearchParams(location.hash.slice(1)).get('project')
      if (id) { const p = await api<Project>('/projects/' + id); setSelected(p); setText(p.task_text) }
      else setSelected(null)
    } catch (e) { setSelected(null); setError((e as Error).message) }
    finally { setLoading(false) }
  }
  const navigation = useRef({ dirty: false, hash: location.hash })
  navigation.current.dirty = dirty
  useEffect(() => { void load(); const change = () => {
    if (navigation.current.dirty && !confirm('任务说明尚未保存，离开并放弃修改？')) {
      history.replaceState(null, '', location.pathname + location.search + navigation.current.hash)
      return
    }
    navigation.current.hash = location.hash
    void load()
  }; window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change) }, [])
  useEffect(() => { const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = '' } }; window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn) }, [dirty])
  function navigate(id?: string, page='task') { setSaved(false); location.hash = id ? 'project=' + id + (page!=='task'?'&view='+page:'') : '' }
  function show(type: typeof modal, p?: Project) { setTarget(p || null); setName(p?.name || ''); setKind(p?.kind || 'contest'); setFormError(''); setModal(type); dialog.current?.showModal() }
  function close() { if (busy) return; dialog.current?.close(); setModal(null) }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); if (modal !== 'delete' && !name.trim()) { setFormError('请输入项目名称'); return }
    setBusy(true); setFormError('')
    try {
      if (modal === 'delete') {
        await api('/projects/' + target!.id, 'DELETE')
        if (selected?.id === target!.id) { setSelected(null); setText(''); location.hash = '' }
      } else {
        const p = await api<Project>(modal === 'create' ? '/projects' : '/projects/' + target!.id, modal === 'create' ? 'POST' : 'PATCH', { name: name.trim(), kind })
        if (selected?.id === p.id) setSelected(p)
      }
      setProjects(await api<Project[]>('/projects')); dialog.current?.close(); setModal(null)
    } catch (e) { setFormError((e as Error).message) }
    finally { setBusy(false) }
  }
  async function save() {
    setBusy(true); setError(''); setSaved(false)
    try { const p = await api<Project>('/projects/' + selected!.id + '/task', 'PUT', { task_source: 'paste', task_text: text }); setSelected(p); setSaved(true) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="shell">
    <a className="skip" href="#main">跳到正文</a>
    <aside><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate() }}><span className="brandmark" aria-hidden="true">S</span>SubmitLens</a>
      <nav aria-label="项目导航"><button className={!selected ? 'nav active' : 'nav'} onClick={() => navigate()}>我的项目</button>
      {selected && <><div className="project-label">{selected.name}</div><button className={view==='task'?'nav active':'nav'} aria-current={view==='task'?'page':undefined} onClick={()=>navigate(selected.id)}>任务要求</button><button className={view==='artifacts'?'nav active':'nav'} aria-current={view==='artifacts'?'page':undefined} onClick={()=>navigate(selected.id,'artifacts')}>成果验收</button><button className={view==='delivery'?'nav active':'nav'} onClick={()=>navigate(selected.id,'delivery')}>交付中心</button></>}</nav>
    </aside>
    <main id="main"><header><div><div className="breadcrumb">{selected ? <button onClick={() => navigate()}>我的项目</button> : '项目'}</div><h1>{selected ? (view==='delivery'?'交付中心':view==='artifacts'?'成果验收':'任务要求') : '我的项目'}</h1>{selected && <p className="project-heading">{selected.name}<span className="kind">{selected.kind === 'contest' ? '竞赛' : '课程'}</span></p>}</div>
      {!selected && <button className="primary" onClick={() => show('create')}>新建项目</button>}
      {selected && view==='task' && <div className="actions"><span role="status">{dirty ? '未保存' : saved ? '已保存' : ''}</span><button className="primary" disabled={busy || !dirty} onClick={save}>{busy ? '保存中…' : '保存'}</button></div>}</header>
      {error && <div className="error" role="alert">{error} <button onClick={() => { void (dirty ? save() : load()) }}>重试</button></div>}
      {loading ? <p role="status">正在读取…</p> : selected ? view==='delivery' ? <Delivery key={selected.id} id={selected.id}/> : view==='artifacts' ? <Artifacts key={selected.id} id={selected.id}/> : <><section className="editor"><label>上传文件<input type="file" accept=".pdf,.docx,.md,.txt" disabled={busy} onChange={async e => { const file=e.target.files?.[0]; if(!file)return; e.target.value=''; if(file.size>50*1024*1024){setError('文件超过 50 MB，请缩小后重试');return} if(dirty&&!confirm('上传将替换未保存文本，继续？'))return;setBusy(true);setError('');try{const body=new FormData();body.append('file',file);const r=await fetch(`/api/projects/${selected.id}/task-file`,{method:'POST',body});const p=await r.json();if(!r.ok)throw new Error(p.detail);setSelected(p);setText(p.task_text)}catch(error){setError((error as Error).message)}finally{setBusy(false)} }}/></label><label htmlFor="task">粘贴文本</label><textarea id="task" value={text} onChange={e => { setText(e.target.value); setSaved(false) }} spellCheck={false} placeholder="粘贴任务说明" disabled={busy}/><footer><span>任务原文</span><span>{text.length} 字符</span></footer><details><summary>来源 {selected.task_filename}</summary>{selected.task_segments?.map((s,i)=><div key={i}><b>{s.ref}</b><pre className="original">{s.text}</pre></div>)}</details></section><Requirements key={selected.id + selected.updated_at} id={selected.id} dirty={dirty}/></> : <section className="project-list" aria-label="项目列表">
        {projects.length === 0 ? <div className="empty"><h2>暂无项目</h2></div> : <><div className="list-heading"><span>项目名称</span><span>更新时间</span><span>操作</span></div>{projects.map(p => <article key={p.id}><div className="project-cell"><span className="file-symbol" aria-hidden="true"/><div><button className="project-name" onClick={() => navigate(p.id)}>{p.name}</button><span className="project-type">{p.kind === 'contest' ? '竞赛' : '课程'}</span></div></div><time dateTime={p.updated_at}>{new Date(p.updated_at).toLocaleString('zh-CN', { hour12: false })}</time><div className="row-actions"><button onClick={() => show('rename', p)}>重命名</button><button className="danger-text" onClick={() => show('delete', p)}>删除</button></div></article>)}</>}
      </section>}
    </main>
    <dialog ref={dialog} onCancel={e => { if (busy) e.preventDefault(); else setModal(null) }}><form onSubmit={submit}><h2>{modal === 'create' ? '新建项目' : modal === 'rename' ? '重命名项目' : '删除项目'}</h2>
      {modal === 'delete' ? <p className="delete-copy">删除“{target?.name}”及任务说明？此操作无法撤销。</p> : <><label htmlFor="name">项目名称</label><input id="name" autoFocus value={name} onChange={e => setName(e.target.value)} disabled={busy}/><label htmlFor="kind">项目类型</label><select id="kind" value={kind} onChange={e => setKind(e.target.value as Project['kind'])} disabled={busy}><option value="contest">竞赛</option><option value="course">课程</option></select></>}
      {formError && <p className="error" role="alert">{formError}</p>}<div className="dialog-actions"><button type="button" onClick={close} disabled={busy}>取消</button><button className={modal === 'delete' ? 'danger' : 'primary'} disabled={busy}>{busy ? '处理中…' : modal === 'create' ? '创建项目' : modal === 'rename' ? '保存' : '删除项目'}</button></div></form></dialog>
  </div>
}
createRoot(document.getElementById('root')!).render(<App />)
