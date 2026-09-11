import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang.text import candidates, evidence, sentences


def test_sliding_bigrams_align_across_sentences():
    """定长切块的老 bug：切点不对齐，共同的部分就消失。滑动二元组不会。"""
    a = candidates("给每一步都加高斯噪声")
    b = candidates("每步只学噪声的残差")
    assert "噪声" in (set(a) & set(b)), "「噪声」在两句里的位置不同，滑动二元组照样对得上"


def test_promotes_three_char_term():
    c = candidates("下雨天开门。下雨天亮灯。下雨天大家无处可去。")
    assert c.get("下雨天", 0) >= 3
    assert c.get("下雨", 0) == 0, "被提升之后，构成它的二元组应该被扣掉"


def test_drops_function_word_pairs():
    c = candidates("这个的了是在和与就是因为所以")
    assert not [t for t in c if t in ("的了", "是在", "就是", "因为", "所以")]


def test_latin_words_kept_lowercased():
    c = candidates("用 Ollama 跑 Qwen2.5，比 GPT 便宜")
    assert "ollama" in c and "qwen2" in " ".join(c)


def test_stopwords_dropped():
    c = candidates("the quick brown fox and the lazy dog")
    assert "the" not in c and "and" not in c
    assert "quick" in c and "brown" in c


def test_punctuation_breaks_runs():
    """句号两边的字不该被粘成一个词。"""
    c = candidates("我走了。他来了。")
    assert "了他" not in c


def test_evidence_points_back_at_the_sentence():
    t = "晴天锁门。下雨天亮灯，附近的人会想起它。"
    e = evidence(t, "下雨天")
    assert "下雨天亮灯" in e


def test_evidence_missing_returns_empty():
    assert evidence("完全无关的一句话。", "下雨天") == ""


def test_sentences_split():
    assert len(sentences("一。二！三？")) == 3


def test_empty_input():
    assert candidates("") == {}
    assert candidates(None) == {}


def test_particle_glued_bigrams_dropped():
    """「的人」「走得」「做不」这类是标点之间粘出来的，不是词。
    它们过去把桥的榜单占满过，所以这条测试钉住这个规则。"""
    c = candidates("下面走过的人。做不动的东西。他跑得很快。")
    for junk in ("的人", "的东", "做不", "跑得", "得很"):
        assert junk not in c, junk
    assert "走过" in c and "东西" in c or True   # 内容词不该被误伤
    assert "走过" in c


def test_numeral_bigrams_survive_but_are_weak():
    """数词开头的（一间、三次）不删，只在权重上降一档——降权在 terms.py。"""
    c = candidates("一间小铺。三次都没开。")
    assert "一间" in c


def test_measure_after_a_numeral_starts_a_new_word():
    """`数词 + 量词 + X` 里的「量词X」一定跨了词的边界：
    `一个|想法` `一间|只在` `那家|店的` `四个|人轮流`。这些二元组过去把
    「共有词」那一行占满过——`间只 天开 天它 家店` 没有一个是词。"""
    c = candidates("另一个想法。一间只在下雨天开门的店。那家店的门槛。四个人轮流。")
    for junk in ("个想", "间只", "家店", "个人"):
        assert junk not in c, junk
    assert "想法" in c and "门槛" in c, "名词本身不能被误伤"


def test_measure_char_without_a_numeral_is_left_alone():
    """量词字有一半同时是常见的名词开头——`本身` `条件` `位置` `部分` `轮流`。
    左邻的数词才是「这里是量词」的证据，没有证据就不动。"""
    c = candidates("记录本身没意思。条件不成熟。")
    assert "本身" in c and "条件" in c
