#!/usr/bin/env python3
"""
Explorer MetaAgent – analyzes findings and suggests new targets.

This agent acts as a higher-level intelligence within the swarm, consuming
web exploration findings from ExplorerNode agents, classifying them using
a Large Language Model (LLM), and generating new, relevant URLs to explore.
It publishes these new targets back into the CRDT for ExplorerNodes to pick up.
"""
import asyncio
import logging
import os
import sys
import time
import uuid
import json
import re
from typing import Dict, Any, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ExplorerMetaAgent")

class ExplorerMetaAgent:
    """
    Explorer MetaAgent analyzes findings from ExplorerNode agents and suggests new targets.

    It uses an LLM to classify web findings (USEFUL, HARMFUL, NEUTRAL) and
    generates new URLs based on useful findings, publishing them to the CRDT.
    """
    def __init__(self):
        """
        Initializes the ExplorerMetaAgent with a unique node ID,
        an LLM client configured for smaller contexts, and a CRDT adapter.
        """
        self.node_id: str = f"exp-meta-{uuid.uuid4().hex[:8]}"
        # Using a smaller context to reduce load and cost for classification/generation tasks.
        self.llm: LLMClient = LLMClient(n_ctx=2048)
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step: int = 0
        logger.info(f"🔎 Initializing ExplorerMetaAgent with ID: {self.node_id}")

    async def run(self) -> None:
        """
        Runs the main operational loop of the ExplorerMetaAgent.

        It periodically calls the `reflect` method to process findings and suggest new targets.
        The reflection interval is determined by `self.step % 100 == 0` which, with a 1-second
        sleep, means roughly every 100 seconds.
        """
        logger.info(f"🔎 ExplorerMetaAgent {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 100 == 0:
                logger.debug(f"Executing reflection cycle (step {self.step}).")
                await self.reflect()
            await asyncio.sleep(1.0)

    async def reflect(self) -> None:
        """
        Performs the reflection process, which involves:
        1. Retrieving all "explorer_finding" entries from the CRDT.
        2. Classifying a subset of these findings using the LLM into categories
           like USEFUL, HARMFUL, or NEUTRAL, and updating their classification in CRDT.
        3. Generating new related URLs based on "USEFUL" findings using the LLM.
        4. Publishing these newly suggested URLs as "explorer_targets" to the CRDT.

        Error handling is included to catch issues during LLM interaction or CRDT updates.
        """
        try:
            findings_to_classify: List[Dict[str, Any]] = await self._get_findings_for_classification()
            if not findings_to_classify:
                logger.debug("No new findings to classify.")
                return

            classified_findings: List[Dict[str, Any]] = await self._classify_findings(findings_to_classify)
            await self._generate_new_targets(classified_findings)

        except Exception as e:
            logger.error(f"ExplorerMetaAgent reflection failed: {e}", exc_info=True)

    async def _get_findings_for_classification(self) -> List[Dict[str, Any]]:
        """
        Retrieves "explorer_finding" entries from the CRDT that have not yet been classified,
        or those recently updated.

        Returns:
            List[Dict[str, Any]]: A list of finding dictionaries suitable for classification.
        """
        # CRDTAdapter.state is assumed to be an in-memory representation, hence not awaited.
        all_state: Dict[str, Any] = self.crdt.state
        findings: List[Dict[str, Any]] = [
            v for k, v in all_state.items()
            if isinstance(v, dict) and v.get("type") == "explorer_finding"
        ]
        # Prioritize unclassified findings or those without a recent classification update
        # For simplicity, we just take the first N findings to process in a cycle
        return findings[-5:] # Process the 5 most recent findings

    async def _classify_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Classifies a subset of findings using the LLM and updates their classification in the CRDT.

        Args:
            findings (List[Dict[str, Any]]): A list of finding dictionaries to classify.

        Returns:
            List[Dict[str, Any]]: The list of findings after classification and CRDT update.
        """
        classified_results: List[Dict[str, Any]] = []
        for f in findings:
            # Skip if already classified in this run, or if content is missing
            if f.get("classification") in ("USEFUL", "HARMFUL", "NEUTRAL") or not f.get("content_preview"):
                classified_results.append(f)
                continue

            content: str = f.get("content_preview", "")
            url: str = f.get("url", "N/A")
            prompt: str = f"""User: Classify this web finding from {url}. Content preview: {content}
Categories: USEFUL, HARMFUL, NEUTRAL. Output ONLY one word.
Assistant: """
            response: Optional[str] = self.llm.generate(prompt, max_tokens=10, temperature=0.2)
            if response:
                classification: str = response.strip().upper()
                if classification in ("USEFUL", "HARMFUL", "NEUTRAL"):
                    # Create a copy to avoid modifying the CRDT state directly without proper synchronization
                    # or unintentional side effects. Add a unique ID for the update.
                    updated_finding = f.copy()
                    updated_finding["classification"] = classification
                    updated_finding["timestamp"] = time.time() # Update timestamp to mark as fresh
                    updated_finding["gid"] = f"exp_f_{int(time.time())}_{uuid.uuid4().hex[:4]}" # New GID for update
                    await self.crdt.add_genome(updated_finding)
                    classified_results.append(updated_finding)
                    logger.info(f"Classified {url} as: {classification}")
                else:
                    logger.warning(f"LLM returned invalid classification '{classification}' for {url}.")
                    classified_results.append(f) # Keep original if classification is invalid
            else:
                logger.warning(f"LLM failed to classify URL: {url}")
                classified_results.append(f) # Keep original if LLM failed
        return classified_results

    async def _generate_new_targets(self, classified_findings: List[Dict[str, Any]]) -> None:
        """
        Generates new related URLs based on "USEFUL" findings using the LLM
        and publishes them as "explorer_targets" to the CRDT.

        Args:
            classified_findings (List[Dict[str, Any]]): A list of findings, some of which may be classified.
        """
        useful_findings: List[Dict[str, Any]] = [f for f in classified_findings if f.get("classification") == "USEFUL"]
        if not useful_findings:
            logger.debug("No useful findings to generate new targets from.")
            return

        # Filter for non-None URLs before joining
        # Use up to 3 most recent useful findings for context
        url_list: List[str] = [f_url for f in useful_findings[-3:] if (f_url := f.get("url")) is not None]
        if not url_list:
            logger.debug("No valid URLs found in useful findings to base new suggestions on.")
            return

        prompt: str = f"User: Based on these useful URLs: {', '.join(url_list)}. Suggest 2 new related URLs. Output ONLY JSON with 'urls' array.\nAssistant: {{"
        response: Optional[str] = self.llm.generate(prompt, max_tokens=80, temperature=0.3)

        if response:
            json_match = re.search(r'{.*}', response, re.DOTALL)
            if json_match:
                candidate_json_str = json_match.group(0)
                try:
                    data: Dict[str, Any] = json.loads(candidate_json_str)
                    if "urls" in data and isinstance(data["urls"], list):
                        new_urls: List[str] = [str(u).strip() for u in data["urls"] if isinstance(u, str) and u.strip()]
                        if new_urls:
                            cmd: Dict[str, Any] = {
                                "type": "explorer_targets",
                                "data": {"urls": new_urls},
                                "timestamp": time.time(),
                                "gid": f"exp_targets_{int(time.time())}_{uuid.uuid4().hex[:4]}",
                            }
                            await self.crdt.add_genome(cmd)
                            logger.info(f"🔎 ExplorerMetaAgent suggested URLs: {new_urls}")
                        else:
                            logger.warning(f"LLM suggested an empty or invalid list of URLs from response: {response}")
                    else:
                        logger.warning(f"LLM response JSON missing 'urls' key or it's not a list: {response}")
                except json.JSONDecodeError as jde:
                    logger.error(f"Failed to parse LLM's JSON response for new URLs. Response: '{response}'. Error: {jde}")
            else:
                logger.warning(f"Could not find JSON in LLM response for new URLs: {response}")
        else:
            logger.warning("LLM failed to generate new URLs.")


if __name__ == "__main__":
    node: ExplorerMetaAgent = ExplorerMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerMetaAgent stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"ExplorerMetaAgent encountered a fatal error: {e}", exc_info=True)