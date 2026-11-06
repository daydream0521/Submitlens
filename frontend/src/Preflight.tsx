import { useState } from 'react'
export type Check = {type:string;actual:string;expected:string;quote:string;source_ref:string;reason:string;checked_at:string;status:string}
export type CheckedRequirement = {status:string;last_check_result?:Check[];review_decision?:string;review_note?:string;reviewed_at?:string;last_checked_at?:string;needs_manual_review?:boolean}
export const labels:Record<string,string>={pass:'通过',fail:'不通过',pending:'待复核',unchecked:'待检查',excluded:'未参与验收',error:'检查异常'}
const names:Record<string,string>={exists:'文件存在',extension:'文件格式',pdf_pages:'PDF 页数',video_duration:'MP4 时长',file_count:'文件数量',content:'内容要求'}
export function PreflightDetail({item,busy,review}:{item:CheckedRequirement;busy:boolean;review:(decision:string,note:string)=>void}){
 const [note,setNote]=useState(item.review_note||'')
 return <div className="preflight-detail"><h3>检查结果：{labels[item.status]||'待检查'}</h3>
 {!item.last_check_result&&<p>尚未检查，请开始预检</p>}
 {item.last_check_result?.map((c,i)=><div className="check-result" key={i}><h4>{names[c.type]} <span>{c.status==='pending'&&item.review_decision&&item.review_decision!=='pending'?'人工确认':c.type==='content'?'人工复核':'系统检查'} / {c.status==='pending'&&item.review_decision==='pass'?'符合':c.status==='pending'&&item.review_decision==='fail'?'不符合':labels[c.status]}</span></h4><dl><dt>实际</dt><dd>{c.actual}</dd><dt>要求</dt><dd>{c.expected}</dd><dt>依据</dt><dd>{c.source_ref}<blockquote>{c.quote||'未填写原文'}</blockquote></dd><dt>检查时间</dt><dd>{new Date(c.checked_at).toLocaleString('zh-CN',{hour12:false})}</dd></dl>{c.reason&&<p>{c.reason}</p>}</div>)}
 {item.status!=='excluded'&&<section className="manual-review"><h3>人工复核</h3><p>{item.review_decision==='pass'?'人工确认符合':item.review_decision==='fail'?'人工确认不符合':'未复核'}</p><label>复核备注<input value={note} disabled={busy} onChange={e=>setNote(e.target.value)}/></label><div className="row-actions"><button disabled={busy} onClick={()=>review('pass',note)}>符合</button><button disabled={busy} onClick={()=>review('fail',note)}>不符合</button><button disabled={busy} onClick={()=>review('pending',note)}>暂不复核</button></div>{item.reviewed_at&&<p>{new Date(item.reviewed_at).toLocaleString('zh-CN',{hour12:false})}</p>}</section>}
 </div>
}

