"""Opt-in embedding recall; lexical evidence remains a separate explanation."""
import hashlib
import json
import math
import urllib.request
from . import db, store


def related(c, identifier):
    conf = db.kv_get(c,'conf',{}) or {}
    settings = conf.get('embeddings') or {}
    if settings.get('enabled') is not True:
        return {'enabled':False,'related':[]}
    model = next((m for m in conf.get('models',[]) if m.get('id')==settings.get('model_id')),None)
    if not model or not model.get('base'):
        raise ValueError('请为语义召回选择已配置的嵌入模型。')
    documents = store.docs(c)
    if identifier not in {doc['id'] for doc in documents}:
        raise ValueError('没有这个想法。')
    if len(documents)>1000:
        raise ValueError('语义召回单次最多支持 1000 篇文档。')
    # Persist only vector/cache identifiers; model secrets never enter responses.
    cached = db.kv_get(c,'embeddings_cache',{})
    namespace = model['base'].rstrip('/')+'|'+str(model.get('model') or '')
    vectors, missing, keys = {}, [], {}
    for doc in documents:
        text = '\n'.join(piece['text'] for piece in doc['pieces'])[:12000]
        key = hashlib.sha256((namespace+'\0'+text).encode()).hexdigest()
        keys[doc['id']] = key
        if key in cached:
            vectors[doc['id']] = cached[key]
        else:
            missing.append((doc['id'],text))
    staged = {}
    for start in range(0,len(missing),32):
        batch = missing[start:start+32]
        request = urllib.request.Request(model['base'].rstrip('/')+'/embeddings',
            data=json.dumps({'model':model.get('model'),'input':[text for _,text in batch]}).encode(),
            headers={'Content-Type':'application/json', **({'Authorization':'Bearer '+model['key']} if model.get('key') else {})})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                data=json.loads(response.read(16*1024*1024))['data']
            if not isinstance(data,list) or len(data)!=len(batch): raise ValueError()
            indexed = {row['index']:row['embedding'] for row in data}
            if set(indexed)!=set(range(len(batch))): raise ValueError()
            for index,(did,_) in enumerate(batch):
                value=indexed[index]
                if not isinstance(value,list) or not 1<=len(value)<=8192 or not all(type(x) in (int,float) and math.isfinite(x) for x in value): raise ValueError()
                norm=math.sqrt(sum(x*x for x in value))
                if not math.isfinite(norm) or norm<=0: raise ValueError()
                vectors[did]=[x/norm for x in value]
                staged[keys[did]]=vectors[did]
        except Exception:
            raise ValueError('嵌入服务调用失败或返回无效向量，请检查模型配置。') from None
    dimensions={len(vector) for vector in vectors.values()}
    if len(dimensions)>1:
        raise ValueError('嵌入模型维度发生变化，请清理语义缓存后重试。')
    merged={**cached,**staged}
    db.kv_set(c,'embeddings_cache',{key:merged[key] for key in set(keys.values())})
    c.commit()
    lexical=store.graph(c)['terms']
    query=vectors[identifier]
    source_terms={item['term'] for item in lexical.get(identifier,[])}
    hits=[]
    for doc in documents:
        if doc['id']==identifier: continue
        score=sum(a*b for a,b in zip(query,vectors[doc['id']]))
        if score<0.45: continue
        shared=sorted(source_terms & {item['term'] for item in lexical.get(doc['id'],[])})
        hits.append({'id':doc['id'],'title':doc['title'],'score':round(min(1,max(-1,score)),4),
                     'basis':'embedding','lexical_terms':shared,
                     'explanation':'向量相似度，仅表示语义候选；共同词条单独列出。'})
    hits.sort(key=lambda hit:(-hit['score'],hit['id']))
    return {'enabled':True,'related':hits[:20],'embedded_documents':len(missing),'model_id':model['id']}
