"""分词与词条抽取。

中文没有空格，英文有。这个模块只做一件事：把一段话变成一串**候选词条**，
每个词条带出现次数。它不认识词典，靠的是滑动二元组 + 长度提升。

为什么是滑动二元组，不是定长切块：定长切块（比如每 2-4 字切一刀）会让
「给每一步加」和「每步只学」永远对不上——切点不对齐，共同的部分就消失了。
滑动二元组不挑切点，代价是噪声多，所以后面要靠停用表和长度提升把噪声压下去。
"""
import re
from collections import Counter

CJK = re.compile(r"[一-鿿㐀-䶿]+")
LAT = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{2,}")
SPLIT = re.compile(r"[^一-鿿㐀-䶿A-Za-z0-9+\-]+")

# 单字功能词：两个字都在这里面的二元组直接丢掉
FUNC = set("的了是在和与把被让这那个一不再还也有没就更很上下中为对从到"
           "它我你他她们来去用能要会并且以及然后所以因为只出成件事都又"
           "而但却则于其之与或者如果虽然但是可以应该已经正在过着地得"
           "什么怎么这样那样一些很多非常真的确实其实反正总是")

# 不可能作为词首的虚词：「的人」「了他」这类是粘出来的，不是词
NO_HEAD = set("的了着地得之而及或就也都还又很更最太把被让使即则乃")
# 不可能作为词尾的虚词：「他的」「走得」同理
NO_TAIL = set("的了着地得之而及或就也都还又很更太把被让使若虽因即则不没无未")
# 数词开头的二元组（一间、三次、十年）内容很稀，降权而不是删
NUM_HEAD = set("一二三四五六七八九十百千万两几半")

# 数词 + 指示词。它们后面跟量词，量词后面才是名词的开头——见下面 MEASURE。
# 故意不含方位词（上下前后）：「下雨天」的 下 不是指示词，把它算进来会切错实体。
DET = NUM_HEAD | set("这那每某各另")

# 量词。闭合词类，几十个字穷举得完，不是一张会越长越长的停用表。
#
# 它只在**有左邻语境**的时候起作用：`数/指示词 + 量词 + X` 里，`量词X` 这个二元组
# 一定跨了词的边界（`一个|想法` `一间|只在` `那家|店的` `四个|人轮流`），扔掉。
# 不能无条件扔量词开头的二元组——`本身` `条件` `位置` `部分` `轮流` 都是真词，
# 它们只是恰好以量词字开头。左邻的数词/指示词才是「这里是个量词」的证据。
MEASURE = set("个只条件家间张次位种台部本篇门段名份层双对群块片杯瓶碗顿场回句"
              "步页节课行组批轮届艘架辆匹株棵朵粒颗滴根支把封串堆列排队")

# 实体的两头。只给 entity.py 切边界用，不参与二元组过滤——`存在` `现在`
# 这类真词要留着。
#
# 头和尾是**两套**，而且尾比头短得多。原因是不对称的：介词、连词、助动词几乎
# 不可能是一个实体的第一个字（`在下雨天开` `因为下雨`），但它们里面很多是常见的
# 词尾——`理由` `机会` `功能` `数据` `行为` `方向`。当初把这些字一起放进尾禁字，
# 结果是 `定期见面的理由` 被砍成了 `定期见面的理`。
ENT_HEAD_BAN = set("在从对向跟给到于用为比由按据除关至往朝沿依和与或但而且则却"
                   "是有会能要将把被让使如果因所虽即才就只都也还又很更最太")

# 尾禁字只收「几乎不可能结束一个内容词」的：介词、连词、系动词。
# 方位词也算——`城市里` 的实体是 `城市`，`里` 是贴上去的。
# `面` 不在这里，否则 `定期见面` 会被砍成 `定期见`。
ENT_TAIL_BAN = set("在从跟给于和与但且是里中内外处")

# 成对出现但没有信息量的常见二元组
STOP2 = set("""什么 怎么 这个 那个 一个 一下 一样 一点 一种 一起 可以 应该 已经 正在
因为 所以 但是 如果 虽然 然后 而且 或者 就是 还是 只是 不是 没有 有点 有些 觉得
知道 时候 地方 东西 事情 问题 方式 方法 情况 时间 现在 以后 之前 之后 自己 我们
你们 他们 起来 出来 进去 下来 上去 过来 回去 真的 确实 其实 反正 总是 特别 非常
这些 那些 这样 那样 这么 那么 多少 几个 大家 别人 人们 一直 一定 可能 也许 大概
需要 想要 打算 试试 看看 说说 做做 用来 对于 关于 通过 根据 按照 由于 除了 包括""".split())

# 时间/数量/程度词：不是没意义，但它们能把任何两件事连起来，
# 所以在权重上降一档，而不是删掉——万一某个想法真的就是关于「每天」的。
GENERIC = set("""每天 每周 每年 每次 每月 今天 明天 昨天 现在 以前 将来 最近 有时 平时
一天 两天 三天 一年 半年 上午 中午 晚上 早上 半夜 白天 一次 两次 三次 第一 第二 一半
很多 不少 一些 大量 少量 一点 全部 所有 任何 每个 各种 几种
哪儿 哪里 哪些 哪个 哪天 什么 怎样 如何 为何 是否""".split())

