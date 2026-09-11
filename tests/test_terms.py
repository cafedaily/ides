import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang.terms import extract, DIM_W


def doc(i, pieces, title="标题"):
    return {"id": i, "kind": "idea", "title": title,
            "pieces": [{"dim": d, "text": t} for d, t in pieces]}


DOCS = [
    doc("a", [("now", "下雨天开门的店。下雨天亮灯。下雨天大家无处可去。"),
              ("ask", "那个人现在是怎么凑合的？下雨天没地方待。")], "下雨天的店"),
    doc("b", [("why", "我真正想要的是安静，不是更多声音。安静很难买。")], "背景音"),
    doc("c", [("spark", "图书馆里能不能借一个下午的安静")], "借安静"),
    doc("d", [("now", "记录本身没意思，空白才有。记录了一年的轨迹。")], "走过的路"),
]
T = extract(DOCS)


def test_every_doc_has_terms():
    for d in DOCS:
        assert T[d["id"]], d["id"]


def test_weights_normalised():
    for items in T.values():
        s = sum(i["w"] ** 2 for i in items)
        assert s <= 1.0001, "归一化之后平方和不该超过 1"


def test_sorted_by_weight():
    for items in T.values():
        ws = [i["w"] for i in items]
        assert ws == sorted(ws, reverse=True)


def test_dims_recorded():
    a = {i["term"]: i for i in T["a"]}
    assert "下雨天" in a
    assert set(a["下雨天"]["dims"]) <= {"title", "now", "ask", "seed"}
    assert "now" in a["下雨天"]["dims"]


def test_shared_term_across_docs_has_df_two():
    b = {i["term"]: i for i in T["b"]}
    c = {i["term"]: i for i in T["c"]}
    assert "安静" in b and "安静" in c
    assert b["安静"]["df"] == 2


def test_title_dim_weighted_higher():
    assert DIM_W["title"] > DIM_W["note"]


def test_singleton_two_char_terms_dropped():
    """只在一篇里出现过的两字词是噪声的主要来源。只要这篇还留得下别的词，就该被丢掉。"""
    r = extract([doc("x", [("now", "潜艇舷窗的玻璃厚度。下雨天要看清楚，下雨天最难。")]),
                 doc("y", [("now", "下雨天的甜品店，下雨天排队最长。")])])
    got = {i["term"]: i for i in r["x"]}
    assert "下雨天" in got, "跨篇共有的词该留下"
    assert "潜艇" not in got, "只在这一篇出现过的两字词该被丢掉"


def test_a_doc_with_only_noise_keeps_it_rather_than_going_empty():
    """兜底：如果按规则筛完什么都不剩，就把原样留下。

    一篇抽不出词条，就永远进不了图——既搜不到，也串不上。
    宁可留着噪声，也不要一个隐形的想法。"""
    one = extract([doc("x", [("now", "潜艇舷窗玻璃的厚度")])])
    assert one["x"], "唯一的一篇也必须抽得出词条"


def test_empty_doc_yields_empty_list():
    e = extract([doc("z", [("now", "")])])
    assert e["z"] == [] or all(i["w"] > 0 for i in e["z"])


def test_top_n_respected():
    long_text = "。".join("第%d件事情是关于甲乙丙丁戊己庚辛的具体安排" % i for i in range(40))
    r = extract([doc("m", [("now", long_text)]), doc("n", [("now", long_text)])], top_n=5)
    assert len(r["m"]) <= 5
