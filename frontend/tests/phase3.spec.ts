import {test,expect} from '@playwright/test'

test('成果定向上传、多对多关联、选定与删除覆盖',async({page,request})=>{
 const root=process.env.APP_URL||'http://127.0.0.1:5173'
 const p=await(await request.post(root+'/api/projects',{data:{name:'成果回归-'+Date.now(),kind:'contest'}})).json()
 const base=root+'/api/projects/'+p.id
 try{
 const add=async(title:string)=>(await(await request.post(base+'/requirements',{data:{title,description:title}})).json()).id
 const env=await add('环境配置说明'),guide=await add('复现指南'),video=await add('演示视频')
 await request.post(base+'/confirm')
 await page.goto(root+'/#project='+p.id+'&view=artifacts')
 await expect(page.getByRole('heading',{name:'成果验收',exact:true})).toBeVisible()
 await page.getByLabel('批量上传成果',{exact:true}).setInputFiles({name:'README.md',mimeType:'text/markdown',buffer:Buffer.from('环境配置与复现')})
 await expect(page.locator('.library-file')).toHaveCount(1)
 for(const rid of [env,guide]){
  await page.locator('.coverage-row').filter({hasText:rid===env?'环境配置说明':'复现指南'}).click()
  const section=page.locator('#evidence-'+rid)
  await section.getByRole('button',{name:'从文件库选择'}).click()
  await section.getByRole('button',{name:'关联文件',exact:true}).click()
  await expect(section.locator('.evidence-file').last()).toContainText('README.md')
 }
 let rows=await(await request.get(base+'/artifacts')).json()
 expect(rows[0].requirements).toHaveLength(2)
 const readme=page.locator('.library-file').filter({hasText:'README.md'})
 await readme.locator('summary').click()
 await readme.getByRole('button',{name:'环境配置说明',exact:true}).click()
 await expect(page.locator('#evidence-'+env).getByRole('heading',{name:'环境配置说明',exact:true})).toBeVisible()
 await page.locator('.coverage-row').filter({hasText:'演示视频'}).click()
 const section=page.locator('#evidence-'+video)
 await section.getByLabel('上传成果',{exact:true}).setInputFiles([
 {name:'demo_old.mp4',mimeType:'video/mp4',buffer:Buffer.from('old candidate')},
 {name:'demo_final.mp4',mimeType:'video/mp4',buffer:Buffer.from('new candidate')}])
 await expect(section.locator('.evidence-file')).toHaveCount(2)
 await section.locator('.evidence-file').filter({hasText:'demo_final.mp4'}).getByRole('button',{name:'设为提交文件'}).click()
 await expect(page.locator('.coverage-row').filter({hasText:'演示视频'})).toContainText('已有证据')
 await page.reload()
 await page.locator('.coverage-row').filter({hasText:'演示视频'}).click()
 await expect(section.locator('.evidence-file').filter({hasText:'demo_final.mp4'})).toContainText('取消选定')
 await page.screenshot({path:'test-results/phase3-desktop.png',fullPage:true})
 await page.setViewportSize({width:375,height:812})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
 await page.screenshot({path:'test-results/phase3-mobile.png',fullPage:true})
 const final=page.locator('.library-file').filter({hasText:'demo_final.mp4'})
 await final.locator('summary').click()
 page.once('dialog',d=>d.accept())
 await final.getByRole('button',{name:'删除文件',exact:true}).click()
 await expect(page.locator('.coverage-row').filter({hasText:'演示视频'})).toContainText('缺少证据')
 await expect(section.locator('.evidence-file')).toHaveCount(1)
 await expect(page.getByText('已验证通过',{exact:true})).toHaveCount(0)
 }finally{await request.delete(base)}
})
