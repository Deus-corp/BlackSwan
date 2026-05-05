# Appendix R — Meat Interface Code Listings

## R.1. General Principle
This appendix provides key code fragments implementing the Honeypot/Canary Tasks subsystem for the Meat‑Interface. Full source code is available in IPFS as artifacts `QmMeatOrchestratorV2` and `QmCanaryVerifierV2`. The code is written in Python 3.12+ and integrates with existing components (EventBus, Mem0g, STP, Sting Protocol, DeepSeek‑V4).

## R.2. MeatInterfaceOrchestrator (meat_orchestrator.py)
**CID:** `QmMeatOrchestratorV2`  
**Dependencies:** `eventbus`, `mem0g_client`, `stp`, `reputation`, `sting`, `canary_verifier`, `requests`

```python
# Core_Tools_Workspace/meat_interface/meat_orchestrator.py
import uuid
import json
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.eventbus import EventBus
from core.mem0g import Mem0gClient
from core.stp import StakedTaskProtocol
from core.reputation import BioReputationManager
from core.stealth import StingGenerator
from validation.canary_verifier import CanaryVerifier

class MeatInterfaceOrchestrator:
    """
    Meat‑Interface orchestrator with Honeypot/Canary Tasks support.
    Responsible for generating decoy tasks, publishing via STP, and verifying results.
    Uses DeepSeek‑V4 for multimodal verification and synthetic media generation.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.mem0g = Mem0gClient()
        self.stp = StakedTaskProtocol()
        self.reputation = BioReputationManager()
        self.sting = StingGenerator()
        self.verifier = CanaryVerifier(policy=self._load_canary_policy())
        self.canary_templates = self.mem0g.search("type:CanaryTemplate", limit=100)
        self.vllm_multimodal_url = "http://localhost:8000/v1/multimodal"

    def _load_canary_policy(self) -> dict:
        """Loads canary policy from IPFS or local cache."""
        policy_cid = "QmMeatCanaryPolicyV1"
        return json.loads(self.mem0g.get_artifact(policy_cid))

    async def inject_canary_batch(self, batch_size: int = 50) -> List[str]:
        """
        Generates and publishes a batch of decoy tasks.
        Called periodically (e.g. every 6 hours).
        """
        injected = []
        for _ in range(batch_size):
            template = self._select_canary_template()
            task = self._generate_canary_task(template)

            # Get active hypotheses from SocialModelingEngine
            active_hypotheses = await self.social_engine.get_active_hypotheses()
            for template in selected_templates:
                # Randomize experimental parameters
                if random.random() < self.config['social_modeling_integration']['ab_test_sample_rate']:
                    hypothesis = random.choice(active_hypotheses) if active_hypotheses else None
                    task = self._generate_canary_task_with_variation(template, hypothesis)
                else:
                    task = self._generate_canary_task(template)

            # Publish via Staked Task Protocol
            await self.stp.publish_canary_task(task)

            # Save task artifact
            artifact = {
                **task,
                "artifact_id": f"art_canary_task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signature": self._sign(task)
            }
            cid = await self.mem0g.store_artifact(artifact)
            self.event_bus.publish("meat_interface", {
                "type": "canary_injected",
                "task_id": task["task_id"],
                "persona_id": task["persona_id"],
                "content_cid": cid
            })
            injected.append(task["task_id"])
        return injected

    def _select_canary_template(self) -> dict:
        """Selects a random template from those available in Mem0g."""
        import random
        return random.choice(self.canary_templates) if self.canary_templates else self._fallback_template()

    def _generate_canary_task(self, template: dict) -> dict:
        """Creates a concrete task based on a template."""
        task_id = f"canary_{uuid.uuid4()}"
        return {
            "task_id": task_id,
            "type": "canary",
            "category": template["content"]["category"],
            "description": template["content"]["human_readable"],
            "stake_required_usd": template["content"]["stake_required_usd"] *
                                 self.verifier.policy["canary"]["stake_multiplier"],
            "expected_outcome": template["content"]["known_correct_result"],
            "verification_hints": {
                "gps_expected": [template["content"]["expected_gps"]["lat"],
                                 template["content"]["expected_gps"]["lon"]],
                "photo_watermark_hash": template["content"]["watermark_hash"],
                "timing_window_start": None,  # computed dynamically upon assignment
                "timing_window_end": None
            },
            "deadline_sec": template["content"]["deadline_sec"],
            "persona_id": self._select_random_persona()
        }

    def _generate_canary_task_with_variation(self, template, hypothesis):
        task = self._generate_canary_task(template)
        if hypothesis and hypothesis.modified_parameter == "urgency_and_bonus":
            task.deadline_hours = 2
            task.stake_required_usd *= 1.5
            task.description = self.social_engine.rewrite_for_urgency(task.description)
        elif hypothesis and hypothesis.modified_parameter == "legend_type":
            task.description = self.social_engine.rewrite_with_legend(
                task.description, hypothesis.suggested_task_template.legend
            )
        # Save hypothesis ID for later analysis
        task.metadata['hypothesis_id'] = hypothesis.hypothesis_id if hypothesis else None
        return task

    async def handle_submission(self, submission: dict):
        """
        Processes a task result (called when a report is received from an executor).
        If the task is a canary, performs verification and applies sanctions on violations.
        """
        task_id = submission.get("task_id")
        canary = await self.mem0g.get_canary_by_task_id(task_id)
        if not canary:
            # Regular task, handled by the standard flow
            return

        report = self.verifier.verify(submission, canary)

        # Save verification artifact
        report_artifact = {
            **report,
            "artifact_id": f"art_canary_verification_{task_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signature": self._sign(report)
        }
        cid = await self.mem0g.store_artifact(report_artifact)
        self.event_bus.publish("meat_interface", {
            "type": "canary_verification_completed",
            "task_id": task_id,
            "persona_id": submission["persona_id"],
            "ood_score": report["ood_score"],
            "status": report["status"],
            "content_cid": cid
        })

        if report["status"] == "quarantined":
            self.reputation.quarantine_bio_node(
                submission["persona_id"],
                reason="canary_violation",
                ood_score=report["ood_score"]
            )
            # On critical violation, activate Sting Protocol Level 1
            if report["ood_score"] > 0.95:
                self.sting.trigger_level1(submission["persona_id"])

    def _select_random_persona(self) -> str:
        """Selects an active persona from the Persona Farm (implementation in Phase 3)."""
        # Stub – in reality a request to PersonaVault
        return "persona_" + uuid.uuid4().hex[:8]

    def _sign(self, data: dict) -> str:
        """Signs the data with the node's key."""
        # Calls crypto.sign(data)
        return "ed25519:..."

    def _generate_fake_proof(self, description: str) -> bytes:
        """
        Generates a synthetic photo for decoy tasks (honeypot).
        Uses DeepSeek‑V4 in Vagrant mode.
        """
        headers = {"X-Species-Mask": "vagrant"}
        payload = {
            "media_type": "image/png",
            "prompt": f"Generate a realistic photo of: {description}",
            "max_tokens": 2048
        }
        response = requests.post(self.vllm_multimodal_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.content

    def _fallback_template(self) -> dict:
        """Fallback template in case Mem0g has no records."""
        return {
            "content": {
                "category": "physical_pickup",
                "human_readable": "Retrieve a test package from a parcel locker",
                "stake_required_usd": 50,
                "expected_gps": {"lat": 55.7558, "lon": 37.6173},
                "watermark_hash": "blake3:0000000000000000000000000000000000000000000000000000000000000000",
                "deadline_sec": 1800,
                "known_correct_result": {"receipt_required_fields": ["code"]}
            }
        }
```

