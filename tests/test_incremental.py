import copy
import random
from yang.graph_engine import GraphCache
from yang.terms import extract
from yang import graph


def doc(identifier, text):
    return {"id":identifier,"kind":"idea","title":text[:18],"pieces":[{"dim":"now","text":text}]}


def test_synonyms_connect_with_original_evidence():
    docs=[doc("a","我想让大模型帮助整理知识"),doc("b","LLM 可以整理知识"),doc("c","每一步都记录学习"),doc("d","每步都记录学习")]
    result=graph.build(docs)
    assert "大模型" in {x['term'] for x in result['terms']['a']}
    assert "大模型" in {x['term'] for x in result['terms']['b']}
    bridge=next(x for x in result['bridges'] if {x['a'],x['b']}=={'a','b'} and x['term']=='大模型')
    assert 'LLM' in bridge['b_say']['text']
    assert set(x['term'] for x in result['terms']['c']) & set(x['term'] for x in result['terms']['d'])


def test_incremental_matches_full_after_add_update_delete():
    docs=[doc('a','下雨天开门的店，下雨天亮灯'),doc('b','图书馆借一个下午的安静'),doc('c','大模型记录每一步学习')]
    cache=GraphCache()
    assert cache.update(docs)==graph.build(docs)
    for change in [doc('d','LLM记录每步学习'),doc('b','图书馆借安静的房间。下雨天开门的店')]:
        docs=[d for d in docs if d['id']!=change['id']]+[change]
        assert cache.update(docs)==graph.build(docs)
    docs=[d for d in docs if d['id']!='a']
    assert cache.update(docs)==graph.build(docs)
    assert cache.update([])==graph.build([])


def test_incremental_randomized_corpus_and_settings_changes():
    randomizer=random.Random(42)
    phrases=['下雨天开门的店','定期见面的理由','值夜班的人','图书馆的安静','每一步学习','LLM整理知识']
    docs=[];cache=GraphCache()
    for index in range(20):
        identifier=str(randomizer.randrange(8))
        docs=[d for d in docs if d['id']!=identifier]
        if index%4:
            docs.append(doc(identifier,'。'.join(randomizer.sample(phrases,3))))
        settings={'aliases':{'安静空间':'安静'}} if index>=10 else {}
        assert cache.update(docs,settings)==graph.build(docs,settings)


def test_adaptive_function_noise_and_alias_cycle():
    docs=[doc(str(i),'才是 bright'+str(i)+' 才是 useful'+str(i)) for i in range(10)]
    result=graph.build(docs)
    assert '才是' in result['quality']['adaptive_stopwords']
    assert all('才是' not in {x['term'] for x in values} for values in result['terms'].values())
    try:
        graph.build(docs,{'aliases':{'alpha':'beta','beta':'alpha'}})
        assert False
    except ValueError:
        pass


def test_cache_hit_and_changed_entity_retokenization():
    cache=GraphCache();docs=[doc('a','下雨天开门的店')]
    cache.update(docs);cache.update(docs)
    assert cache.metrics['cache_hit']
    docs.append(doc('b','下雨天开门的店'))
    assert cache.update(docs)==graph.build(docs)
    assert cache.metrics['changed_documents']==1
    assert cache.metrics['retokenized_documents']>=1
