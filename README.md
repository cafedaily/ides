# 养想法

创建自己的空间，连接自己选择的模型，把念头慢慢养成形。当前版本的网页是本地数据应用：空间、想法和模型配置都保存在当前设备的浏览器中。

## 使用流程

1. **创建空间**：首次打开为空白，填写空间名称。没有演示内容、预置模型或网站账号登录。
2. **配置大模型**：在“设置 → 模型配置”中填写名称、服务地址、模型 ID 和 API Key。支持 OpenAI 兼容接口；可先测试连接，再保存。可以设置默认模型或给不同动作分配不同模型。
3. **构建想法**：记录念头、用自己的模型起名和追问、保存回答、分叉或归档。请求支持流式输出与取消。连接失败会保留输入并显示错误。
4. **导出数据**：普通 JSONL 备份不包含模型密钥；口令加密备份包含配置与密钥。
5. **导入数据**：选择文件并校验，预览条数后选择合并或替换。默认保留当前模型配置；可明确选择导入文件中的模型配置。替换前自动下载一份当前内容的普通备份。

## 数据与网络

- 每个空间有独立的 IndexedDB 数据库，存储键为 `yang.space.v3.<space-id>`。空间列表在本机 localStorage 中；未保存草稿在本窗口 sessionStorage 中。数据库不可用时使用 localStorage 降级保存。
- 页面不会读取、写入或同步网站的 `/api/*`。静态托管服务只分发网页文件。
- 模型调用直接从浏览器发送到用户填写的服务地址，并携带用户提供的 API Key。服务需要允许浏览器跨域访问（CORS）。HTTPS 网页通常需要 HTTPS 模型地址；本地服务可使用浏览器允许的 loopback 地址。
- 所有用户记录均在本机持久化；**调用远程模型时，相关提示和想法文本仍会发送给所选模型服务**。第三方服务的数据保留政策由该服务决定。
- 多窗口修改采用本地版本检查。冲突时保留当前窗口草稿，用户选择保留当前版本或载入另一窗口版本；不会自动覆盖对方的记录。仅切换页面不会产生数据版本冲突。
- 清理浏览器网站数据会删除本机空间，使用导出文件备份和跨设备迁移。

## 构建和检查

```bash
python web/build.py --output dist/index.html
python -m pip install cryptography
python tests/run.py
python scripts/check_web.py
npm install --no-save playwright
npx playwright install chromium
node tests/browser.mjs
```

打开 `dist/index.html` 可使用本机存储、导入和导出。模型服务需允许页面实际的 Origin；文件页面可能使用 `null` Origin，可将网页托管在自己的 HTTP/HTTPS 站点上解决。仓库不会自动启动或部署服务。

浏览器检查使用明确标注的本地模拟模型验证 CORS、流式协议、错误恢复和存储，不读取个人数据库或真实密钥。配置页不会自动调用模型，只有“测试连接”或用户主动使用模型功能时才发送请求。

## 本地图谱

圈图保留实际碰撞关系；词条桥和路径由 `web/src/local_graph.js` 在浏览器内计算，支持同义词、忽略词和原文证据。当前浏览器算法使用中文候选词与 TF-IDF，并复用相同输入的缓存。旧版 Python 增量图谱及其性能基准仍作为后端历史实现保留，不能将旧版性能数值当作当前浏览器实现的性能结论。

## 旧版数据与开发记录

旧版 `yang.v1`、`yang.demo.v2`、`yang.private.v2` 和服务器 SQLite 不会被自动合入或删除。可以从旧版本导出 JSONL，然后在新空间中显式导入。旧版服务端模型配置不作为新空间的默认模型。

项目使用 [Pi Development Harness](https://github.com/cafedaily/pi-development-harness) 管理项目身份、受控写入、模块知识更新和验证。历史 0.2.1 开发案例见 `docs/harness-0.2.1-validation.json`；当前结构与验收分别见 `docs/architecture.json`、`docs/local-space-validation.json`。