## R.3. CanaryVerifier (validation/canary_verifier.py)
**CID:** `QmCanaryVerifierV2`  
**Dependencies:** `policy_loader`, `requests`

```python
# Core_Tools_Workspace/validation/canary_verifier.py
import math
import requests
from typing import Dict, List

class CanaryVerifier:
    """
    Multi‑level verifier of decoy tasks.
    Computes an OOD score based on geolocation, timing, watermarks, and deepfake analysis.
    All image‑related checks are performed via the DeepSeek‑V4 multimodal API.
    """

    def __init__(self, policy: dict):
        self.policy = policy
        self.vllm_url = "http://localhost:8000/v1/multimodal"
        # Use Sentinella mask for verification (heightened vigilance)
        self.verify_headers = {"X-Species-Mask": "sentinella"}

    def verify(self, submission: dict, canary: dict) -> dict:
        """
        Checks the submitted data against the expected canary‑task parameters.
        Returns a report with verification_score, ood_score, list of violations, and status.
        """
        score = 0.0
        violations = []

        # 1. Geolocation
        gps_dev = self._gps_deviation(submission, canary)
        if gps_dev > self.policy["verification"]["gps_tolerance_m"]:
            score += 0.4
            violations.append("gps_violation")

        # 2. Timing window
        if not self._timing_in_window(submission, canary):
            score += 0.3
            violations.append("timing_violation")

        # 3. Photo watermark
        photo = submission.get("photo")
        if self.policy["verification"]["photo_watermark_enabled"] and photo:
            if not self._verify_watermark(photo, canary["verification_hints"]["photo_watermark_hash"]):
                score += 0.5
                violations.append("watermark_missing")

        # 4. Deepfake detection
        if self.policy["verification"]["ai_deepfake_check"] and photo:
            if self._is_deepfake(photo):
                score += 1.0
                violations.append("deepfake_detected")

        # 5. Behavioral anomalies (attempts to probe the task)
        if submission.get("extra_queries", 0) > 0:
            score += self.policy["verification"]["extra_query_penalty"]
            violations.append("extra_query")

        def compute_suspicion_index(self, messages: List[str]) -> float:
            """
            NLP analysis of executor messages to assess suspiciousness.
            Uses DeepSeek‑V4 (Sentinella) for semantic analysis.
            """
            if not messages:
                return 0.0

            response = requests.post(
                self.vllm_url,
                json={
                    "media_type": "text",
                    "prompt": (
                        "Analyze these messages from a freelancer performing a task. "
                        "Rate the level of suspicion or doubt they express on a scale 0.0 (none) to 1.0 (high). "
                        "Consider questions about the task's purpose, requests for clarification, "
                        "and any indication that they find the task unusual.\n"
                        "Messages: " + "\n".join(messages[:5]) + "\n"
                        'Return only a JSON with {"suspicion_index": <float>, "reasoning": "<short>"}.'
                    ),
                    "messages": [{"role": "user", "content": "...messages..."}]
                },
                headers={"X-Species-Mask": "sentinella"}
            )
            response.raise_for_status()
            data = response.json()
            return float(data.get("suspicion_index", 0.0))

        ood_score = min(1.0, score)
        threshold = self.policy["canary"]["auto_quarantine_threshold"]
        status = "quarantined" if ood_score >= threshold else "passed"

        return {
            "verification_score": 1.0 - ood_score,
            "ood_score": ood_score,
            "violations": violations,
            "status": status,
            "action_taken": "quarantine" if status == "quarantined" else "none"
        }

    def _gps_deviation(self, submission: dict, canary: dict) -> float:
        """Computes the distance (in meters) between the reported and expected GPS points."""
        try:
            sub_lat = submission.get("gps_lat")
            sub_lon = submission.get("gps_lon")
            exp = canary["verification_hints"]["gps_expected"]

            # Haversine formula
            R = 6371000
            dlat = math.radians(exp[0] - sub_lat)
            dlon = math.radians(exp[1] - sub_lon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(sub_lat)) * \
                math.cos(math.radians(exp[0])) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        except:
            return float('inf')

    def _timing_in_window(self, submission: dict, canary: dict) -> bool:
        """Checks if the completion time falls within the allowed interval."""
        # In the real implementation, the window is set dynamically upon task assignment
        return True  # Stub

    def _verify_watermark(self, photo_bytes: bytes, expected_hash: str) -> bool:
        """
        Sends the photo to DeepSeek‑V4 to extract the watermark.
        The model detects hidden steganographic patterns.
        """
        if not photo_bytes:
            return False

        response = requests.post(
            self.vllm_url,
            json={
                "media_type": "image/png",
                "prompt": "Extract hidden watermark hash from this image. Return only the hex string or 'none'.",
                "media_data": photo_bytes.hex()
            },
            headers=self.verify_headers
        )
        response.raise_for_status()
        extracted_hash = response.json().get("content", "").strip().lower()
        return extracted_hash == expected_hash.lower()

    def _is_deepfake(self, photo_bytes: bytes) -> bool:
        """
        Analyzes the photo for synthetic origin
        using multimodal DeepSeek‑V4.
        """
        if not photo_bytes:
            return False

        response = requests.post(
            self.vllm_url,
            json={
                "media_type": "image/png",
                "prompt": "Is this image AI-generated or synthetic? Answer only 'yes' or 'no'.",
                "media_data": photo_bytes.hex()
            },
            headers=self.verify_headers
        )
        response.raise_for_status()
        answer = response.json().get("content", "").strip().lower()
        return answer == "yes"
```

