from __future__ import annotations

import json
from typing import Any, Dict, List

from .types import ExplorerFinding


def build_classification_prompt(findings: List[ExplorerFinding]) -> str:
    payload = {
        "task": "Classify each web finding as USEFUL, HARMFUL, or NEUTRAL.",
        "rules": [
            "USEFUL means likely worth deeper exploration or likely to lead to new relevant URLs.",
            "HARMFUL means spam, malicious, irrelevant, or low-trust content.",
            "NEUTRAL means neither clearly useful nor harmful.",
            "Return JSON only.",
        ],
        "items": [
            {
                "source_gid": f["source_gid"],
                "url": f.get("url"),
                "content_preview": (f.get("content_preview") or "")[:1500],
                "domain": f.get("domain"),
            }
            for f in findings
        ],
        "output_schema": {
            "items": [
                {
                    "source_gid": "...",
                    "url": "https://...",
                    "classification": "USEFUL|HARMFUL|NEUTRAL",
                    "confidence": 0.0,
                    "reason": "short reason",
                }
            ]
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_target_prompt(context_urls: List[str], findings: List[ExplorerFinding], top_domains: List[Dict[str, Any]]) -> str:
    payload = {
        "task": "Suggest 2-5 new related exploration targets.",
        "constraints": [
            "Prefer URLs on the same domain or closely related domains when appropriate.",
            "Avoid duplicates and obvious tracking variants.",
            "Avoid non-http(s) URLs.",
            "Return JSON only.",
        ],
        "context_urls": context_urls,
        "supporting_findings": [
            {
                "source_gid": f.get("source_gid"),
                "url": f.get("url"),
                "classification": f.get("classification"),
                "confidence": f.get("confidence", 0.0),
                "reason": f.get("reason", ""),
                "domain": f.get("domain"),
            }
            for f in findings
        ],
        "top_domains": top_domains,
        "output_schema": {"urls": ["https://example.com/path"]},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
