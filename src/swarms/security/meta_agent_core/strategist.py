#!/usr/bin/env python3

from __future__ import annotations

from src.intelligence.llm_client import LLMClient

from .models import SecurityDecision


class SecurityStrategist:
    def __init__(self) -> None:
        self.llm = LLMClient(n_ctx=4096)

    def refine(self, decision: SecurityDecision) -> SecurityDecision:
        return decision