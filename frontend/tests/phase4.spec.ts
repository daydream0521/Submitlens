import {test,expect} from '@playwright/test'
test('预检待复核、人工确认与删除后失效',async({page,request})=>{
 const root=process.env.APP_URL||'http://127.0.0.1:5173'
 const p=await(await request.post(root+'/api/projects',{data:{name:'第四阶段-'+Date.now(),kind:'contest'}})).json()
 const base=root+'/api/projects/'+p.id
 try{
 const r=await(await request.post(base+'/requirements',{data:{title:'说明文档',description:'TXT格式及内容核对',needs_manual_review:true,constraints:[{type:'extension',value:'TXT',quote:'TXT格式'},{type:'content',value:'核对说明内容',quote:'核对说明内容'}]}})).json()
 await request.post(base+'/confirm')
 const a=await(await request.post(base+'/artifacts?requirement_id='+r.id,{multipart:{files:{name:'readme.txt',mimeType:'text/plain',buffer:Buffer.from('说明')}}})).json()
 await request.put(base+'/requirements/'+r.id+'/artifacts/'+a[0].id,{data:{selected:true}})
 await page.goto(root+'/#project='+p.id+'&view=artifacts')
 await expect(page.getByRole('heading',{name:'验收状态：待检查'})).toBeVisible()
 await page.getByRole('button',{name:'开始预检',exact:true}).click()
 await expect(page.getByRole('heading',{name:'验收状态：待复核'})).toBeVisible()
 await page.locator('.coverage-row').filter({hasText:'说明文档'}).click()
 const section=page.locator('#evidence-'+r.id)
 await expect(section.locator('.check-result')).toHaveCount(3)
 await section.getByLabel('复核备注').fill('已阅读说明')
 await section.getByRole('button',{name:'符合',exact:true}).click()
 await expect(page.getByRole('heading',{name:'验收状态：通过'})).toBeVisible()
 await expect(section).toContainText('人工确认 / 符合')
 await page.reload()
 await expect(page.getByRole('heading',{name:'验收状态：通过'})).toBeVisible()
 await page.locator('.coverage-row').filter({hasText:'说明文档'}).click()
 await page.screenshot({path:'test-results/phase4.png',fullPage:true})
 await section.getByRole('button',{name:'取消关联',exact:true}).click()
 await expect(page.getByRole('heading',{name:'验收状态：不通过'})).toBeVisible()
 await expect(section.getByText('未复核',{exact:true})).toBeVisible()
 }finally{await request.delete(base)}
})
