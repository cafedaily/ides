import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yang import demo
from yang.graph import build, path
from yang.terms import extract
from yang.store import docs as _docs_of_state


def docs():
    """把演示语料拆成带维度的片段——和 store.docs 同一套规则。"""
    st = demo.state()
    out = []
    for i in st["ideas"]:
        p = [{"dim": "title", "text": i["title"]}]
        if i["seed"]:
            p.append({"dim": "seed", "text": i["seed"]})
        if i["now"]:
            p.append({"dim": "now", "text": i["now"]})
        for g in i["grew"]:
            p.append({"dim": g["kind"], "text": g["q"] + "\n" + g["a"]})
        out.append({"id": i["id"], "kind": "idea", "title": i["title"], "pieces": p})
    for x in st["cold"]:
        out.append({"id": x["id"], "kind": "cold", "title": x["title"],
                    "pieces": [{"dim": "title", "text": x["title"]},
                               {"dim": "why", "text": x["why"]}]})
    for s in st["sparks"]:
        out.append({"id": s["id"], "kind": "spark", "title": s["text"][:24],
                    "pieces": [{"dim": "spark", "text": s["text"]}]})
    return out


D = docs()
G = build(D)
BR = {(b["term"], frozenset((b["a"], b["b"]))): b for b in G["bridges"]}


def has_bridge(term, a, b):
    return (term, frozenset((a, b))) in BR


def test_every_doc_gets_terms():
    empty = [d for d, v in G["terms"].items() if not v]
    assert not empty, "这些文档一个词条都没抽出来：%s" % empty


def test_bridge_from_a_dead_idea_to_a_live_one():
    """语料里故意埋的：凉了的想法的教训「定期见面的理由」，
    正好长在还活着的「每周一次的做饭约定」的「现在它是什么」里。"""
    hit = [b for b in G["bridges"]
           if {b["a"], b["b"]} == {"c-social", "i-cook"}]
    assert hit, "从 c-social 到 i-cook 应该有桥"
    assert any("why" in b["a_dims"] + b["b_dims"] for b in hit)
    assert max(b["bonus"] for b in hit) > 1.0, "一头是「为什么凉了」应该有加成"


def test_bridge_between_spark_and_dead_idea():
    """「安静」：一个凉了的想法的教训，和一个还没成形的念头。"""
    hit = [b for b in G["bridges"] if {b["a"], b["b"]} == {"c-bgm", "k-quiet"}]
    assert hit, "c-bgm 的「我真正想要的是安静」应该连到 k-quiet"


def test_cross_dimension_scores_above_same_dimension():
    cross = [b for b in G["bridges"] if not (set(b["a_dims"]) & set(b["b_dims"]))]
    assert cross, "应该存在纯跨维度的桥"
    assert all(b["bonus"] > 1.0 for b in cross)


def test_bridge_carries_evidence():
    for b in G["bridges"][:10]:
        assert b["a_say"]["text"], "每条桥都要能点回原话：%s" % b["term"]
        assert b["b_say"]["text"]


def test_collide_pair_shows_up_as_similar_or_bridged():
    """i-cats 的「碰一下」明确撞的是 i-rain，两者共有「下雨天」。"""
    linked = any({e["a"], e["b"]} == {"i-rain", "i-cats"} for e in G["sim"]) \
        or has_bridge("下雨天", "i-rain", "i-cats")
    assert linked


def test_similarity_is_symmetric_and_bounded():
    for e in G["sim"]:
        assert 0 < e["sim"] <= 1.0001
        assert e["a"] != e["b"]


def test_path_between_two_unrelated_ideas():
    """i-cloth（旧衣服履历）和 i-line（走过的路）没直接关系，
    但都谈到「记录」，应该串得起来。"""
    p = path(extract(D), "i-cloth", "i-line")
    assert p, "应该找得到一条路"
    assert p["nodes"][0] == "idea:i-cloth" and p["nodes"][-1] == "idea:i-line"
    assert p["hops"] >= 2
    # 路上每一跳都必须是真实节点，不能是编的
    for n in p["nodes"]:
        assert n.startswith("idea:") or n.startswith("term:")


def test_path_to_self_is_trivial():
    p = path(extract(D), "i-rain", "i-rain")
    assert p and p["hops"] == 0


def test_path_missing_node():
    assert path(extract(D), "i-rain", "不存在的") is None


def test_cooccurrence_npmi_in_range():
    for e in G["cooc"]:
        assert -1.0001 <= e["npmi"] <= 1.0001
        assert e["n"] >= 2


def test_nodes_and_edges_reference_each_other():
    ids = {n["id"] for n in G["nodes"]}
    for e in G["edges"]:
        assert e["a"] in ids and e["b"] in ids


def test_empty_corpus_does_not_explode():
    g = build([])
    assert g["nodes"] == [] and g["bridges"] == []


def test_single_doc_has_no_bridges():
    g = build([{"id": "x", "kind": "idea", "title": "只有一个",
                "pieces": [{"dim": "now", "text": "下雨天开门的店，下雨天亮灯。"}]}])
    assert g["bridges"] == [] and g["sim"] == []
