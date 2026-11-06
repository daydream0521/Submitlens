import {test,expect} from '@playwright/test'
test('待处理草稿可选择规范出处并编辑',async({page})=>{
 const root=process.env.APP_URL||'http://127.0.0.1:5173'
 const project={id:'offline-citation',name:'出处处理',kind:'contest',task_text:'任务',task_segments:[],updated_at:'2026-11-06'}
 let row:any={id:'draft',title:'视频',description:'提交MP4',required:true,quote:'提交MP4',source_ref:'',constraints:[],needs_manual_review:true,confirmed:false,source_issues:[{field:'source_ref',reason:'引文匹配多处，请选择章节与来源片段',quote:'提交MP4',matches:[{ref:'行 3 / 视频',section:'省赛 / 视频'},{ref:'行 8 / 视频',section:'国赛 / 视频'}]}]}
 await page.route('**/api/projects**',async route=>{
  const url=new URL(route.request().url()),method=route.request().method()
  if(url.pathname.endsWith('/requirements/draft')&&method==='PUT'){
   const body=route.request().postDataJSON();expect(body.source_ref).toBe('行 3 / 视频')
   row={...body,id:'draft',source_issues:[],confirmed:false};return route.fulfill({json:row})
  }
  if(url.pathname.endsWith('/requirements'))return route.fulfill({json:[row]})
  return route.fulfill({json:url.pathname==='/api/projects'?[project]:project})
 })
 await page.goto(root+'/#project=offline-citation')
 await expect(page.locator('.requirements')).toContainText('出处待处理')
 await page.locator('.requirements>details>summary').click()
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 await page.getByRole('button',{name:'省赛 / 视频 / 行 3 / 视频',exact:true}).click()
 await expect(page.getByLabel('出处',{exact:true})).toHaveValue('行 3 / 视频')
 await page.getByRole('button',{name:'保存要求',exact:true}).click()
 await expect(page.locator('.requirements')).not.toContainText('出处待处理')
})
