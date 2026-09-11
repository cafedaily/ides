"""Atomic optimistic sync. A conflict never mutates the database."""
import copy
from . import db, jsonl, quality, store

COLLECTIONS = {'ideas': ('idea', store.put_idea), 'sparks': ('spark', store.put_spark),
               'cold': ('cold', store.put_cold)}


class Conflict(Exception):
    def __init__(self, revision):
        self.revision = revision


def validate_state(state):
    if not isinstance(state, dict):
        raise ValueError('状态必须是对象。')
    seen = set()
    for collection, (kind, _) in COLLECTIONS.items():
        rows = state.get(collection, [])
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError('记录必须是列表，最多 10000 条。')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('记录必须是对象。')
            errors = jsonl.check_record({**row, 't':kind}, 0)
            if errors:
                raise ValueError(errors[0]['msg'])
            if row['id'] in seen:
                raise ValueError('记录 id 必须跨集合唯一。')
            seen.add(row['id'])
    conf = state.get('conf')
    if conf is not None:
        if not isinstance(conf, dict):
            raise ValueError('配置必须是对象。')
        errors = jsonl.check_record({**conf, 't':'conf'}, 0)
        if errors:
            raise ValueError(errors[0]['msg'])
        models = conf.get('models') or []
        ids = [m.get('id') for m in models]
        if len(models) > 30 or any(not isinstance(i,str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('模型 id 必须唯一，最多 30 个模型。')
        settings = conf.get('graph') or {}
        if not isinstance(settings, dict):
            raise ValueError('图谱设置必须是对象。')
        quality.Normalizer(settings)
        quality.stopwords({}, settings)


def apply(c, body):
    if not isinstance(body, dict) or type(body.get('base_revision')) is not int or body['base_revision'] < 0:
        raise ValueError('必须提供非负整数 base_revision。')
    changes = body.get('changes', {})
    if not isinstance(changes, dict) or set(changes) - COLLECTIONS.keys():
        raise ValueError('changes 仅支持 ideas、sparks、cold。')
    c.execute('BEGIN IMMEDIATE')
    try:
        revision = db.kv_get(c, 'revision', 0)
        if revision != body['base_revision']:
            raise Conflict(revision)
        current = store.state(c)
        prospective = copy.deepcopy(current)
        mutations = []
        for name, change in changes.items():
            if not isinstance(change, dict) or set(change) - {'upsert','delete'}:
                raise ValueError('集合变更仅支持 upsert 和 delete。')
            upsert, deleted = change.get('upsert',[]), change.get('delete',[])
            if not isinstance(upsert,list) or not isinstance(deleted,list) or not all(jsonl._is_id(i) for i in deleted):
                raise ValueError('upsert/delete 格式错误。')
            if not all(isinstance(row,dict) and jsonl._is_id(row.get('id')) for row in upsert):
                raise ValueError('upsert 记录 id 无效。')
            ids = [row['id'] for row in upsert]
            if len(ids) != len(set(ids)) or set(ids) & set(deleted):
                raise ValueError('同一请求不能重复更新或删除同一记录。')
            mapping = {row['id']:row for row in prospective[name]}
            for identifier in deleted:
                mapping.pop(identifier, None)
            mapping.update({row['id']:row for row in upsert})
            prospective[name] = list(mapping.values())
            mutations.append((name,upsert,deleted))
        if 'conf' in body:
            prospective['conf'] = body['conf']
        validate_state(prospective)
        for name, upsert, deleted in mutations:
            for identifier in deleted:
                c.execute('DELETE FROM '+name+' WHERE id=?', (identifier,))
            for row in upsert:
                COLLECTIONS[name][1](c,row)
        if 'conf' in body:
            db.kv_set(c,'conf',store._merge_conf_keys(c,body['conf']))
        db.kv_set(c,'revision',revision+1)
        c.commit()
        return {'ok':True,'revision':revision+1}
    except BaseException:
        c.rollback()
        raise