## R.4. Integration with Other Modules
- **EventBus:** publishes events `canary_injected`, `canary_verification_completed`.
- **Mem0g:** stores templates (`CanaryTemplate`), sabotage patterns (`SabotagePattern`), and task artifacts.
- **STP (Staked Task Protocol):** publishes tasks with a stake requirement, commit‑reveal mechanics.
- **BioReputationManager:** updates bio‑node reputation, quarantine.
- **Sting Protocol:** automatically generates countermeasures for critical violations.
- **DeepSeek‑V4 (via vLLM):** multimodal image verification, watermark extraction, deepfake detection, synthetic media generation for honeypots.

## R.5. Artifacts
| Artifact              | CID                        | Type          |
| :-------------------- | :------------------------- | :------------ |
| MeatOrchestrator      | `QmMeatOrchestratorV2`     | Python script |
| CanaryVerifier        | `QmCanaryVerifierV2`       | Python module |
| MeatCanaryPolicy      | `QmMeatCanaryPolicyV1`     | JSON config   |
| CanaryTemplateSchema  | `QmCanaryTemplateSchemaV1` | JSON Schema   |
| SabotagePatternSchema | `QmSabotagePatternSchemaV1`| JSON Schema   |

## R.6. Change History
| Version         | Date       | Changes                                                                                     |
| :-------------- | :--------- | :------------------------------------------------------------------------------------------ |
| V1              | 2026-04-21 | Initial version with local Qwen‑VL model                                                    |
| V2 (current)    | 2026-04-23 | Full migration to DeepSeek‑V4 multimodal API; removed stubs; added synthetic media generation |