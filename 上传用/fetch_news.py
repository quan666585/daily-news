#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日时政 & 机会资讯抓取器
- 抓取多个 RSS 源，分为「国家 / 国际 / 与我相关」三个板块
- 输出 site/news.json 供手机端 PWA 读取
- 可选：推送到微信(PushPlus) / Bark(iOS) / Telegram
仅使用 Python 标准库，无需安装依赖。
"""
import os, re, json, ssl, sys, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

TZ = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "news.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"

# ---------------------------------------------------------------- 信息源
FEEDS = [
    # (板块, 名称, 地址, 每源最多条数)
    ("cn",    "中国新闻网·要闻", "https://www.chinanews.com.cn/rss/importnews.xml", 10),
    ("cn",    "中国新闻网·国内", "https://www.chinanews.com.cn/rss/china.xml", 10),
    ("cn",    "中国新闻网·滚动", "https://www.chinanews.com.cn/rss/scroll-news.xml", 8),
    ("cn",    "中国新闻网·财经", "https://www.chinanews.com.cn/rss/finance.xml", 6),
    ("world", "中国新闻网·国际", "https://www.chinanews.com.cn/rss/world.xml", 15),
    ("world", "BBC 中文", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", 12),
    ("me",    "中国新闻网·教育", "https://www.chinanews.com.cn/rss/edu.xml", 6),
    ("me",    "钛媒体", "https://www.tmtpost.com/rss", 7),
    ("me",    "极客公园", "http://www.geekpark.net/rss", 6),
    ("me",    "华尔街见闻", "https://dedicated.wallstreetcn.com/rss.xml", 5),
    ("me",    "界面新闻", "https://a.jiemian.com/index.php?m=article&a=rss", 5),
    ("me",    "少数派", "https://sspai.com/feed", 3),
]

# ---------------------------------------------------------------- 关键词（与我相关）
# A 级：直接决定应届生的选择（工作 / 升学 / 落户 / 钱）
CAREER = ["就业", "招聘", "校招", "秋招", "春招", "应届", "毕业生", "考公", "国考",
          "公务员", "事业单位", "选调", "考研", "保研", "考编", "人才引进", "求职",
          "实习", "落户", "人才补贴", "创业", "新职业", "风口", "五年规划",
          "政府工作报告", "中央经济工作会议", "两会", "扩招", "岗位", "薪酬", "薪资",
          "简历", "面试", "试用期", "劳动合同", "毕业", "学位", "学费", "助学贷款"]
# B 级：政策与生活成本
POLICY = ["政策", "新规", "试点", "改革", "规划", "补贴", "社保", "公积金", "个税",
          "房价", "租房", "消费券", "最低工资", "就业率", "灵活就业", "民营经济",
          "减负", "降息", "关税", "扩内需", "以旧换新", "医保", "高校", "专业设置",
          "招生", "教育", "养老", "生育", "户籍", "贷款利率", "楼市"]
# C 级：风口行业（需要命中两个以上才算数）
INDUSTRY = ["人工智能", "AI", "大模型", "机器人", "新能源", "储能", "光伏", "芯片",
            "半导体", "低空经济", "商业航天", "生物医药", "跨境电商", "新质生产力",
            "算力", "数据要素", "国产替代", "出海", "融资", "独角兽", "智能驾驶",
            "自动驾驶", "具身智能", "量子", "核电", "氢能", "卫星", "创新药", "6G"]

MAX_PER_SECTION = 30
ME_MIN_BUCKET = 1
ME_MAX_PER_SOURCE = 4


def score(title):
    """返回 (分桶, 命中词)。3=强相关 2=政策 1=风口 0=无关"""
    a = [k for k in CAREER if k in title]
    b = [k for k in POLICY if k in title]
    c = [k for k in INDUSTRY if k in title]
    if a:
        bucket = 3
    elif b:
        bucket = 2
    elif len(c) >= 2:
        bucket = 1
    else:
        bucket = 0
    return bucket, (a + b + c)[:3]


def _ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read()


def to_text(data):
    """按 XML 声明或内容猜测编码（GB2312/GBK 源很多）。"""
    head = data[:300].decode("ascii", "ignore")
    m = re.search(r'encoding=["\']([\w-]+)["\']', head, re.I)
    encs = []
    if m:
        encs.append(m.group(1))
    encs += ["utf-8", "gb18030"]
    for e in encs:
        try:
            return data.decode(e)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "ignore")


def clean(t):
    if not t:
        return ""
    t = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def strip_ns(tag):
    return tag.split("}")[-1].lower() if isinstance(tag, str) else ""


def parse_feed(raw):
    """返回 [(title, link, pubdate_str, summary)]，容错优先。"""
    text = to_text(raw)
    # 去掉非法控制字符，修补裸 &
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"&(?!#?\w+;)", "&amp;", text)

    root = None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # 退化为正则抽取
        out = []
        for block in re.findall(r"<item[\s>].*?</item>", text, re.S | re.I):
            def g(tag):
                m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), block, re.S | re.I)
                return clean(m.group(1)) if m else ""
            out.append((g("title"), g("link"), g("pubDate"), g("description")))
        return out

    items = []
    nodes = root.iter()
    for node in nodes:
        if strip_ns(node.tag) not in ("item", "entry"):
            continue
        title = link = date = desc = ""
        for ch in node:
            name = strip_ns(ch.tag)
            if name == "title":
                title = clean("".join(ch.itertext()))
            elif name == "link":
                link = (ch.get("href") or clean("".join(ch.itertext()))).strip()
            elif name in ("pubdate", "published", "updated", "date"):
                if not date:
                    date = clean("".join(ch.itertext()))
            elif name in ("description", "summary", "content"):
                if not desc:
                    desc = clean("".join(ch.itertext()))[:160]
        if title and link:
            items.append((title, link, date, desc))
    return items


def parse_time(s):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        dt = None
    if dt is None:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def norm_key(title):
    return re.sub(r"[\s\W_]+", "", title).lower()[:40]


def collect():
    sections = {"cn": [], "world": [], "me": []}
    seen = set()
    me_pool = []
    errors = []
    cutoff = datetime.now(TZ).timestamp() - 5 * 86400

    for sec, name, url, cap in FEEDS:
        try:
            items = parse_feed(fetch(url))
        except Exception as e:  # 单个源失败不影响整体
            errors.append("%s:%s" % (name, type(e).__name__))
            continue
        n = 0
        for title, link, date, desc in items[:60]:
            k = norm_key(title)
            if not k or k in seen:
                continue
            dt = parse_time(date)
            if dt is None or dt.timestamp() < cutoff:
                continue  # 只要近 5 天的
            seen.add(k)
            bucket, hits = score(title)
            item = {
                "t": title[:120],
                "u": link,
                "s": name,
                "d": dt.strftime("%m-%d %H:%M"),
                "ts": int(dt.timestamp()),
                "k": hits,
            }
            if sec != "me" and n < cap and len(sections[sec]) < MAX_PER_SECTION:
                sections[sec].append(item)
                n += 1
            if bucket >= ME_MIN_BUCKET and len(me_pool) < 400:
                me_pool.append((bucket, dict(item)))

    for sec in ("cn", "world"):
        sections[sec].sort(key=lambda x: -x["ts"])

    # 「与我相关」：先按相关度分桶，再按时间；同一来源最多 4 条，保证多样性
    me_pool.sort(key=lambda x: (-x[0], -x[1]["ts"]))
    picked, keys, per_src = [], set(), {}
    for bucket, it in me_pool:
        k = norm_key(it["t"])
        if k in keys or per_src.get(it["s"], 0) >= ME_MAX_PER_SOURCE:
            continue
        keys.add(k)
        per_src[it["s"]] = per_src.get(it["s"], 0) + 1
        picked.append(it)
        if len(picked) >= MAX_PER_SECTION:
            break
    sections["me"] = picked

    return {
        "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
        "date": datetime.now(TZ).strftime("%Y年%m月%d日"),
        "counts": {k: len(v) for k, v in sections.items()},
        "errors": errors,
        "sections": sections,
    }


def push(data):
    """按需推送：环境变量 PUSHPLUS_TOKEN / BARK_URL / TG_TOKEN+TG_CHAT"""
    if os.environ.get("SKIP_PUSH") == "1":
        return
    lines = ["**%s · 今日要闻**" % data["date"], ""]
    labels = {"cn": "一、国家", "world": "二、国际", "me": "三、与我相关"}
    for key in ("cn", "world", "me"):
        items = data["sections"][key][:5]
        if not items:
            continue
        lines.append("**%s**" % labels[key])
        for i, it in enumerate(items, 1):
            lines.append("%d. [%s](%s)" % (i, it["t"], it["u"]))
        lines.append("")

    md = "\n".join(lines)

    token = os.environ.get("PUSHPLUS_TOKEN")
    if token:
        body = urllib.parse.urlencode({
            "token": token, "title": "今日要闻 · " + data["date"][:10],
            "content": md.replace("\n", "<br>"), "template": "markdown",
        }).encode()
        req = urllib.request.Request("https://www.pushplus.plus/send", data=body)
        print("[pushplus]", urllib.request.urlopen(req, timeout=15, context=_ctx()).status)

    bark = os.environ.get("BARK_URL")
    if bark:
        url = bark.rstrip("/") + "/" + urllib.parse.quote("今日要闻 " + data["date"][:10])
        body = urllib.parse.urlencode({"body": md[:1800], "group": "每日新闻"}).encode()
        req = urllib.request.Request(url, data=body)
        print("[bark]", urllib.request.urlopen(req, timeout=15, context=_ctx()).status)

    tg, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if tg and chat:
        body = urllib.parse.urlencode({
            "chat_id": chat, "text": md, "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % tg, data=body)
        print("[telegram]", urllib.request.urlopen(req, timeout=15, context=_ctx()).status)


def main():
    data = collect()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("saved:", OUT, data["counts"], "errors:", data["errors"])
    if "--push" in sys.argv:
        push(data)


if __name__ == "__main__":
    main()
