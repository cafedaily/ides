"""实体归并：把散成一串二元组的同一个东西，认回成一个词条。

`text.candidates` 是**逐段**看文本的，它只能发现在同一段里重复出现的多字词
（`下雨天` 说了三次才长得出来）。可是大部分实体在每篇里只说一次——
「一个定期见面的理由」在两篇里各出现一次，逐段的眼光永远看不见它，
于是它被打碎成 `个定` `定期` `期见` `见面` 四条二元组。

碎成四条不只是难看，它有三处实际后果：

1. **余弦被灌水**：两篇共有的其实是一个实体，点积里却算了四次，
   于是「共有一个长短语」的两篇，排在了「共有四个不同概念」的两篇前面；
2. **桥的名额被占**：`PER_PAIR=2` 本来是给一对想法留两条不同的线索的，
   结果两条都是同一个短语的碎片；
3. **界面上那行「共有词」没法读**：`间只 天开 天它 家店` 没有一个是词。

这个模块把眼光从「一段」抬到「整个语料」：跨篇统计 n-gram，把总是一起出现的
一串字认成一个实体，交回给 `text.candidates` 优先整体匹配。

## 判据

一个候选串 `g` 要成为实体，要同时过三关：

- **出现够多**：跨语料至少 `MIN_COUNT` 次。只说过一次的短语没法和别的东西连，
  留着也进不了图。
- **边界干净**：头上不能是数词/指示词/量词（`一个定期见面` → `定期见面`），
  尾巴上不能是虚词、介词、连词（`下雨天开门的` → `下雨天开门`）。
  量词和虚词都是**闭合词类**，几十个字穷举得完，不是一张会越长越长的停用表。
- **凝固**：`g` 出现的次数，要接近它内部每个二元组各自出现的次数
  （`MIN_COHESION`）。意思是那些二元组基本只因为 `g` 才存在。
  这条判据和 `text.candidates` 里的长度提升是同一个，只是尺度从一段换成了全语料。

## 为什么不用邻接熵

无监督分词的标准做法是左右邻接熵（真词的上下文丰富，碎片的上下文单一）。
这里不用，因为它在这个规模上估不准：一个人的想法空间只有几十篇、几千字，
一个短语出现两三次，算出来的熵是噪声不是信号。凝固度只要两个计数就能算，
在小语料上退化得体面得多。等语料涨到几百篇再换。

## 已知的边界

跨语料统计意味着**加一篇想法可能改变旧想法的词条**。这是有意的：实体是语料的
属性，不是单篇的属性。代价是图谱不增量——`rebuild` 每次都从头算。几十篇没问题。
"""
from collections import Counter, defaultdict

from .text import (DET, ENT_HEAD_BAN, ENT_TAIL_BAN, MEASURE, NO_HEAD, NO_TAIL,
                   STOP2, runs_of)

MIN_COUNT = 2          # 跨语料至少出现这么多次
MIN_LEN = 3            # 实体至少三个字。两个字的交给二元组，那条路已经通了
MAX_LEN = 8            # 「下雨天开门的店」七个字。再长基本是整句，不是实体
MIN_COHESION = 0.75    # 和 text.candidates 的 promote_ratio 同源

HEAD_BAN = DET | NO_HEAD | ENT_HEAD_BAN
TAIL_BAN = DET | NO_TAIL | ENT_TAIL_BAN


def _trim(g, left=None):
    """砍掉两头不可能属于实体的字。砍到不能再砍为止。

    头：数词、指示词、虚词、介词、连词、副词（`在下雨天开` `只在下雨天开门`）；
    尾：数词、虚词、介词、连词、方位词（`下雨天开门的` `连缺两` `城市里`）。

    量词是特例，**只砍头、而且只在左边确实站着一个数词/指示词的时候砍**。
    这条不对称是有代价换来的：`一个定期见面` 里的 `个` 该砍，因为左边的 `一`
    证明了它是量词；可 `本地模型` 的 `本` 不能砍，`下雨天开门` 的 `门` 更不能砍
    ——量词字有一半同时是常见的名词和词尾（门、家、条、本、部、场、句、行）。
    没有数词作证据就不动它。

    左邻的字可能落在候选窗口外面（`一个定期见面的理由` 有九个字，`一` 挤不进
    `MAX_LEN`），所以 `left` 从语料里查：这个串出现过的位置，前面站的都是什么字。
    这是整个模块唯一一处邻接统计——它撑得住，是因为要回答的问题是二元的
    （左边是不是数词），不是去估一个熵。
    """
    i, j = 0, len(g)
    while i < j:
        if g[i] in HEAD_BAN:
            i += 1
        elif g[i] in MEASURE and _det_before(g, i, left):
            i += 1
        else:
            break
    while j > i and g[j - 1] in TAIL_BAN:
        j -= 1
    return g[i:j]


