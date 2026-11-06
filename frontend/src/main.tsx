import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Project = { id: string; name: string; kind: 'contest' | 'course'; task_text: string; updated_at: string }
async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try { response = await fetch('/api' + path, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }) }
  catch { throw new Error('无法连接服务，请启动后端后重试') }
  if (!response.ok) throw new Error(response.status === 404 ? '项目不存在，请返回项目列表' : '操作失败，请重试')
  return response.status === 204 ? undefined as T : response.json()
}

function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
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
  function navigate(id?: string) { setSaved(false); location.hash = id ? 'project=' + id : '' }
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
      {selected && <><div className="project-label">{selected.name}</div><div className="nav active" aria-current="page">任务要求</div><div className="nav unavailable">成果验收 <small>未实现</small></div><div className="nav unavailable">交付中心 <small>未实现</small></div></>}</nav>
    </aside>
    <main id="main"><header><div><div className="breadcrumb">{selected ? <button onClick={() => navigate()}>我的项目</button> : '项目'}</div><h1>{selected ? '任务要求' : '我的项目'}</h1>{selected && <p className="project-heading">{selected.name}<span className="kind">{selected.kind === 'contest' ? '竞赛' : '课程'}</span></p>}</div>
      {!selected && <button className="primary" onClick={() => show('create')}>新建项目</button>}
      {selected && <div className="actions"><span role="status">{dirty ? '未保存' : saved ? '已保存' : ''}</span><button className="primary" disabled={busy || !dirty} onClick={save}>{busy ? '保存中…' : '保存'}</button></div>}</header>
      {error && <div className="error" role="alert">{error} <button onClick={() => { void (dirty ? save() : load()) }}>重试</button></div>}
      {loading ? <p role="status">正在读取…</p> : selected ? <section className="editor"><label htmlFor="task">粘贴文本</label><textarea id="task" value={text} onChange={e => { setText(e.target.value); setSaved(false) }} spellCheck={false} placeholder="粘贴任务说明" disabled={busy}/><footer><span>任务原文</span><span>{text.length} 字符</span></footer></section> : <section className="project-list" aria-label="项目列表">
        {projects.length === 0 ? <div className="empty"><h2>暂无项目</h2></div> : <><div className="list-heading"><span>项目名称</span><span>更新时间</span><span>操作</span></div>{projects.map(p => <article key={p.id}><div className="project-cell"><span className="file-symbol" aria-hidden="true"/><div><button className="project-name" onClick={() => navigate(p.id)}>{p.name}</button><span className="project-type">{p.kind === 'contest' ? '竞赛' : '课程'}</span></div></div><time dateTime={p.updated_at}>{new Date(p.updated_at).toLocaleString('zh-CN', { hour12: false })}</time><div className="row-actions"><button onClick={() => show('rename', p)}>重命名</button><button className="danger-text" onClick={() => show('delete', p)}>删除</button></div></article>)}</>}
      </section>}
    </main>
    <dialog ref={dialog} onCancel={e => { if (busy) e.preventDefault(); else setModal(null) }}><form onSubmit={submit}><h2>{modal === 'create' ? '新建项目' : modal === 'rename' ? '重命名项目' : '删除项目'}</h2>
      {modal === 'delete' ? <p className="delete-copy">删除“{target?.name}”及任务说明？此操作无法撤销。</p> : <><label htmlFor="name">项目名称</label><input id="name" autoFocus value={name} onChange={e => setName(e.target.value)} disabled={busy}/><label htmlFor="kind">项目类型</label><select id="kind" value={kind} onChange={e => setKind(e.target.value as Project['kind'])} disabled={busy}><option value="contest">竞赛</option><option value="course">课程</option></select></>}
      {formError && <p className="error" role="alert">{formError}</p>}<div className="dialog-actions"><button type="button" onClick={close} disabled={busy}>取消</button><button className={modal === 'delete' ? 'danger' : 'primary'} disabled={busy}>{busy ? '处理中…' : modal === 'create' ? '创建项目' : modal === 'rename' ? '保存' : '删除项目'}</button></div></form></dialog>
  </div>
}
createRoot(document.getElementById('root')!).render(<App />)
