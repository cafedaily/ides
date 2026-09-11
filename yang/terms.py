"""Dimension-weighted TF-IDF with shared full/incremental scoring."""
import math
from collections import Counter, defaultdict
from . import entity, quality
from .text import GENERIC, NUM_HEAD, candidates

DIM_W = {"title":1.7,"now":1.35,"seed":1.2,"ask":1.0,"angle":1.0,"collide":1.0,"note":0.9,"why":1.3,"spark":1.1}
DIMS = tuple(DIM_W)
TOP_N, MIN_W, GENERIC_W = 24, 0.04, 0.45


def _doc_terms(doc, entities=None):
    tf, dims = Counter(), defaultdict(Counter)
    for piece in doc["pieces"]:
        dim = piece["dim"]
        for term, count in candidates(piece["text"], entities).items():
            tf[term] += count * DIM_W.get(dim, 1.0)
            dims[term][dim] += count
    return tf, dims


def score_raw(docs, raw, top_n=TOP_N, min_w=MIN_W, settings=None):
    excluded = quality.stopwords(raw, settings)
    df = Counter(term for tf, _dims in raw.values() for term in tf if term not in excluded)
    n, out = max(1, len(docs)), {}
    for doc in docs:
        source_tf, dims = raw[doc["id"]]
        tf = {term: value for term, value in source_tf.items() if term not in excluded}
        if not tf:
            out[doc["id"]] = []
            continue
        scored = []
        for term, frequency in tf.items():
            if df[term] < 2 and len(term) <= 2 and not term.isascii():
                continue
            idf = math.log((n + 1) / (df[term] + 1)) + 1.0
            scored.append((term, (1 + math.log(frequency)) * idf))
        if not scored:
            scored = [(term, 1.0) for term in tf]
        norm = math.sqrt(sum(weight * weight for _, weight in scored)) or 1.0
        items = []
        for term, weight in scored:
            weak = term in GENERIC or (len(term) == 2 and term[0] in NUM_HEAD)
            normalized = weight / norm * (GENERIC_W if weak else 1.0)
            if normalized >= min_w:
                items.append({"term":term,"w":round(normalized,5),"tf":round(tf[term],3),"df":df[term],"dims":dict(dims[term])})
        items.sort(key=lambda item: (-item["w"], item["term"]))
        out[doc["id"]] = items[:top_n]
    return out


def extract(docs, top_n=TOP_N, min_w=MIN_W, entities=None, settings=None):
    normalizer = quality.Normalizer(settings)
    normalized = [normalizer.document(doc) for doc in docs]
    if entities is None:
        entities = entity.discover(piece["text"] for doc in normalized for piece in doc["pieces"])
    raw = {doc["id"]: _doc_terms(doc, entities) for doc in normalized}
    return score_raw(docs, raw, top_n, min_w, settings)
