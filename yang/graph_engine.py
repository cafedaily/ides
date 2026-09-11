"""Exact incremental graph maintenance; no stored claim substitutes for recomputation.

Source changes update per-document n-gram statistics. Entity selection reuses those
statistics; only documents containing changed entities are retokenized. Global
IDF is rescored exactly. Cooccurrence counts and pair topology are updated only
where their inputs changed, while numerical pair scores track current weights.
"""
import hashlib
import itertools
import json
import math
import time
from collections import Counter, defaultdict
from . import entity, quality, terms
from .text import runs_of


def signature(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()


class GraphCache:
    def __init__(self):
        self.clear()

    def clear(self):
        self.documents = {}
        self.doc_signatures = {}
        self.stats = {}
        self.counts = Counter()
        self.left = defaultdict(Counter)
        self.entities = set()
        self.raw = {}
        self.vectors = {}
        self.topologies = {}
        self.pairs = {}
        self.score_templates = {}
        self.topology_ids = {}
        self.term_sets = {}
        self.term_docs = Counter()
        self.co_counts = Counter()
        self.evidence_cache = {}
        self.settings_signature = None
        self.result = None
        self.metrics = {}

    def _change_stats(self, stats, sign):
        counts, left = stats
        for token, value in counts.items():
            self.counts[token] += sign * value
            if self.counts[token] <= 0:
                self.counts.pop(token, None)
        for token, chars in left.items():
            for char in chars:
                self.left[token][char] += sign
                if self.left[token][char] <= 0:
                    del self.left[token][char]
            if not self.left[token]:
                del self.left[token]

    def update(self, documents, settings=None, force=False):
        started = time.perf_counter()
        settings = settings or {}
        setting_sig = signature(settings)
        if force or setting_sig != self.settings_signature:
            self.clear()
            self.settings_signature = setting_sig
        docs = {doc["id"]: doc for doc in sorted(documents, key=lambda doc: doc["id"])}
        if len(docs) != len(documents):
            raise ValueError("Duplicate graph document ID")
        signatures = {identifier: signature(doc) for identifier, doc in docs.items()}
        changed = {identifier for identifier in self.doc_signatures.keys() | signatures.keys() if self.doc_signatures.get(identifier) != signatures.get(identifier)}
        if not changed and self.result is not None:
            self.metrics = {"changed_documents":0,"retokenized_documents":0,"pairs_recomputed":0,"seconds":time.perf_counter()-started,"cache_hit":True}
            return self.result
        normalizer = quality.Normalizer(settings)
        for identifier in changed:
            if identifier in self.stats:
                self._change_stats(self.stats.pop(identifier), -1)
            self.evidence_cache.pop(identifier, None)
            if identifier not in docs:
                self.raw.pop(identifier, None)
                continue
            doc = normalizer.document(docs[identifier])
            stats = entity._counts([run for piece in doc["pieces"] for run in runs_of(piece["text"])])
            self.stats[identifier] = stats
            self._change_stats(stats, 1)
        discovered = entity.discover_counts(self.counts, self.left)
        entity_delta = discovered ^ self.entities
        retokenized = 0
        for identifier, doc in docs.items():
            normalized = normalizer.document(doc)
            if identifier in changed or identifier not in self.raw or any(token in piece["text"] for token in entity_delta for piece in normalized["pieces"]):
                self.raw[identifier] = terms._doc_terms(normalized, discovered)
                retokenized += 1
        scored = terms.score_raw(list(docs.values()), self.raw, settings=settings)
        vectors = {identifier: {item["term"]: item for item in items} for identifier, items in scored.items()}
        topologies = {identifier: tuple((term, tuple(sorted(item["dims"]))) for term, item in sorted(vector.items())) for identifier, vector in vectors.items()}
        weights = {identifier: tuple((term, item["w"]) for term, item in sorted(vector.items())) for identifier, vector in vectors.items()}
        old_weights = {identifier: tuple((term, item["w"]) for term, item in sorted(vector.items())) for identifier, vector in self.vectors.items()}
        topology_changes = {identifier for identifier in self.topologies.keys() | topologies.keys() if self.topologies.get(identifier) != topologies.get(identifier)}
        weight_changes = {identifier for identifier in weights if weights[identifier] != old_weights.get(identifier)}
        for identifier in self.term_sets.keys() | vectors.keys():
            old, new = self.term_sets.get(identifier, set()), set(vectors.get(identifier, {}))
            if old != new:
                self.term_docs.subtract(old)
                self.term_docs.update(new)
                self.co_counts.subtract(itertools.combinations(sorted(old), 2))
                self.co_counts.update(itertools.combinations(sorted(new), 2))
        self.term_sets = {identifier:set(vector) for identifier, vector in vectors.items()}
        self.co_counts = +self.co_counts
        self.term_docs = +self.term_docs
        pairs, sim_candidates, bridge_candidates = {}, [], []
        projection_cache, projection_ids, projection_values, score_templates = {}, {}, {}, {}
        recomputed = 0
        from .graph import _dim_bonus, MIN_SIM, MIN_BRIDGE, PER_PAIR, TOP_SIM, MIN_NPMI
        for a, b in itertools.combinations(docs, 2):
            previous = self.pairs.get((a,b))
            if previous is not None and a not in topology_changes and b not in topology_changes:
                shared = previous[0]
                topology_id = previous[3]
            else:
                shared = tuple((term, _dim_bonus(set(vectors[a][term]["dims"]),set(vectors[b][term]["dims"]))) for term in sorted(vectors[a].keys() & vectors[b].keys()))
                topology_id = self.topology_ids.setdefault(shared, len(self.topology_ids))
            if not shared:
                pair = (shared, None, (), topology_id)
            elif previous is not None and shared == previous[0] and a not in weight_changes and b not in weight_changes:
                pair = previous
            else:
                recomputed += 1
                ids = []
                for identifier in (a,b):
                    projection_key = (identifier, topology_id)
                    projection_id = projection_cache.get(projection_key)
                    if projection_id is None:
                        values = tuple(vectors[identifier][term]["w"] for term, _bonus in shared)
                        projection_id = projection_ids.setdefault(values, len(projection_ids))
                        projection_values[projection_id] = values
                        projection_cache[projection_key] = projection_id
                    ids.append(projection_id)
                score_key = (topology_id, min(ids), max(ids))
                template = score_templates.get(score_key)
                if template is None:
                    products = [(term, wa*wb, bonus) for (term,bonus),wa,wb in zip(shared,projection_values[ids[0]],projection_values[ids[1]])]
                    similarity = sum(product for _, product, _ in products)
                    shared_top = tuple(term for term,_,_ in sorted(products,key=lambda x:(-x[1],x[0]))[:5])
                    best = tuple(sorted(((round(product*bonus,5),term,bonus) for term,product,bonus in products if product*bonus>=MIN_BRIDGE),key=lambda x:(-x[0],x[1]))[:PER_PAIR])
                    template = (round(similarity,4) if similarity>=MIN_SIM else None, shared_top, best)
                    score_templates[score_key] = template
                sim = {"a":a,"b":b,"sim":template[0],"shared":list(template[1])} if template[0] is not None else None
                bridges = tuple((score,term,a,b,bonus) for score,term,bonus in template[2])
                pair = (shared, sim, bridges, topology_id)
            pairs[(a,b)] = pair
            if pair[1]: sim_candidates.append(pair[1])
            bridge_candidates.extend(pair[2])
        sim_candidates.sort(key=lambda item:(-item["sim"],item["a"],item["b"]))
        sim, degree = [], Counter()
        for item in sim_candidates:
            if degree[item["a"]]>=TOP_SIM and degree[item["b"]]>=TOP_SIM: continue
            sim.append(item);degree[item["a"]]+=1;degree[item["b"]]+=1
        bridges = []
        for score, term, a, b, bonus in sorted(bridge_candidates,key=lambda x:(-x[0],x[1],x[2],x[3]))[:60]:
            say = []
            for identifier in (a,b):
                cache = self.evidence_cache.setdefault(identifier,{})
                if term not in cache: cache[term] = normalizer.evidence(docs[identifier],term)
                say.append(cache[term])
            bridges.append({"term":term,"a":a,"b":b,"score":score,"bonus":bonus,"a_dims":sorted(vectors[a][term]["dims"]),"b_dims":sorted(vectors[b][term]["dims"]),"a_title":docs[a]["title"],"b_title":docs[b]["title"],"a_say":say[0],"b_say":say[1]})
        cooc, n = [], max(1,len(docs))
        for (a,b), count in self.co_counts.items():
            if count<2 or count>=n: continue
            pab=count/n
            npmi=math.log(pab/((self.term_docs[a]/n)*(self.term_docs[b]/n)))/(-math.log(pab))
            if npmi>=MIN_NPMI: cooc.append({"a":a,"b":b,"n":count,"npmi":round(npmi,4)})
        cooc.sort(key=lambda item:(-item["npmi"],item["a"],item["b"]))
        nodes=[{"id":"idea:"+identifier,"type":doc["kind"],"label":doc["title"],"ref":identifier,"n_terms":len(scored[identifier])} for identifier,doc in docs.items()]
        term_nodes,edges={},[]
        for identifier,items in scored.items():
            for item in items:
                term=item["term"];node=term_nodes.setdefault(term,{"id":"term:"+term,"type":"term","label":term,"ref":term,"docs":0,"w":0.0})
                node["docs"]+=1;node["w"]=round(node["w"]+item["w"],5)
                edges.append({"a":"idea:"+identifier,"b":"term:"+term,"type":"has","w":item["w"],"dims":item["dims"]})
        nodes.extend(term_nodes[term] for term in sorted(term_nodes))
        result={"nodes":nodes,"edges":edges,"terms":scored,"cooc":cooc,"sim":sim,"bridges":bridges,
                "quality":{"aliases":normalizer.mapping,"adaptive_stopwords":sorted(quality.stopwords(self.raw,settings)),"entities":len(discovered)}}
        self.documents,self.doc_signatures,self.entities=docs,signatures,discovered
        self.vectors,self.topologies,self.pairs=vectors,topologies,pairs
        self.result=result
        self.metrics={"changed_documents":len(changed),"retokenized_documents":retokenized,"pairs_recomputed":recomputed,"pairs_total":len(pairs),"seconds":time.perf_counter()-started,"cache_hit":False}
        return result
