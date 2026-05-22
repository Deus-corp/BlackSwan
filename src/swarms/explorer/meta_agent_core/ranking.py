from __future__ import annotations

from typing import Dict, List, Tuple

from .types import ExplorerFinding
from .utils import extract_domain


def rank_and_deduplicate_targets(urls: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def score_targets(urls: List[str], supporting_findings: List[ExplorerFinding]) -> List[Tuple[str, float]]:
    domain_counts: Dict[str, int] = {}
    for finding in supporting_findings:
        domain = finding.get("domain") or extract_domain(finding.get("url"))
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    scored: List[Tuple[str, float]] = []
    for url in urls:
        domain = extract_domain(url) or ""
        domain_bonus = min(0.3, 0.1 * domain_counts.get(domain, 0))
        score = 0.55 + domain_bonus + 0.05
        if any(domain and domain == (f.get("domain") or extract_domain(f.get("url"))) for f in supporting_findings):
            score += 0.15
        scored.append((url, min(1.0, score)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored