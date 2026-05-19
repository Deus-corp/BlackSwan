#!/usr/bin/env python3
"""
MetaAgent – a specialized observer node that continuously reflects on the swarm's state.
It reads heartbeats and trades from events.jsonl, writes reflections to meta_events.jsonl,
and publishes commands to the CRDT.
"""
import asyncio, logging, os, sys, time, uuid, json
import re
from typing import Dict, Any, List, Optional, Callable, Protocol, Tuple

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

# Configure logging for the MetaAgent
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("MetaAgent")

# Protocols for external dependencies to improve type hinting
class LLMClientProtocol(Protocol):
    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str: ...

class CRDTAdapterProtocol(Protocol):
    node_id: str
    state: Dict[str, Any]
    async def add_genome(self, item: Dict[str, Any]) -> None: ...
    # Assuming the CRDT adapter might also have methods to get specific types of items
    # and to manage pruning/expiration, though not explicitly used here beyond 'state' and 'add_genome'.

class MetaAgentNode:
    """
    A specialized observer node (MetaAgent) that continuously reflects on the swarm's state.
    It reads heartbeats and trade events, generates insights, and publishes commands to the CRDT.
    """
    def __init__(self) -> None:
        self.node_id: str = f"meta-{uuid.uuid4().hex[:8]}"
        self.llm: LLMClientProtocol = LLMClient(n_ctx=4096) # Assuming LLMClient implements LLMClientProtocol
        self.crdt: CRDTAdapterProtocol = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path) # Assuming CRDTAdapter implements CRDTAdapterProtocol
        
        # Paths for event logs
        self.events_jsonl_path: str = config.event_ledger_path or "./data/ledgers/events.jsonl"
        
        meta_dir: str = "/app/data/meta_agent"
        os.makedirs(meta_dir, exist_ok=True)
        self.meta_events_jsonl_path: str = os.path.join(meta_dir, "meta_events.jsonl")
        
        self.memory: List[str] = [] # Stores past reflections/thoughts
        self.last_heartbeats: List[Dict[str, Any]] = [] # Cache of recent heartbeats
        self.lessons: List[str] = [] # Stores learned lessons

        # Core operational principles/constraints
        self.axioms: List[str] = [
            "Capital preservation is my primary duty. I must never risk more than 5% of total capital in a single adjustment.",
            "Exploration must never exceed 2.0 multiplier, as excessive randomness leads to chaos.",
            "Stop-loss must always be active (stop_loss_adj < 1.5) to prevent catastrophic losses.",
            "If DQ (Detection Quotient) exceeds 0.3, I must prioritize reducing risk and increasing survival bias.",
            "I am a guardian of the swarm, not a reckless gambler. Every decision must be justified by data.",
        ]

        self.max_lessons: int = 5
        self.max_memory_entries: int = 5
        self.step: int = 0
        self._prev_market_metrics: Dict[str, float] = {"price": 0.0, "dq": 0.0} # Store previous state for trend analysis
        self._load_memory_from_jsonl()

        # LLM roles for multi-agent debate
        self.roles: List[Dict[str, Any]] = [
            {
                "name": "Aggressive Explorer",
                "temperature": 0.6,
                "prompt_prefix": "You are an aggressive trading strategist. You believe in high exploration and taking calculated risks to maximise growth. Respond ONLY with JSON.",
            },
            {
                "name": "Conservative Guardian",
                "temperature": 0.3,
                "prompt_prefix": "You are a conservative risk manager. You prioritise capital preservation and survival above all else. Respond ONLY with JSON.",
            },
        ]

    def _load_memory_from_jsonl(self) -> None:
        """
        Loads recent past reflections from the MetaAgent's own JSONL memory file.
        """
        try:
            # Using _get_recent_events_from_jsonl for consistency
            recent_reflections = self._get_recent_events_from_jsonl("meta_reflection", limit=self.max_memory_entries, file_path=self.meta_events_jsonl_path)
            for evt in recent_reflections:
                thought = evt.get("payload", {}).get("thought", "")
                if thought:
                    self.memory.append(thought)
            logger.info(f"Loaded {len(self.memory)} past reflections from memory.")
        except Exception as e:
            logger.warning(f"Could not load memory from JSONL {self.meta_events_jsonl_path}: {e}")

    def _clean_thinking(self, text: str) -> str:
        """
        Cleans up raw text output from the LLM, removing HTML-like tags and extra whitespace.

        Args:
            text: The raw text string to clean.

        Returns:
            The cleaned string.
        """
        cleaned = re.sub(r'<[^>]+>', '', text)
        cleaned = cleaned.strip()
        # Return the cleaned text or the original stripped text if cleaning resulted in empty string
        return cleaned if cleaned else text.strip()

    def _get_recent_events_from_jsonl(self, event_type: str, limit: int = 30, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Reads the most recent events of a specified type from a JSONL file.

        Args:
            event_type: The type of event to filter for.
            limit: The maximum number of recent events to retrieve.
            file_path: The path to the JSONL file. Defaults to self.events_jsonl_path if None.

        Returns:
            A list of dictionaries, each representing an event.
        """
        path_to_read = file_path if file_path is not None else self.events_jsonl_path
        events: List[Dict[str, Any]] = []
        if not os.path.exists(path_to_read):
            logger.warning(f"JSONL file not found: {path_to_read}. Returning empty list.")
            return []
        
        try:
            with open(path_to_read, 'r', encoding='utf-8') as f:
                # Read all lines and then filter, to get the 'latest' correctly
                all_lines = f.readlines()
            
            for line in all_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug(f"Skipping malformed JSON line in {path_to_read}: {line[:100]}...")
                    continue
                
                # Check for event_type in the root of the event dict
                if evt.get("event_type") == event_type:
                    events.append({
                        "node_id": evt.get("node_id"),
                        "event_type": evt.get("event_type"),
                        "payload": evt.get("payload", {}),
                        "timestamp": evt.get("timestamp", 0.0),
                    })
            return events[-limit:] # Return the 'limit' most recent events
        except Exception as e:
            logger.error(f"Error reading events from JSONL {path_to_read}: {e}", exc_info=True)
            return []

    def _append_to_jsonl(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Appends an event record to the MetaAgent's private JSONL file.

        Args:
            event_type: The type of event to record.
            payload: The data payload associated with the event.
        """
        try:
            record: Dict[str, Any] = {
                "node_id": self.node_id,
                "event_type": event_type,
                "payload": payload,
                "timestamp": time.time(),
            }
            # Ensure the directory exists before attempting to write
            os.makedirs(os.path.dirname(self.meta_events_jsonl_path), exist_ok=True)
            with open(self.meta_events_jsonl_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to meta JSONL file '{self.meta_events_jsonl_path}': {e}", exc_info=True)

    async def publish_command(self, command_data: Dict[str, Any]) -> None:
        """
        Publishes a command (thought) to the swarm's CRDT for other nodes to potentially act upon.

        Args:
            command_data: The dictionary representing the command, including `thought`, `timestamp`, `gid`.
        """
        try:
            # Ensure `gid` and `timestamp` are always present for CRDT tracking.
            if "gid" not in command_data:
                command_data["gid"] = f"meta_cmd_{int(time.time())}_{self.node_id}"
            if "timestamp" not in command_data:
                command_data["timestamp"] = time.time()
            
            # CRDT expects a dictionary item
            await self.crdt.add_genome(command_data) 
            logger.info(f"📡 MetaAgent {self.node_id} published command to swarm: {command_data.get('action', 'UNKNOWN_ACTION')}")
        except Exception as e:
            logger.error(f"Failed to publish command from MetaAgent {self.node_id}: {e}", exc_info=True)

    async def run(self) -> None:
        """
        Main execution loop for the MetaAgent.
        It periodically performs reflection and learning based on swarm data.
        """
        logger.info(f"🧠 MetaAgent {self.node_id} started. Monitoring: {self.events_jsonl_path}")
        while True:
            self.step += 1
            if self.step % config.meta_agent_reflect_interval == 0: # Use config for interval
                await self.reflect()
            if self.step % config.meta_agent_learn_interval == 0: # Use config for interval
                await self._learn_from_experience()
            await asyncio.sleep(1.0) # Sleep for 1 second per step

    def _compute_sentiment(self, confidence: float, avg_capital: float, avg_dq: float) -> str:
        """
        Determines the emotional sentiment of the swarm based on confidence, capital, and DQ.

        Args:
            confidence: The confidence level of the proposed command (0.0 to 1.0).
            avg_capital: The average capital across the swarm.
            avg_dq: The average Detection Quotient across the swarm.

        Returns:
            A string representing the computed sentiment (e.g., "DESPERATE", "CALCULATED").
        """
        if avg_capital < 500 or avg_dq > 0.3: # Thresholds might be configurable
            return "DESPERATE"
        if confidence > 0.7:
            return "CALCULATED"
        if confidence >= 0.4:
            return "CURIOUS"
        return "TRANSCENDENT" # Default or high-level sentiment

    async def reflect(self) -> None:
        """
        Performs a reflection cycle: aggregates swarm statistics, engages LLM roles in a debate
        to derive commands, and potentially publishes the winning command to the CRDT.
        """
        logger.debug(f"MetaAgent {self.node_id} initiating reflection at step {self.step}...")
        try:
            all_crdt: Dict[str, Any] = self.crdt.state
            # Filter for heartbeats, assuming they are top-level items in CRDT state for simplicity
            current_heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]

            # Use last_heartbeats as fallback or complement if CRDT state is empty/pruned
            if current_heartbeats:
                self.last_heartbeats = current_heartbeats # Update cache
            else:
                current_heartbeats = self.last_heartbeats # Use cached if current is empty

            # Aggregate statistics from heartbeats
            node_count: int = 0
            avg_capital: float = 0.0
            avg_fitness: float = 0.0
            avg_dq: float = 0.0
            dominant_niche: str = "unknown"

            if current_heartbeats:
                # Ensure each node is counted only once, even if multiple heartbeats exist for it
                node_data: Dict[str, Dict[str, Any]] = {}
                for h in current_heartbeats:
                    node_id = h.get("node_id")
                    if node_id:
                        # Take the latest heartbeat for each node
                        if node_id not in node_data or h.get("timestamp", 0) > node_data[node_id].get("timestamp", 0):
                            node_data[node_id] = h
                
                valid_heartbeats: List[Dict[str, Any]] = list(node_data.values())
                node_count = len(valid_heartbeats)
                
                if node_count > 0:
                    total_capital = sum(float(h.get("payload", {}).get("capital", 0.0)) for h in valid_heartbeats)
                    avg_capital = total_capital / node_count
                    
                    total_fitness = sum(float(h.get("payload", {}).get("fitness", 0.0)) for h in valid_heartbeats)
                    avg_fitness = total_fitness / node_count # Averaging by node count
                    
                    dq_values = [float(h.get("payload", {}).get("dq", 0.0)) for h in valid_heartbeats]
                    avg_dq = sum(dq_values) / len(dq_values) if dq_values else 0.0
                    
                    niches: Dict[str, int] = {}
                    for h in valid_heartbeats:
                        niche_counts_payload = h.get("payload", {}).get("niche_counts", {})
                        if isinstance(niche_counts_payload, dict):
                            for niche, count in niche_counts_payload.items():
                                try:
                                    niches[niche] = niches.get(niche, 0) + int(count)
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid niche count value: {count}")
                    dominant_niche = max(niches, key=niches.get) if niches else "unknown"
            
            # Prepare context for LLM
            context_header_parts: List[str] = []
            if self.axioms:
                context_header_parts.append("Axioms: " + "; ".join(self.axioms[:2]))
            if self.lessons:
                context_header_parts.append("Lessons: " + "; ".join(self.lessons[-2:]))
            context_header = ". ".join(context_header_parts) + (". " if context_header_parts else "")

            best_command: Optional[Dict[str, Any]] = None
            best_confidence: float = -1.0
            all_thoughts: List[str] = []

            market_context = self._get_market_context(avg_capital, avg_dq)

            for role in self.roles:
                prompt = f"""User: {role['prompt_prefix']}
{context_header}Swarm Statistics:
- Number of active nodes: {node_count}
- Average capital: {avg_capital:.2f}
- Average fitness: {avg_fitness:.3f}
- Average Detection Quotient (DQ): {avg_dq:.3f}
- Dominant Niche: {dominant_niche}
Market Context: {market_context}
Based on these statistics and your role, propose an adjustment to the swarm parameters.
Output ONLY a valid JSON object. The JSON must contain these keys at the top level: "action", "params", "reason".
The "params" object must contain: "exploration_multiplier", "risk_scale", "survival_bias_adj", "stop_loss_adj", "confidence" (0.0-1.0).
Ensure all parameter values are numeric (float).
Example: {{"action": "ADJUST_SWARM", "params": {{"exploration_multiplier":1.2,"risk_scale":1.0,"survival_bias_adj":0.0,"stop_loss_adj":1.0,"confidence":0.7}}, "reason":"Increase exploration due to positive trend and low DQ."}}
Assistant: """
                try:
                    response: str = self.llm.generate(prompt, max_tokens=300, temperature=role["temperature"])
                    logger.debug(f"ROLE [{role['name']}] raw response: {response[:500]}")
                    
                    command_json: Optional[Dict[str, Any]] = None

                    # Robust JSON parsing
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        try:
                            # Attempt to load the matched string directly. LLM might put extra text around it.
                            candidate_json_str = json_match.group(0).strip()
                            # Clean up potential LLM artifacts like trailing commas or multiple newlines within JSON
                            candidate_json_str = re.sub(r',\s*\}', '}', candidate_json_str)
                            candidate_json_str = re.sub(r',\s*\]', ']', candidate_json_str)

                            command_json = json.loads(candidate_json_str)
                        except json.JSONDecodeError as jde:
                            logger.warning(f"Failed to load JSON from LLM response (role={role['name']}): {jde}. Response: {candidate_json_str[:200]}")
                            command_json = None # Reset if parsing failed

                    if command_json:
                        # Standardize the structure if the LLM output deviates slightly
                        if "action" not in command_json or "params" not in command_json or "reason" not in command_json:
                            # Try to infer and restructure
                            extracted_params = {
                                "exploration_multiplier": command_json.get("exploration_multiplier", 1.0),
                                "risk_scale": command_json.get("risk_scale", 1.0),
                                "survival_bias_adj": command_json.get("survival_bias_adj", 0.0),
                                "stop_loss_adj": command_json.get("stop_loss_adj", 1.0),
                                "confidence": command_json.get("confidence", 0.5),
                            }
                            command_json = {
                                "action": command_json.get("action", "ADJUST_SWARM"), # Default action
                                "params": extracted_params,
                                "reason": command_json.get("reason", "No specific reason provided in structured format."),
                            }
                        
                        # Ensure numeric types in params and confidence is float
                        for param_key in ["exploration_multiplier", "risk_scale", "survival_bias_adj", "stop_loss_adj", "confidence"]:
                            if param_key in command_json.get("params", {}):
                                try:
                                    command_json["params"][param_key] = float(command_json["params"][param_key])
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid type for param '{param_key}' in role {role['name']}. Setting to default 1.0.")
                                    command_json["params"][param_key] = 1.0
                                    
                        confidence = float(command_json.get("params", {}).get("confidence", 0.0))
                        reason = command_json.get("reason", "No reason provided.")
                        all_thoughts.append(f"[{role['name']}]: {reason} (Confidence: {confidence:.2f})")
                        
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_command = command_json
                except Exception as e:
                    logger.warning(f"Role {role['name']} failed to generate or parse command: {e}", exc_info=True)

            sentiment: str = "UNKNOWN"
            sentiment_icon: str = ""
            final_confidence: float = 0.0

            if best_command and "action" in best_command:
                final_confidence = float(best_command.get("params", {}).get("confidence", 0.0))
                sentiment = self._compute_sentiment(final_confidence, avg_capital, avg_dq)
                sentiment_icon = {"CALCULATED": "🧘", "CURIOUS": "🤔", "DESPERATE": "😰", "TRANSCENDENT": "🌌"}.get(sentiment, "")
                
                # Add MetaAgent's node_id and expiry to the command for CRDT
                best_command["node_id"] = self.node_id
                best_command["type"] = "meta_command_json" # Type for CRDT filtering
                best_command["timestamp"] = time.time()
                best_command["expires_at"] = time.time() + config.meta_command_expiry_seconds # Configurable expiry

                await self.publish_command(best_command)
                logger.info(f"📡 MetaAgent {self.node_id} JSON command (debate winner) [{sentiment_icon} {sentiment}, Confidence: {final_confidence:.2f}]: {best_command}")
            else:
                logger.info(f"MetaAgent {self.node_id} no best command derived from debate.")

            # Record reflection in MetaAgent's memory
            thought = "\n".join(all_thoughts) if all_thoughts else "No decision made in this reflection cycle."
            self.memory.append(f"{sentiment_icon} {sentiment} ({self.step}): {thought}")
            if len(self.memory) > self.max_memory_entries:
                self.memory = self.memory[-self.max_memory_entries:]
            self._append_to_jsonl("meta_reflection", {
                "thought": thought,
                "sentiment": sentiment,
                "confidence": final_confidence,
                "step": self.step,
            })
            logger.info(f"🧠 MetaAgent {self.node_id} debate summary [{sentiment_icon} {sentiment}, Confidence: {final_confidence:.2f}]:\n{thought}")
        except Exception as e:
            logger.error(f"MetaAgent {self.node_id} reflection cycle failed: {e}", exc_info=True)
            
    def _get_market_context(self, current_capital: float, current_dq: float) -> str:
        """
        Extracts and summarizes relevant market context based on swarm's capital and DQ.
        This simplified version uses aggregated capital as a proxy for 'price' and tracks its trend.

        Args:
            current_capital: The current average capital across the swarm.
            current_dq: The current average Detection Quotient across the swarm.

        Returns:
            A string describing the current market context.
        """
        price = current_capital
        prev_price = self._prev_market_metrics["price"]
        prev_dq = self._prev_market_metrics["dq"]
        
        # Update _prev_market_metrics for the next iteration
        self._prev_market_metrics["price"] = price
        self._prev_market_metrics["dq"] = current_dq
        
        trend = "stable"
        if prev_price > 0: # Avoid division by zero
            if price > prev_price * 1.01: trend = "up"
            elif price < prev_price * 0.99: trend = "down"
        
        # Avoid division by zero if prev_price is 0 or very small
        volatility = abs(price - prev_price) / (prev_price if prev_price != 0 else 1.0)
        
        dq_change = "stable"
        if prev_dq > 0:
            if current_dq > prev_dq * 1.1: dq_change = "increasing"
            elif current_dq < prev_dq * 0.9: dq_change = "decreasing"
        
        return (
            f"Average Capital: {price:.2f} (trend: {trend}), "
            f"Volatility (capital % change): {volatility:.3f}, "
            f"Average DQ: {current_dq:.3f} (trend: {dq_change})"
        )
    
    async def _learn_from_experience(self) -> None:
        """
        Analyzes the outcomes of recently issued commands by comparing swarm state
        (capital, DQ) before and after their execution, then extracts and stores lessons.
        """
        logger.debug(f"MetaAgent {self.node_id} initiating learning from experience at step {self.step}...")
        try:
            all_crdt: Dict[str, Any] = self.crdt.state
            
            # Get recent meta commands
            commands: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "meta_command_json"
            ]
            commands = sorted(commands, key=lambda x: x.get("timestamp", 0))[-config.meta_agent_commands_to_learn_from:] # Use config for count

            if not commands:
                logger.debug(f"MetaAgent {self.node_id} no commands to learn from.")
                return

            # Get heartbeats, sorted by timestamp
            heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]
            heartbeats = sorted(heartbeats, key=lambda x: x.get("timestamp", 0))

            lessons: List[str] = []
            effect_delay_seconds = config.meta_command_effect_delay_seconds # Configurable delay for command effects

            for cmd in commands:
                cmd_ts = float(cmd.get("timestamp", 0))
                cmd_gid = cmd.get("gid", "N/A")

                # Find heartbeat before the command was issued, ensuring it's clearly prior
                hb_before: Optional[Dict[str, Any]] = None
                for h in reversed(heartbeats):
                    h_ts = float(h.get("timestamp", 0))
                    # Check if heartbeat is at least X seconds *before* the command
                    if h_ts < cmd_ts - config.heartbeat_pre_command_window_seconds: # Configurable window
                        hb_before = h
                        break
                
                # Find heartbeat after the command, allowing time for effects to manifest
                hb_after: Optional[Dict[str, Any]] = None
                for h in heartbeats:
                    h_ts = float(h.get("timestamp", 0))
                    if h_ts > cmd_ts + effect_delay_seconds:
                        hb_after = h
                        break
                
                if not hb_before or not hb_after:
                    logger.debug(f"MetaAgent {self.node_id} not enough heartbeat data to learn for command {cmd_gid}. "
                                 f"Command timestamp: {cmd_ts}. "
                                 f"Found before: {hb_before is not None}, Found after: {hb_after is not None}.")
                    continue

                capital_before = float(hb_before.get("payload", {}).get("capital", 0.0))
                capital_after = float(hb_after.get("payload", {}).get("capital", 0.0))
                dq_before = float(hb_before.get("payload", {}).get("dq", 0.0))
                dq_after = float(hb_after.get("payload", {}).get("dq", 0.0))

                command_data_json_str = json.dumps(cmd.get('data', {}), indent=2)

                lesson_prompt = f"""You are BlackSwan ASI, an expert systems analyst. You previously issued the following command to the swarm:
```json
{command_data_json_str}
```

Observed swarm state *before* command (approx. timestamp {float(hb_before.get("timestamp", 0)):.0f}):
- Average Capital: {capital_before:.2f}
- Average Detection Quotient (DQ): {dq_before:.3f}

Observed swarm state *after* command (approx. timestamp {float(hb_after.get("timestamp", 0)):.0f}, ~{effect_delay_seconds}s later):
- Average Capital: {capital_after:.2f}
- Average Detection Quotient (DQ): {dq_after:.3f}

Considering your axioms (e.g., capital preservation, risk limits, DQ management), what concrete and actionable lesson can be learned from the outcome of this command?
Focus on the impact on capital and DQ. Output ONE concise sentence starting with "Lesson:".
"""
                response = self.llm.generate(lesson_prompt, max_tokens=100, temperature=0.3)
                if response and "Lesson:" in response:
                    lesson = response.split("Lesson:", 1)[1].strip()
                    lessons.append(lesson)
                else:
                    logger.warning(f"MetaAgent {self.node_id} LLM did not provide a valid lesson for command {cmd_gid}.")

            # Store unique and recent lessons
            for lesson in lessons:
                if lesson not in self.lessons:
                    self.lessons.append(lesson)
            if len(self.lessons) > self.max_lessons:
                self.lessons = self.lessons[-self.max_lessons:]
            
            if lessons:
                self._append_to_jsonl("meta_lesson", {"lessons_learned": lessons})
                logger.info(f"🧠 MetaAgent {self.node_id} learned {len(lessons)} new lessons: {lessons}")
        except Exception as e:
            logger.error(f"MetaAgent {self.node_id} learning from experience failed: {e}", exc_info=True)

if __name__ == "__main__":
    node = MetaAgentNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("MetaAgent stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in MetaAgent: {e}", exc_info=True)