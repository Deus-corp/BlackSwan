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
from typing import Dict, Any, List, Optional, Match, Literal, TypedDict

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)


# --- Type Definitions for CRDT Records ---

class ExplorerFinding(TypedDict):
    """
    Represents a web exploration finding stored in the CRDT.
    Fields are designed to match CRDT entries with specific types and expected content.
    """
    type: Literal["explorer_finding"]
    url: Optional[str] # Can be None if URL was not captured or invalid
    content_preview: Optional[str] # Can be None if content could not be extracted
    classification: Literal['USEFUL', 'HARMFUL', 'NEUTRAL', 'unclassified']
    timestamp: float
    gid: str # Global ID, unique identifier for the entry


class ExplorerTargetsData(TypedDict):
    """Specific data structure for the 'data' field of explorer_targets."""
    urls: List[str]


class ExplorerTargets(TypedDict):
    """Represents a set of new URLs suggested for exploration."""
    type: Literal["explorer_targets"]
    data: ExplorerTargetsData
    timestamp: float
    gid: str # Global ID, unique identifier for the entry


class ExplorerMetaAgent:
    """
    Explorer MetaAgent analyzes findings from ExplorerNode agents and suggests new targets.

    It uses an LLM to classify web findings (USEFUL, HARMFUL, NEUTRAL) and
    generates new URLs based on useful findings, publishing them to the CRDT.
    """
    def __init__(self) -> None:
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
        1. Retrieving "explorer_finding" entries from the CRDT that need classification.
        2. Classifying a subset of these findings using the LLM into categories
           like USEFUL, HARMFUL, or NEUTRAL, and updating their classification in CRDT.
        3. Generating new related URLs based on "USEFUL" findings using the LLM.
        4. Publishing these newly suggested URLs as "explorer_targets" to the CRDT.

        Error handling is included to catch issues during LLM interaction or CRDT updates.
        """
        try:
            findings_to_classify: List[ExplorerFinding] = await self._get_findings_for_classification()
            if not findings_to_classify:
                logger.debug("No new unclassified findings to process.")
                return

            classified_findings: List[ExplorerFinding] = await self._classify_findings(findings_to_classify)
            await self._generate_new_targets(classified_findings)

        except Exception as e:
            logger.error(f"ExplorerMetaAgent reflection failed: {e}", exc_info=True)

    async def _get_findings_for_classification(self) -> List[ExplorerFinding]:
        """
        Retrieves "explorer_finding" entries from the CRDT that have not yet been classified.

        It sorts them by timestamp and returns the 5 most recent unclassified findings.

        Returns:
            List[ExplorerFinding]: A list of finding dictionaries suitable for classification.
        """
        all_state: Dict[str, Any] = self.crdt.state
        unclassified_findings_raw: List[Dict[str, Any]] = []

        for v in all_state.values():
            if (isinstance(v, dict) and
                    v.get("type") == "explorer_finding" and
                    v.get("gid") is not None): # GID is essential for CRDT entries

                # Ensure 'classification' is one of the Literal types or 'unclassified'
                classification_value = v.get("classification")
                if classification_value not in ('USEFUL', 'HARMFUL', 'NEUTRAL', 'unclassified'):
                    classification_value = 'unclassified' # Default to unclassified if invalid or missing

                # Only consider findings that are currently unclassified
                if classification_value == 'unclassified':
                    finding_copy = v.copy()
                    finding_copy.setdefault("timestamp", 0.0) # Ensure timestamp for sorting
                    finding_copy["classification"] = classification_value # Set normalized classification
                    finding_copy.setdefault("url", None) # Explicitly set to None if missing for TypedDict
                    finding_copy.setdefault("content_preview", None) # Explicitly set to None if missing for TypedDict
                    unclassified_findings_raw.append(finding_copy)


        # Sort by timestamp in descending order to get the most recent unclassified ones
        unclassified_findings_raw.sort(key=lambda x: x.get("timestamp", 0.0), reverse=True)

        # Process up to 5 of the most recent unclassified findings in each cycle
        # Convert raw dictionaries to ExplorerFinding TypedDicts
        return [ExplorerFinding(**f) for f in unclassified_findings_raw[:5]]

    async def _classify_findings(self, findings: List[ExplorerFinding]) -> List[ExplorerFinding]:
        """
        Classifies a subset of findings using the LLM and updates their classification in the CRDT.

        Args:
            findings: A list of finding dictionaries to classify.

        Returns:
            The list of findings after classification and CRDT update. Includes
            both originally classified findings and newly classified ones.
        """
        classified_results: List[ExplorerFinding] = []
        for f in findings:
            # Skip if already classified, or if content_preview is missing
            if f["classification"] in ("USEFUL", "HARMFUL", "NEUTRAL") or not f.get("content_preview"):
                classified_results.append(f)
                continue

            content: str = f.get("content_preview", "") # Can be None, so use .get with default
            url: str = f.get("url", "N/A") # Can be None, so use .get with default
            prompt: str = f"""User: Classify this web finding from {url}. Content preview: {content}