STOPW = set("""the and for you your this that with have has are was were will would can could
from into about their there they them then than when what which who how why not but our
its it's don't doing does did been being some more most just like also only very much many
one two three get got make made use used using """.split())


def _runs(text):
    """把一段话切成中文串和英文词。标点断开，避免二元组跨句子。"""
    zh, en = [], []
    for seg in SPLIT.split(text or ""):
        if not seg:
            continue
        for m in CJK.finditer(seg):
            zh.append(m.group(0))
        for m in LAT.finditer(seg):
            w = m.group(0).lower()
            if w not in STOPW:
                en.append(w)
    return zh, en


def runs_of(text):
    """只要中文串。`entity.py` 跨语料统计 n-gram 时用它，口径必须和这里一致。"""
    return _runs(text)[0]


def _bigrams(run, prev=""):
    """run 里的二元组。`prev` 是这一段前面那个字——被实体切走的那一刀左边。

    没有 prev 的时候（一段的开头）量词规则不生效，这是对的：句首的 `个` 没有
    左邻数词作证据，不能断定它是量词。
    """
    out = []
    for i in range(len(run) - 1):
        g = run[i:i + 2]
        if g[0] in FUNC and g[1] in FUNC:
            continue
        if g[0] in NO_HEAD or g[1] in NO_TAIL:
            continue
        if g in STOP2:
            continue
        left = prev if i == 0 else run[i - 1]
        if left in DET and g[0] in MEASURE:
            continue        # 一个|想法、那家|店的：量词后面是下一个词的开头
        out.append(g)
    return out


def _ngrams(run, n):
    return [run[i:i + n] for i in range(len(run) - n + 1)]


def _split_by_entities(run, ents, max_len):
    """把 `entity.discover` 认出来的实体从 run 里整块切走，最长优先、不重叠。

    返回 (命中的实体, [(剩下的片段, 片段左边那个字)])。左邻的字要带着，
    因为 `_bigrams` 的量词规则要看它——切一刀不该把语境也切没了。
    """
    hits, parts = [], []
    i = start = 0
    n = len(run)
    while i < n:
        hit = ""
        for L in range(min(max_len, n - i), 2, -1):
            if run[i:i + L] in ents:
                hit = run[i:i + L]
                break
        if not hit:
            i += 1
            continue
        if i > start:
            parts.append((run[start:i], run[start - 1] if start else ""))
        hits.append(hit)
        i += len(hit)
        start = i
    if start < n:
        parts.append((run[start:], run[start - 1] if start else ""))
    return hits, parts


def candidates(text, entities=None, promote_min=2, promote_ratio=0.75):
    """返回 Counter{词条: 次数}。

    `entities` 是 `entity.discover` 跨语料认出来的实体。给了就先整块切走——
    「定期见面」算一条，不再散成 `定期` `期见` `见面` 三条。不给就退回纯二元组，
    单独用这个函数（测试、`evidence` 之外的临时调用）时行为和以前一样。

    长度提升：如果三字串出现的次数，接近它内部两个二元组各自出现的次数，
    说明那两个二元组多半只是因为这个三字串才出现的——那就把三字串留下，
    把两个二元组各减掉相应的次数。四字同理。「下雨天」就是这么从
    「下雨」「雨天」里长出来的。这一步只看**这一段**，看不见跨篇才成立的实体，
    所以才有 `entity.py`。
    """
    zh, en = _runs(text)
    cnt = Counter()
    segs = []
    if entities:
        max_len = max(len(e) for e in entities)
        for run in zh:
            hits, parts = _split_by_entities(run, entities, max_len)
            cnt.update(hits)
            segs.extend(parts)
    else:
        segs = [(run, "") for run in zh]

    for seg, prev in segs:
        cnt.update(_bigrams(seg, prev))
    cnt.update(en)

    for n in (3, 4):
        longer = Counter()
        for seg, _prev in segs:
            for g in _ngrams(seg, n):
                longer[g] += 1
        for g, c in longer.items():
            if c < promote_min:
                continue
            parts = [g[i:i + 2] for i in range(n - 1)]
            base = [cnt.get(p, 0) for p in parts]
            if not base or min(base) <= 0:
                continue
            if c >= promote_ratio * min(base):
                cnt[g] = cnt.get(g, 0) + c
                for p in parts:
                    cnt[p] = max(0, cnt.get(p, 0) - c)
    return Counter({t: c for t, c in cnt.items() if c > 0})


SENT = re.compile(r"[^。！？!?\n]+[。！？!?]?")


def sentences(text):
    return [s.strip() for s in SENT.findall(text or "") if s.strip()]


def evidence(text, term, width=60):
    """找出这个词条第一次出现在哪一句里。图上的一条边要能点回原话。"""
    for s in sentences(text):
        if term in s.lower() or term in s:
            if len(s) <= width:
                return s
            i = max(0, s.find(term) - width // 3)
            return ("…" if i else "") + s[i:i + width] + ("…" if i + width < len(s) else "")
    return ""
