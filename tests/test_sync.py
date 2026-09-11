import copy
import json
import time
from unittest.mock import patch
from yang import api, db, demo, store, sync, semantic


def test_sync_atomic_conflict_delete_update_and_keys(tmp_path):
    c=db.connect(tmp_path/'sync.db')
    store.load_state(c,demo.state(),'replace')
    before=store.state(c)
    first=copy.deepcopy(before['ideas'][0]);first['title']='更新后的想法'
    body={'base_revision':before['revision'],'changes':{'ideas':{'upsert':[first],'delete':[before['ideas'][1]['id']]}}}
    result=api.dispatch(c,'POST','/api/sync',{},body)
    assert result['revision']==before['revision']+1
    current=store.state(c)
    assert len(current['ideas'])==len(before['ideas'])-1
    try:
        api.dispatch(c,'POST','/api/sync',{},body)
        assert False
    except api.Err as error:
        assert error.code==409 and error.details['revision']==result['revision']
    assert store.state(c)==current
    invalid={'base_revision':result['revision'],'changes':{'ideas':{'delete':[first['id']]},'sparks':{'upsert':[{'id':'bad'}]}}}
    try:
        sync.apply(c,invalid)
        assert False
    except ValueError:
        pass
    assert store.state(c)==current
    c.close()


def test_two_connections_cannot_overwrite_same_revision(tmp_path):
    file=tmp_path/'race.db';a=db.connect(file);b=db.connect(file)
    state={'base_revision':0,'changes':{'sparks':{'upsert':[{'id':'new','text':'初始','at':int(time.time()*1000)}]}}}
    sync.apply(a,state)
    try:
        sync.apply(b,state)
        assert False
    except sync.Conflict:
        pass
    assert store.state(b)['revision']==1
    a.close();b.close()


def test_sync_rejects_alias_cycle_and_preserves_secret(tmp_path):
    c=db.connect(tmp_path/'conf.db')
    conf={'models':[{'id':'m','name':'测试','key':'PRIVATE','base':'https://example.test/v1'}]}
    store.load_state(c,{'conf':conf})
    remote=store.state(c);assert 'PRIVATE' not in json.dumps(remote)
    conf=remote['conf'];conf['graph']={'aliases':{'测试':'别名','别名':'测试'}}
    try:
        sync.apply(c,{'base_revision':remote['revision'],'conf':conf})
        assert False
    except ValueError:
        pass
    conf.pop('graph')
    sync.apply(c,{'base_revision':remote['revision'],'conf':conf})
    assert store.state(c,True)['conf']['models'][0]['key']=='PRIVATE'
    c.close()


def test_semantic_disabled_has_no_network_and_validates_vectors(tmp_path):
    c=db.connect(tmp_path/'semantic.db');store.load_state(c,demo.state())
    with patch('urllib.request.urlopen',side_effect=AssertionError('must not call')):
        assert semantic.related(c,'i-rain')=={'enabled':False,'related':[]}
    conf={'models':[{'id':'embed','name':'Embedding','base':'https://example.test/v1','model':'vector'}],
          'embeddings':{'enabled':True,'model_id':'embed'}}
    store.load_state(c,{'conf':conf})
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,*args): return self.content
    calls=[]
    def model(req,timeout):
        payload=json.loads(req.data);calls.append(payload)
        response=Response()
        response.content=json.dumps({'data':[{'index':i,'embedding':[1,0.5,0.2]} for i in range(len(payload['input']))]}).encode()
        return response
    with patch('urllib.request.urlopen',side_effect=model):
        result=semantic.related(c,'i-rain');count=len(calls)
        assert result['enabled'] and result['related'] and result['embedded_documents']>0
        assert semantic.related(c,'i-rain')['embedded_documents']==0 and len(calls)==count
    db.kv_set(c,'embeddings_cache',{});c.commit()
    def bad(req,timeout):
        response=Response();response.content=b'{"data":[{"index":0,"embedding":[NaN]}]}'
        return response
    with patch('urllib.request.urlopen',side_effect=bad):
        try: semantic.related(c,'i-rain');assert False
        except ValueError: pass
    assert db.kv_get(c,'embeddings_cache')=={}
    c.close()