def _det_before(g, i, left):
    """`g[i]` 这个量词左边是不是数词/指示词。串里有就看串里，没有就问语料。"""
    if i > 0:
        return g[i - 1] in DET
    if not left:
        return False
    seen = left.get(g, ())
    return bool(seen) and all(ch in DET for ch in seen)


def _plausible(t):
    """两条否决：这一串是句子，不是实体。

    - 里面含一个 STOP2 二元组（`什么` `如果` `因为`）——那是连接词在说话，
      不是一个东西的名字；
    - 里面含「数词 + 量词」（`连缺两次就换人` 的 `两次`）——数量词开启一个新的
      名词短语，所以这一串跨了短语边界，它是半句话。

    第二条也是 `text._bigrams` 那条量词规则的同一个道理，只是那边看的是
    二元组的左邻，这边看的是长串的内部。
    """
    for i in range(len(t) - 1):
        if t[i:i + 2] in STOP2:
            return False
        if t[i] in DET and t[i + 1] in MEASURE:
            return False
    return True


def _counts(runs, max_len=MAX_LEN):
    """所有长度 2..max_len 的 n-gram 计数，外加每个串的左邻字。

    中文串已经按标点断开，不跨句。串在句首时左邻记成空——那种位置没有证据，
    `_det_before` 会当成「不是量词」。
    """
    c = Counter()
    left = defaultdict(set)
    for run in runs:
        L = len(run)
        for n in range(2, max_len + 1):
            for i in range(L - n + 1):
                g = run[i:i + n]
                c[g] += 1
                left[g].add(run[i - 1] if i else "")
    return c, left


def discover(texts, min_count=MIN_COUNT, min_len=MIN_LEN,
             max_len=MAX_LEN, min_cohesion=MIN_COHESION):
    """texts: 整个语料的每一段文本 → 实体集合。

    返回一个 set，`text.candidates` 拿它做最长优先的整体匹配。
    """
    runs = []
    for t in texts:
        runs.extend(runs_of(t))
    if not runs:
        return set()

    cnt, left = _counts(runs, max_len)
    keep = {}
    # 从长到短：长的先定下来，短的如果只是它的一段，后面会被剔掉
    for g, c in sorted(cnt.items(), key=lambda kv: (-len(kv[0]), -kv[1])):
        if len(g) < min_len or c < min_count:
            continue
        t = _trim(g, left)
        if len(t) < min_len or t in keep or not _plausible(t):
            continue
        ct = cnt.get(t, 0)            # 砍完之后用它自己的计数，砍掉的边会带来更多出现
        if ct < min_count:
            continue
        bases = [cnt.get(t[i:i + 2], 0) for i in range(len(t) - 1)]
        if not bases or min(bases) <= 0:
            continue
        if ct < min_cohesion * min(bases):
            continue
        keep[t] = ct

    return _maximal(keep)


def _maximal(keep):
    """短的如果只是长的一段、而且出现次数没多出来，就是长的碎片，剔掉。

    `下雨天开门` 留下，`下雨天开`（同样出现 3 次）剔掉；
    但 `下雨天` 如果出现 6 次——它在别处独立出现过——就留着，两个都是实体。
    """
    out = set(keep)
    for a in list(out):
        for b in out:
            if a is not b and len(a) < len(b) and a in b and keep[a] <= keep[b]:
                out.discard(a)
                break
    return out
