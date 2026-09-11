"""实体归并。

这些测试钉住的是**边界**，不是「认出了多少实体」。认多认少可以调；
把 `定期见面的理由` 砍成 `定期见面的理`、或者把 `下雨天开门` 砍成 `下雨天开`，
是错的，而且是那种只有列出词条才看得见的错。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import demo, entity, store, db
from yang.text import candidates


def corpus():
    c = db.connect(":memory:")
    store.load_state(c, demo.state(), "replace")
    return store.docs(c)


def texts(docs):
    return [p["text"] for d in docs for p in d["pieces"]]


def found():
    return entity.discover(texts(corpus()))


# ---------- 该认出来的 ----------
def test_finds_the_phrase_the_readme_promised():
    """「一个定期见面的理由」在两篇里各说一次。逐篇的眼光看不见它——
    它正是 entity.py 存在的理由。"""
    assert "定期见面的理由" in found()


def test_the_two_ideas_it_links_now_share_one_term_not_five():
    """归并前 i-cook 和 c-social 共有 `理由 个定 定期 期见 见面` 五条，
    其实说的是同一个东西。余弦把它算了五次。"""
    docs = corpus()
    from yang.terms import extract
    tm = extract(docs)
    a = {t["term"] for t in tm["i-cook"]}
    b = {t["term"] for t in tm["c-social"]}
    assert a & b == {"定期见面的理由"}


def test_still_links_them():
    """归并不能把连接弄丢。共有词从五条变一条，但两篇必须还连着。"""
    from yang.graph import build
    g = build(corpus())
    pair = frozenset(("i-cook", "c-social"))
    assert pair in {frozenset((b["a"], b["b"])) for b in g["bridges"]}
    assert pair in {frozenset((s["a"], s["b"])) for s in g["sim"]}


# ---------- 边界 ----------
def test_measure_word_stripped_from_the_head():
    """`一个定期见面的理由` → 砍掉 `一个`。左邻的 `一` 是「这是量词」的证据。"""
    ents = found()
    assert not [e for e in ents if e.startswith("个")], ents


def test_measure_word_kept_at_the_tail():
    """`门` 是量词（一门课），但 `下雨天开门` 的 `门` 是名词。
    量词只砍头不砍尾——这条不对称是 `_trim` 里最容易写反的一处。"""
    assert "下雨天开门" in found()


def test_preposition_stripped_from_the_head():
    """`只在下雨天开门` → `下雨天开门`。介词和副词开不了一个实体。"""
    ents = found()
    assert not [e for e in ents if e[0] in "在从只都也还又就才"], ents


def test_particle_stripped_from_the_tail():
    ents = found()
    assert not [e for e in ents if e[-1] in "的了着在和与是里"], ents


def test_nothing_ends_in_a_numeral():
    """`连缺两次就换人` 砍完是 `连缺两` → 再砍 `两` → 只剩两个字，出局。"""
    ents = found()
    assert not [e for e in ents if e[-1] in "一二三四五六七八九十两几"], ents


# ---------- 否决 ----------
def test_sentences_are_not_entities():
    """`会是什么` `如果有` `因为下雨` 都重复出现过，但它们是连接词在说话。"""
    ents = found()
    for junk in ("会是什么", "如果有", "因为下雨", "城市里"):
        assert junk not in ents, junk


def test_stop_bigram_inside_is_a_veto():
    assert not entity._plausible("会是什么")
    assert not entity._plausible("因为下雨")
    assert entity._plausible("定期见面的理由")


def test_numeral_plus_measure_inside_is_a_veto():
    """数量词开启一个新的名词短语，所以这一串跨了短语边界，是半句话。"""
    assert not entity._plausible("连缺两次就换人")
    assert entity._plausible("下雨天开门的店")


def test_needs_to_repeat():
    """只说过一次的短语连不上任何东西，留着也进不了图。"""
    assert entity.discover(["定期见面的理由很重要"]) == set()
    assert "定期见面的理由" in entity.discover(
        ["定期见面的理由很重要", "缺的是一个定期见面的理由"])


def test_cohesion_gate():
    """`下雨` 到处都是、`下雨天开门` 只在一处，那 `下雨天开门` 是凝固的；
    反过来如果构成它的二元组各自到处乱跑，它就只是碰巧挨在一起。"""
    loose = ["安静的图书馆", "安静的夜里", "图书馆很吵", "图书馆开门", "安静图书馆"]
    assert "安静图书馆" not in entity.discover(loose)


# ---------- 和 candidates 的接口 ----------
def test_candidates_matches_entities_whole():
    ents = {"定期见面的理由"}
    c = candidates("缺的是一个定期见面的理由。", ents)
    assert c["定期见面的理由"] == 1
    for frag in ("定期", "期见", "见面", "理由"):
        assert frag not in c, frag


def test_candidates_longest_wins():
    ents = {"下雨天开门", "下雨天开门的店"}
    c = candidates("一间只在下雨天开门的店。", ents)
    assert c["下雨天开门的店"] == 1 and "下雨天开门" not in c


def test_candidates_without_entities_is_unchanged():
    """不传实体表就是老行为。单独调 candidates 的地方不该被这个改动影响。"""
    a = candidates("一间只在下雨天开门的店。")
    b = candidates("一间只在下雨天开门的店。", None)
    assert a == b


def test_context_survives_the_cut():
    """实体被整块切走之后，剩下片段的左邻字要带着走——
    否则 `一个|想法` 的量词规则在切口上就失效了。"""
    c = candidates("那家店只在下雨天开门。", {"下雨天开门"})
    assert "下雨天开门" in c
    assert "家店" not in c, "左邻的 `那` 还在，量词规则该照常生效"


def test_measure_bigram_needs_a_determiner_before_it():
    """没有数词/指示词作证据就不能扔。`记录本身` 的 `本身` 是真词。"""
    assert "本身" in candidates("记录本身没意思，空白才有。")
    assert "个想" not in candidates("把你另一个想法放进来。")


# ---------- 不炸 ----------
def test_empty_corpus():
    assert entity.discover([]) == set()
    assert entity.discover(["", None]) == set()


def test_latin_only_corpus():
    assert entity.discover(["hello world", "hello world"]) == set()