Categories: USEFUL, HARMFUL, NEUTRAL. Output ONLY one word.
Assistant: """
            response: Optional[str] = self.llm.generate(prompt, max_tokens=10, temperature=0.2)
            if response:
                # Remove XML tags (e.g., <think>, </think>) that LLM sometimes outputs
                cleaned_response: str = re.sub(r'<[^>]+>', '', response).strip()
                classification: str = cleaned_response.upper()
                if classification in ("USEFUL", "HARMFUL", "NEUTRAL"):
                    # IMPORTANT CRDT NOTE: The original code generates a *new* GID for an update.
                    # This implies that each classification event creates a new CRDT record,
                    # rather than updating the existing one in place. This specific CRDT
                    # implementation might reconcile these later. Preserving original behavior,
                    # which means creating a new GID and timestamp for the updated classification.
                    updated_finding: ExplorerFinding = f.copy() # type: ignore [misc] # Copying a TypedDict returns dict, requires cast for re-assignment
                    updated_finding["classification"] = classification # type: ignore [assignment] # Literal assignment check for mypy
                    updated_finding["timestamp"] = time.time() # Update timestamp to mark as fresh
                    updated_finding["gid"] = f"exp_f_{int(time.time())}_{uuid.uuid4().hex[:4]}" # New GID for this update event
                    await self.crdt.add_genome(updated_finding)
                    classified_results.append(updated_finding)
                    logger.info(f"Classified {url} as: {classification}")
                else:
                    logger.warning(f"LLM returned invalid classification '{classification}' for {url}. Keeping original finding.")
                    classified_results.append(f) # Keep original if classification is invalid (unclassified)
            else:
                logger.warning(f"LLM failed to classify URL: {url}. Keeping original finding.")
                # If LLM failed, the finding remains 'unclassified' (or whatever it was before)
                classified_results.append(f)
        return classified_results

    async def _generate_new_targets(self, classified_findings: List[ExplorerFinding]) -> None:
        """
        Generates new related URLs based on "USEFUL" findings using the LLM
        and publishes them as "explorer_targets" to the CRDT.

        Args:
            classified_findings: A list of findings, some of which may be classified.
        """
        useful_findings: List[ExplorerFinding] = [f for f in classified_findings if f["classification"] == "USEFUL"]
        if not useful_findings:
            logger.debug("No useful findings to generate new targets from.")
            return

        # Use up to 3 most recent useful findings for context to generate new URLs
        # Filter for non-None URLs before joining
        recent_useful_urls: List[str] = [
            str(f_url) for f in useful_findings[-3:]
            if (f_url := f["url"]) is not None and isinstance(f_url, str) and f_url.strip()
        ]

        if not recent_useful_urls:
            logger.debug("No valid URLs found in useful findings to base new suggestions on.")
            return

        prompt: str = f"User: Based on these useful URLs: {', '.join(recent_useful_urls)}. Suggest 2 new related URLs. Output ONLY JSON with 'urls' array.\nAssistant: {{"
        response: Optional[str] = self.llm.generate(prompt, max_tokens=80, temperature=0.3)

        if response:
            json_match: Optional[Match[str]] = re.search(r'{.*}', response, re.DOTALL)
            if json_match:
                candidate_json_str: str = json_match.group(0)
                try:
                    data: Dict[str, Any] = json.loads(candidate_json_str)
                    if "urls" in data and isinstance(data["urls"], list):
                        # Filter for valid, non-empty string URLs
                        new_urls: List[str] = [str(u).strip() for u in data["urls"] if isinstance(u, str) and u.strip()]
                        if new_urls:
                            cmd: ExplorerTargets = { # type: ignore [assignment] # Safely assign dict to TypedDict after verification
                                "type": "explorer_targets",
                                "data": {"urls": new_urls},
                                "timestamp": time.time(),
                                "gid": f"exp_targets_{int(time.time())}_{uuid.uuid4().hex[:4]}",
                            }
                            await self.crdt.add_genome(cmd) # type: ignore [arg-type] # CRDTAdapter expects Dict[str, Any]
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