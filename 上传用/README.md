# 每日要闻 · 你的时政与机会雷达

一个可以「装到手机桌面」的轻量新闻 App：每天自动更新，分**国家 / 国际 / 与我相关**三个板块，
其中「与我相关」会按**就业、考公、考研、落户、补贴、行业风口**等关键词，从所有新闻里替你筛出真正用得上的条目。

- 手机端：PWA 网页应用，**iPhone / Android 都能添加到主屏幕**，打开即全屏，像原生 App 一样
- 服务端：GitHub Actions 免费定时抓取（不需要买服务器、不需要备案）
- 推送：每天早上 8 点推一条微信消息（PushPlus，免费），也可以换成 Bark / Telegram

```
news-app/
├─ docs/                 ← 网页本体（GitHub Pages 从这里发布）
│  ├─ index.html
│  ├─ news.json          ← 每次运行后自动更新
│  ├─ manifest.webmanifest
│  ├─ sw.js
│  └─ icon-*.png
├─ fetch_news.py         ← 抓取 + 分类 + 推送
└─ .github/workflows/update.yml
```

---

## 一、5 分钟上线（只做一次）

### 1. 建仓库
1. 打开 <https://github.com> 注册/登录
2. 右上角 **+ → New repository**
3. 名字随便填，例如 `daily-news`，选 **Public**（免费额度够用），点 **Create repository**

### 2. 上传文件
在新建的仓库页面点 **uploading an existing file**，把本项目里**所有文件和文件夹**拖进去：

- `docs` 文件夹（整个拖入）
- `fetch_news.py`
- `.github` 文件夹（在里面，注意别漏，它是隐藏目录）
- `README.md`

> 提示：GitHub 网页拖拽支持文件夹。若 `.github` 拖不上去，用 GitHub Desktop 或 `git push` 上传。

点 **Commit changes**。

### 3. 打开网页
1. 仓库 → **Settings → Pages**
2. **Source** 选 `Deploy from a branch`，Branch 选 `main`、目录选 **`/docs`**，Save
3. 等 1 分钟，页面上方出现网址：`https://你的用户名.github.io/daily-news/`
4. 手机浏览器打开它 ✅

---

## 二、装到手机桌面（10 秒）

| 系统 | 操作 |
|---|---|
| **iPhone** | Safari 打开网址 → 底部「分享」→「添加到主屏幕」 |
| **Android** | Chrome 打开网址 → 右上角「⋮」→「安装应用 / 添加到主屏幕」 |

装好后有独立图标，全屏无地址栏，断网也能看上次缓存的内容。

---

## 三、开启每天 8:00 的微信推送（可选，但推荐）

1. 手机微信扫码登录 <https://www.pushplus.plus>，复制你的 **token**
2. 回到 GitHub 仓库 → **Settings → Secrets and variables → Actions → New repository secret**
   - Name：`PUSHPLUS_TOKEN`
   - Secret：粘贴刚才的 token
3. 仓库 → **Actions** 标签页 → 如果提示 workflow 未启用，点 **I understand my workflows, go ahead and enable them**
4. 想立刻测试：Actions → 左侧「每日要闻」→ **Run workflow**

之后每天早上 8 点左右（GitHub 免费任务可能延迟几分钟），微信会收到一条含三个板块要闻的消息。

> 其他推送方式（任选其一，配好对应的 Secret 即可，可同时配置）：
> - **Bark（iPhone）**：`BARK_URL` = `https://api.day.app/你的key`
> - **Telegram**：`TG_TOKEN` + `TG_CHAT`

---

## 四、先在电脑上看效果

```bash
cd news-app
python fetch_news.py          # 抓一次，生成 docs/news.json
python -m http.server 8000 -d docs
# 浏览器打开 http://localhost:8000
```

手机和电脑连同一个 Wi-Fi 时，手机访问 `http://电脑IP:8000` 也能看（此时不能安装到桌面，需要 https）。

---

## 五、按自己的口味调

都在 `fetch_news.py` 顶部，改完提交即可生效：

| 想改什么 | 改哪里 |
|---|---|
| 加/减信息源 | `FEEDS` 列表，格式 `(板块, 名称, RSS地址, 每源最多几条)` |
| 「与我相关」筛什么 | `CAREER`（强相关，直接入选）/ `POLICY`（政策）/ `INDUSTRY`（风口，需命中 2 个词） |
| 每栏条数 | `MAX_PER_SECTION`，默认 30 |
| 推送时间 | `.github/workflows/update.yml` 里的 `cron: "0 0 * * *"`（UTC，北京时间 = UTC+8，故 0 点 = 早 8 点） |
| 数据更新频率 | 同上，`cron: "10 * * * *"` 表示每小时 |

---

## 常见问题

**Q：`github.io` 在国内打不开或很慢？**
换一个静态托管即可，代码完全不用改（都是相对路径），把 `docs` 目录原样上传：
- **Cloudflare Pages**：<https://pages.cloudflare.com> → Create project → Direct Upload → 拖入 `docs` 文件夹
- **Gitee Pages**：新建仓库上传 `docs` 内容 → 服务 → Gitee Pages（需实名）
- 推送仍然走 GitHub Actions，和网页放在哪无关

**Q：为什么不用 App Store / 应用商店？**
上架需要开发者账号（苹果 688 元/年）、审核和备案；PWA 用浏览器「添加到主屏幕」就能达到同样的效果，且改版不用等审核。

**Q：会收费吗？**
GitHub 公开仓库的 Actions 和 Pages 都免费。PushPlus 免费版每天额度足够 1 条推送。

**Q：数据从哪来？**
中国新闻网、BBC 中文、钛媒体、极客公园、华尔街见闻、界面新闻等公开 RSS，标题与链接均指向原站。

**Q：某个板块空了/报错？**
单个源偶发超时会自动跳过，不影响其他源；连续为空可检查 Actions 运行日志。
