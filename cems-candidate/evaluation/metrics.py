"""
evaluation/metrics.py -- metric calculations for the CEMS evaluation harness (pure functions).

Conventions
  * A metric whose denominator is zero is None ("undefined"), never 0.0 or 1.0.
  * Every task result is a dict with "status":
        "ok"            metrics computed
        "no_labels"     the gold data has no labels for this task
        "no_data"       nothing to evaluate (e.g. empty gold AND empty predictions)
    plus the raw counts, so a reader can recompute any figure.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from rapidfuzz import fuzz


def safe_div(num: float, den: float) -> Optional[float]:
    return None if den == 0 else num / den


def prf(tp: int, fp: int, fn: int) -> Dict[str, Optional[float]]:
    p, r = safe_div(tp, tp + fp), safe_div(tp, tp + fn)
    f1 = None if p is None or r is None else (0.0 if p + r == 0 else 2 * p * r / (p + r))
    return {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def normalize_text(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


# ----------------------------------------------------------------- extraction

def match_comments(pred: Sequence[Dict], gold: Sequence[Dict], threshold: float = 90.0
                   ) -> List[Tuple[int, int, float]]:
    """One-to-one matching of predicted to gold comments.

    pred/gold items: {"source_file", "page", "text"}. Candidates must share source_file and page and
    have a RapidFuzz ratio >= threshold on normalised text; pairs are taken greedily by descending
    score (ties broken by input order), each item used at most once.
    -> [(pred_index, gold_index, score)]
    """
    by_key: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for gi, g in enumerate(gold):
        by_key[(str(g["source_file"]), str(g["page"]))].append(gi)
    cands = []
    for pi, p in enumerate(pred):
        pt = normalize_text(p["text"])
        for gi in by_key.get((str(p["source_file"]), str(p["page"])), []):
            score = fuzz.ratio(pt, normalize_text(gold[gi]["text"]))
            if score >= threshold:
                cands.append((-score, pi, gi))
    cands.sort()
    used_p, used_g, out = set(), set(), []
    for neg, pi, gi in cands:
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        out.append((pi, gi, -neg))
    return sorted(out)


def extraction_metrics(pred: Sequence[Dict], gold: Sequence[Dict], threshold: float = 90.0) -> Dict:
    if not gold and not pred:
        return {"status": "no_data", "n_gold": 0, "n_pred": 0}
    if not gold:
        return {"status": "no_labels", "n_gold": 0, "n_pred": len(pred)}
    matches = match_comments(pred, gold, threshold)
    tp = len(matches)
    res = prf(tp, len(pred) - tp, len(gold) - tp)
    return {"status": "ok", **res, "n": len(gold), "n_gold": len(gold), "n_pred": len(pred),
            "match_threshold": threshold}


# ----------------------------------------------------------------- classification

def classification_metrics(pairs: Iterable[Tuple[Optional[str], Optional[str]]]) -> Dict:
    """pairs: (gold_label, predicted_label) for MATCHED comments. Rows without a gold label are skipped.
    Macro-F1 averages over every label seen in gold or predictions (of the labelled rows)."""
    rows = [(normalize_text(g), normalize_text(p)) for g, p in pairs if normalize_text(g)]
    if not rows:
        return {"status": "no_labels", "n": 0}
    labels = sorted({g for g, _ in rows} | {p for _, p in rows if p})
    per_class = {}
    for lab in labels:
        tp = sum(1 for g, p in rows if g == lab and p == lab)
        fp = sum(1 for g, p in rows if g != lab and p == lab)
        fn = sum(1 for g, p in rows if g == lab and p != lab)
        per_class[lab] = prf(tp, fp, fn)
    f1s = [m["f1"] if m["f1"] is not None else 0.0 for m in per_class.values()]
    correct = sum(1 for g, p in rows if g == p)
    return {"status": "ok", "accuracy": correct / len(rows), "macro_f1": sum(f1s) / len(f1s),
            "n": len(rows), "labels": labels, "per_class": per_class}


# ----------------------------------------------------------------- duplicates

def pairs_from_groups(groups: Dict[object, Set]) -> Set[frozenset]:
    out = set()
    for members in groups.values():
        m = sorted(members, key=str)
        out.update(frozenset((a, b)) for i, a in enumerate(m) for b in m[i + 1:])
    return out


def pairs_from_links(links: Iterable[Tuple[object, object]]) -> Set[frozenset]:
    """links: (item, duplicate_of_item). Groups are connected components, so A->B and C->B make
    the pairs AB, BC and AC."""
    parent: Dict[object, object] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in links:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    groups: Dict[object, Set] = defaultdict(set)
    for x in list(parent):
        groups[find(x)].add(x)
    return pairs_from_groups(groups)


def duplicate_metrics(pred_pairs: Set[frozenset], gold_pairs: Set[frozenset], gold_labelled: bool) -> Dict:
    if not gold_labelled:
        return {"status": "no_labels"}
    if not pred_pairs and not gold_pairs:
        return {"status": "no_data", "note": "no duplicate pairs in gold or predictions",
                "n_gold_pairs": 0, "n_pred_pairs": 0}
    tp = len(pred_pairs & gold_pairs)
    return {"status": "ok", **prf(tp, len(pred_pairs) - tp, len(gold_pairs) - tp),
            "n": len(gold_pairs), "n_gold_pairs": len(gold_pairs), "n_pred_pairs": len(pred_pairs)}


# ----------------------------------------------------------------- retrieval

def retrieval_metrics(ranked: Dict[str, List[str]], relevant: Dict[str, Set[str]], k: int) -> Dict:
    """ranked: query -> retrieved item keys, best first. relevant: query -> set of relevant keys.
    Only queries with at least one relevant label are scored; the rest are counted as skipped.
    Reports mean precision@k, recall@k and hit rate@k (fraction with >= 1 relevant item in top k)."""
    if k < 1:
        raise ValueError("k must be >= 1")
    labelled = [q for q, rel in relevant.items() if rel]
    if not labelled:
        return {"status": "no_labels", "k": k, "n": 0}
    p_sum = r_sum = hits = 0.0
    missing = 0
    for q in labelled:
        top = list(ranked.get(q, []))[:k]
        if q not in ranked:
            missing += 1
        found = len(set(top) & relevant[q])
        p_sum += found / k
        r_sum += found / len(relevant[q])
        hits += 1 if found else 0
    n = len(labelled)
    return {"status": "ok", "k": k, "precision_at_k": p_sum / n, "recall_at_k": r_sum / n,
            "hit_rate_at_k": hits / n, "n": n, "queries_without_results": missing,
            "queries_skipped_unlabelled": len(relevant) - n}
