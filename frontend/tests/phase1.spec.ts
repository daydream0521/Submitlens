import { test, expect } from '@playwright/test'

test('项目管理和换行任务在刷新后保留', async ({ page }) => {
  await page.goto(process.env.APP_URL || 'http://127.0.0.1:5173')
  const suffix = Date.now()
  for (const [name, kind] of [[`竞赛-${suffix}`, 'contest'], [`课程-${suffix}`, 'course']]) {
    await page.getByRole('button', { name: '新建项目' }).click()
    await page.getByLabel('项目名称', { exact: true }).fill(name)
    await page.getByLabel('项目类型').selectOption(kind)
    await page.getByRole('button', { name: '创建项目' }).click()
    await expect(page.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await page.reload()
  await page.getByRole('button', { name: `竞赛-${suffix}`, exact: true }).click()
  const text = '第一段：提交代码。\n\n第二段：保留换行。\n  缩进原文'
  await page.getByLabel('粘贴文本').fill(text)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('已保存')
  await page.reload()
  await expect(page.getByLabel('粘贴文本')).toHaveValue(text)
  await page.screenshot({ path: 'test-results/task-desktop.png', fullPage: true })
  await page.getByRole('button', { name: '我的项目', exact: true }).first().click()
  const row = page.locator('article').filter({ hasText: `竞赛-${suffix}` })
  await row.getByRole('button', { name: '重命名' }).click()
  await page.getByLabel('项目名称', { exact: true }).fill(`改名-${suffix}`)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('button', { name: `改名-${suffix}`, exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/projects-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 375, height: 812 })
  await page.screenshot({ path: 'test-results/projects-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  for (const name of [`改名-${suffix}`, `课程-${suffix}`]) {
    await page.locator('article').filter({ hasText: name }).getByRole('button', { name: '删除', exact: true }).click()
    await page.getByRole('button', { name: '删除项目', exact: true }).click()
    await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  }
})

test('浏览器后退取消与前进不覆盖未保存原文', async ({page,request})=>{
  const root=process.env.APP_URL || 'http://127.0.0.1:5173'
  const name='导航回归-'+Date.now()
  const p=await (await request.post(root+'/api/projects',{data:{name,kind:'course'}})).json()
  await page.goto(root)
  await page.getByRole('button',{name,exact:true}).click()
  await page.getByLabel('粘贴文本',{exact:true}).fill('尚未保存')
  let leave=false
  page.on('dialog',d=>leave?d.accept():d.dismiss())
  await page.goBack()
  await expect(page.getByLabel('粘贴文本',{exact:true})).toHaveValue('尚未保存')
  await page.goForward()
  await expect(page.getByLabel('粘贴文本',{exact:true})).toHaveValue('尚未保存')
  leave=true
  await page.getByRole('button',{name:'我的项目',exact:true}).first().click()
  await expect(page.getByRole('heading',{name:'我的项目',exact:true})).toBeVisible()
  await request.delete(root+'/api/projects/'+p.id)
})

test('文件原文与手动要求确认持久化',async({page,request})=>{
  const root=process.env.APP_URL||'http://127.0.0.1:5173'
  const p=await(await request.post(root+'/api/projects',{data:{name:'要求编辑-'+Date.now(),kind:'contest'}})).json()
  await page.goto(root+'/#project='+p.id)
  await page.getByLabel('上传文件',{exact:true}).setInputFiles({name:'任务.md',mimeType:'text/markdown',buffer:Buffer.from('# 视频\n提交 MP4 5–8 分钟。')})
  await expect(page.getByLabel('粘贴文本',{exact:true})).toHaveValue('# 视频\n提交 MP4 5–8 分钟。')
  await page.getByRole('button',{name:'添加要求',exact:true}).click()
  await page.getByLabel('材料名称',{exact:true}).fill('视频')
  await page.getByLabel('内容',{exact:true}).fill('提交 MP4 5–8 分钟。')
  await page.getByRole('button',{name:'保存要求',exact:true}).click()
  await expect(page.locator('.requirements')).toContainText('草稿')
  await page.getByRole('button',{name:'确认清单',exact:true}).click()
  await expect(page.locator('.requirements')).toContainText('已确认')
  await page.reload()
  await expect(page.locator('.requirements')).toContainText('已确认')
  await page.screenshot({path:'test-results/phase2.png',fullPage:true})
  await request.delete(root+'/api/projects/'+p.id)
})
