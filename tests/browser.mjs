import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
const require=createRequire(process.env.YANG_BROWSER_RUNTIME ? path.resolve(process.env.YANG_BROWSER_RUNTIME,'package.json') : import.meta.url);
const {chromium}=require('playwright'),root=path.resolve(import.meta.dirname,'..');
const server=spawn(process.env.PYTHON||'python',['-u',path.join(root,'tests/browser_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let browser;const checks=[],errors=[],requests=[];
const record=text=>{checks.push(text);console.log(text);};
try{
 const fixture=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(new Error('fixture timeout')),10000);server.stdout.on('data',chunk=>{data+=chunk;try{const out=JSON.parse(data.split('\n')[0]);clearTimeout(timer);resolve(out);}catch{}});server.stderr.on('data',chunk=>process.stderr.write(chunk));server.on('exit',code=>reject(new Error('fixture exited '+code)));});
 browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1280,height:900},acceptDownloads:true});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
 await page.goto(fixture.url,{waitUntil:'domcontentloaded'});await page.getByRole('button',{name:'创建我的空间',exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>S.ideas.length+S.sparks.length+S.conf.models.length),0);
 assert.equal(await page.getByText(/演示|登录|Claude/).count(),0);assert.equal(requests.filter(x=>x.includes('/api/')).length,0);
 await page.getByLabel('空间名称',{exact:true}).fill('我的本地空间');await page.getByRole('button',{name:'创建我的空间',exact:true}).click();
 await page.getByRole('heading',{name:'连接你自己的模型'}).waitFor();record('Empty local onboarding with no demo, built-in model or application API traffic');
 await page.getByLabel('配置名称',{exact:true}).fill('我的模型');await page.getByLabel('服务地址',{exact:true}).fill('invalid-address');
 await page.getByLabel('模型 ID',{exact:true}).fill('custom-model');await page.getByLabel('API Key',{exact:true}).fill('WRONG');
 await page.getByRole('button',{name:'测试连接',exact:true}).click();await page.getByText(/请输入完整的服务地址/).waitFor();
 await page.getByLabel('服务地址',{exact:true}).fill(fixture.model_url);await page.getByRole('button',{name:'测试连接',exact:true}).click();await page.getByText(/模型鉴权失败/).waitFor();
 assert.equal(await page.getByLabel('配置名称',{exact:true}).inputValue(),'我的模型');
 await page.getByLabel('API Key',{exact:true}).fill('SYNTHETIC_LOCAL_KEY');await page.getByRole('button',{name:'测试连接',exact:true}).click();await page.getByText('连接成功。可以保存并开始使用。',{exact:true}).waitFor();
 await page.getByRole('button',{name:'保存模型',exact:true}).click();await page.getByRole('button',{name:'开始构建想法',exact:true}).waitFor();record('Explicit user model setup, validation, CORS connection test and recoverable authentication error');
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>S.space?.name==='我的本地空间' && !!AI);
 assert.equal(await page.evaluate(()=>S.conf.models[0].key),'SYNTHETIC_LOCAL_KEY');record('Workspace and user model configuration persist in device IndexedDB after reload');
 await page.locator('#fab').click();await page.locator('#v-new textarea').fill('一个只属于本机的想法');await page.getByRole('button',{name:'直接开始养',exact:true}).click();
 await page.locator('#v-one .title').filter({hasText:'自己的模型起的名字'}).waitFor();
 await page.getByRole('button',{name:'追问我',exact:false}).click();await page.locator('.prompt textarea').waitFor();
 await page.locator('.prompt textarea').fill('回答也只保存在当前设备。');await page.getByRole('button',{name:'记下来',exact:true}).click();await page.waitForFunction(()=>!DB.pending&&!DB.writing);
 await page.getByRole('button',{name:'追问我',exact:false}).click();await page.getByRole('button',{name:'算了',exact:true}).click();assert.equal(await page.locator('.prompt').count(),0);record('User model shapes ideas, streams follow-up questions, saves answers locally and cancels');
 await page.evaluate(()=>go('data'));await page.getByRole('tab',{name:'导入与导出',exact:true}).click();
 let downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'导出备份',exact:true}).click();let download=await downloadPromise;const plainFile=await download.path();
 const plain=fs.readFileSync(plainFile,'utf8');assert.ok(!plain.includes('SYNTHETIC_LOCAL_KEY'));
 await page.getByLabel('使用口令加密（同时包含模型密钥）',{exact:true}).check();await page.getByLabel('备份口令',{exact:true}).fill('browser-backup-password');
 downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'导出备份',exact:true}).click();download=await downloadPromise;const encryptedFile=await download.path();
 await page.locator('#import-file').setInputFiles(encryptedFile);await page.getByLabel('解密口令',{exact:true}).fill('wrong');await page.getByRole('button',{name:'解密并校验',exact:true}).click();
 await page.waitForFunction(()=>dv.busy===''&&dv.chk&&!dv.chk.ok&&(dv.chk.errors||[]).length>0);await page.getByLabel('解密口令',{exact:true}).fill('browser-backup-password');await page.getByRole('button',{name:'解密并校验',exact:true}).click();await page.getByRole('button',{name:'确认导入',exact:true}).waitFor();
 await page.getByRole('button',{name:'确认导入',exact:true}).click();await page.getByText('数据已导入当前空间。',{exact:true}).waitFor();record('Local plain/encrypted downloads, wrong-password recovery, validated import and key exclusion');
 await page.getByRole('tab',{name:'我的空间',exact:true}).click();await page.getByLabel('新空间名称',{exact:true}).fill('第二个空白空间');await page.getByRole('button',{name:'创建另一个空间',exact:true}).click();await page.getByRole('heading',{name:'连接你自己的模型'}).waitFor();
 assert.equal(await page.evaluate(()=>S.ideas.length+S.conf.models.length),0);
 await page.getByRole('tab',{name:'我的空间',exact:true}).click();await page.getByRole('button',{name:'切换',exact:true}).click();await page.waitForFunction(()=>S.space?.name==='我的本地空间');assert.equal(await page.evaluate(()=>S.ideas.length),1);record('Multiple independent local spaces and explicit switching preserve existing content');
 // Both tabs have the same acknowledged baseline; the second must detect an intervening write.
 await page.waitForFunction(()=>!DB.pending&&!DB.writing);const other=await context.newPage();other.on('pageerror',e=>errors.push(e.message));await other.goto(fixture.url,{waitUntil:'domcontentloaded'});await other.waitForFunction(()=>!!S.space&&!DB.pending&&!DB.writing);
 // Refresh first tab so both observe the latest navigation save revision.
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>!!S.space&&!DB.pending&&!DB.writing);
 await other.evaluate(async()=>{S.sparks.push({id:'other-window',text:'另一窗口修改',at:Date.now()});save();await dbWrite();});
 // Depending on navigation's revision, either tab may own the conflict; never silently overwrite.
 const secondConflict=await other.evaluate(()=>!!DB.conflict);
 if(secondConflict){await other.getByRole('button',{name:'保留此窗口版本',exact:true}).click();await other.waitForFunction(()=>!DB.pending&&!DB.writing&&!DB.conflict);}
 await page.evaluate(()=>{S.sparks.push({id:'my-draft',text:'保留本窗口草稿',at:Date.now()});save();});await page.getByRole('button',{name:'保留此窗口版本',exact:true}).waitFor();
 assert.ok(await page.evaluate(()=>JSON.parse(sessionStorage.getItem(draftKey())).state.sparks.some(x=>x.id==='my-draft')));
 await page.getByRole('button',{name:'保留此窗口版本',exact:true}).click();await page.waitForFunction(()=>!DB.pending&&!DB.writing&&!DB.conflict);await other.close();record('Concurrent tabs surface save conflict and preserve unsaved local draft');
 await context.setOffline(true);await page.locator('#fab').click();await page.locator('#v-new textarea').fill('离线记录');await page.getByRole('button',{name:'放进念头堆',exact:true}).click();await page.waitForFunction(()=>!DB.pending&&!DB.writing);assert.ok(await page.evaluate(()=>S.sparks.some(x=>x.text==='离线记录')));await context.setOffline(false);record('Offline idea capture saves without an application server');
 await page.evaluate(()=>go('data'));await page.getByRole('tab',{name:'模型配置',exact:true}).click();await page.getByRole('button',{name:'编辑',exact:true}).click();
 const target=path.join(root,'test-results');fs.mkdirSync(target,{recursive:true});await page.screenshot({path:path.join(target,'local-settings-desktop.png'),fullPage:true});
 await page.setViewportSize({width:375,height:812});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(target,'local-settings-mobile.png'),fullPage:true});
 await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});await page.screenshot({path:path.join(target,'local-settings-dark.png'),fullPage:true});
 await page.setViewportSize({width:812,height:375});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));record('Responsive settings verified on desktop, 375px mobile, landscape and dark reduced-motion mode');
 assert.equal(requests.filter(url=>new URL(url).origin===fixture.url&&new URL(url).pathname.startsWith('/api/')).length,0);assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(target,'local-browser-validation.json'),JSON.stringify({passed:true,storage:'browser-local',model_fixture:'explicit synthetic CORS endpoint',application_api_requests:0,checks,errors},null,2));
}finally{if(browser)await browser.close();server.kill();}
