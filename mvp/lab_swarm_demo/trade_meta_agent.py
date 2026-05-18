#!/usr/bin/env python3
"""
MetaAgent – a specialized observer node that continuously reflects on the swarm's state.
It reads heartbeats and trades from events.jsonl, writes reflections to meta_events.jsonl,
and publishes commands to the CRDT.
"""
import asyncio, logging, os, sys, time, uuid, json
import re
from typing import Dict, Any, List, Optional, Callable

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("MetaAgent")


class MetaAgentNode:
    """
    A specialized observer node (MetaAgent) that continuously reflects on the swarm's state.
    It reads heartbeats and trade events, generates insights, and publishes commands to the CRDT.
    """
    def __init__(self) -> None:
        self.node_id: str = f"meta-{uuid.uuid4().hex[:8]}"
        self.llm: LLMClient = LLMClient(n_ctx=4096)
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        
        self.events_jsonl_path: str = config.event_ledger_path or "./data/ledgers/events.jsonl"
        
        meta_dir: str = "/app/data/meta_agent"
        os.makedirs(meta_dir, exist_ok=True)
        self.meta_events_jsonl_path: str = os.path.join(meta_dir, "meta_events.jsonl")
        
        self.memory: List[str] = []
        self.last_heartbeats: List[Dict[str, Any]] = []
        self.lessons: List[str] = []

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
        self._prev_price: float = 0.0
        self._load_memory_from_jsonl()

        self.roles: List[Dict[str, Any]] = [
            {
                "name": "Aggressive Explorer",
                "temperature": 0.6,
                "prompt_prefix": "You are an aggressive trading strategist. You believe in high exploration and taking calculated risks to maximise growth.",
            },
            {
                "name": "Conservative Guardian",
                "temperature": 0.3,
                "prompt_prefix": "You are a conservative risk manager. You prioritise capital preservation and survival above all else.",
            },
        ]

    def _load_memory_from_jsonl(self) -> None:
        """
        Loads recent past reflections from the MetaAgent's own JSONL memory file.
        """
        try:
            recent = self._get_recent_events_from_jsonl("meta_reflection", limit=self.max_memory_entries, file_path=self.meta_events_jsonl_path)
            for evt in recent:
                thought = evt.get("payload", {}).get("thought", "")
                if thought:
                    self.memory.append(thought)
            logger.info(f"Loaded {len(self.memory)} past reflections from memory")
        except Exception as e:
            logger.warning(f"Could not load memory from JSONL: {e}")

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
        try:
            if not os.path.exists(path_to_read):
                logger.warning(f"JSONL file not found: {path_to_read}")
                return []
            events: List[Dict[str, Any]] = []
            with open(path_to_read, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping malformed JSON line in {path_to_read}: {line}")
                        continue
                    if evt.get("event_type") == event_type:
                        events.append({
                            "node_id": evt.get("node_id"),
                            "event_type": evt.get("event_type"),
                            "payload": evt.get("payload", {}),
                            "timestamp": evt.get("timestamp", ""),
                        })
            return events[-limit:]
        except Exception as e:
            logger.warning(f"Cannot read events from JSONL {path_to_read}: {e}")
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
            with open(self.meta_events_jsonl_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to meta JSONL: {e}")

    async def publish_command(self, thought: str) -> None:
        """
        Publishes a command (thought) to the swarm's CRDT for other nodes to potentially act upon.
        This method is marked async but currently performs a synchronous CRDT operation.
        It's kept async for consistency and potential future async CRDT implementations.

        Args:
            thought: The reflective thought or command to publish.
        """
        try:
            command: Dict[str, Any] = {
                "thought": thought,
                "timestamp": time.time(),
                "gid": f"meta_cmd_{int(time.time())}",
            }
            # Assuming CRDTAdapter's add_genome is awaitable or doesn't need await if it's sync.
            # If add_genome is indeed sync, `await` here won't hurt but might be redundant.
            await self.crdt.add_genome(command) 
            logger.info("📡 MetaAgent published command to swarm")
        except Exception as e:
            logger.error(f"Failed to publish command: {e}")

    async def run(self) -> None:
        """
        Main execution loop for the MetaAgent.
        It periodically performs reflection and learning based on swarm data.
        """
        logger.info(f"🧠 MetaAgent {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 100 == 0:
                await self.reflect()
            if self.step % 1000 == 0:
                await self._learn_from_experience()
            await asyncio.sleep(1.0)

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
        if avg_capital < 500 or avg_dq > 0.3:
            return "DESPERATE"
        if confidence > 0.7:
            return "CALCULATED"
        if confidence >= 0.4:
            return "CURIOUS"
        return "TRANSCENDENT"

    async def reflect(self) -> None:
        """
        Performs a reflection cycle: aggregates swarm statistics, engages LLM roles in a debate
        to derive commands, and potentially publishes the winning command to the CRDT.
        """
        try:
            # Read heartbeats from CRDT
            all_crdt: Dict[str, Any] = self.crdt.state
            heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]
            if heartbeats:
                # Store a copy of current heartbeats, so even if CRDT prunes, we have recent data.
                # However, for aggregation, always use the most recent available.
                self.last_heartbeats = heartbeats 
            else:
                # If no current heartbeats in CRDT, use previously stored ones.
                heartbeats = self.last_heartbeats

            # Aggregate statistics
            node_count: int = 0
            avg_capital: float = 0.0
            avg_fitness: float = 0.0
            avg_dq: float = 0.0
            dominant_niche: str = "unknown"

            if heartbeats:
                node_ids = set(h.get("node_id", "unknown") for h in heartbeats)
                node_count = len(node_ids)
                total_capital = sum(float(h.get("capital", 0.0)) for h in heartbeats)
                avg_capital = total_capital / node_count if node_count > 0 else 0.0
                
                total_fitness = sum(float(h.get("fitness", 0.0)) for h in heartbeats)
                avg_fitness = total_fitness / max(len(heartbeats), 1)
                
                dq_values = [float(h.get("dq", 0.0)) for h in heartbeats]
                avg_dq = sum(dq_values) / len(dq_values) if dq_values else 0.0
                
                niches: Dict[str, int] = {}
                for h in heartbeats:
                    # Niche counts could be nested under payload or directly in heartbeat
                    niche_counts_payload = h.get("payload", {}).get("niche_counts", {})
                    if not niche_counts_payload: # Fallback if niche_counts is top-level
                        niche_counts_payload = h.get("niche_counts", {})

                    if isinstance(niche_counts_payload, dict):
                        for niche, count in niche_counts_payload.items():
                            niches[niche] = niches.get(niche, 0) + int(count) # Ensure count is int
                dominant_niche = max(niches, key=niches.get) if niches else "unknown"

            # `trades` and `past` variables were unused in the original reflect method.
            # Keeping them here if they are intended for future use or debugging,
            # but noting their lack of immediate impact on the current reflection logic.
            trades = self._get_recent_events_from_jsonl("trade_executed", limit=30) 
            past = "\n".join(f"- {t}" for t in self.memory[-self.max_memory_entries:]) or "(no previous thoughts)"

            # Compact context from axioms and lessons
            context_header = ""
            if self.axioms:
                context_header += "Axioms: " + "; ".join(self.axioms[:2]) + ". "
            if self.lessons:
                context_header += "Lessons: " + "; ".join(self.lessons[-2:]) + ". "

            # ---- Multi-Agent Debate ----
            best_command: Optional[Dict[str, Any]] = None
            best_confidence: float = -1.0
            all_thoughts: List[str] = []

            market_context = self._get_market_context()

            for role in self.roles:
                role_prompt = f"""User: {role['prompt_prefix']}
{context_header}Swarm: {node_count} nodes, avg capital {avg_capital:.0f}, fitness {avg_fitness:.3f}, DQ {avg_dq:.3f}.
Market: {market_context}
Adjust parameters. Output ONLY a valid JSON object with these keys: exploration_multiplier, risk_scale, survival_bias_adj, stop_loss_adj, confidence, reason.
Example: {{"exploration_multiplier":1.2,"risk_scale":1.0,"survival_bias_adj":0.0,"stop_loss_adj":1.0,"confidence":0.7,"reason":"increase exploration"}}
Hints based on market:
- If trend is "up" and volatility is high, Aggressive Explorer should INCREASE exploration.
- If trend is "down" or DQ > 0.2, Conservative Guardian should REDUCE risk.
Assistant: {{"""
                try:
                    response: str = self.llm.generate(role_prompt, max_tokens=250, temperature=role["temperature"])
                    logger.info(f"ROLE [{role['name']}] raw response: {response[:300]}")
                    
                    command_json: Optional[Dict[str, Any]] = None

                    # Attempt 1: Regex to find the first JSON object
                    json_match = re.search(r'(\{.*?})', response, re.DOTALL)
                    if json_match:
                        try:
                            # Clean the matched JSON string (e.g., remove escaped quotes) before loading
                            candidate_json_str = json_match.group(1).replace('\\"', '"')
                            command_json = json.loads(candidate_json_str)
                        except json.JSONDecodeError:
                            logger.debug(f"Failed to load JSON from regex extracted string: {candidate_json_str[:100]}")
                    
                    # Attempt 2: If regex failed, try the original bracket-counting logic
                    if command_json is None:
                        start_brace = response.find('{')
                        if start_brace != -1:
                            depth = 0
                            end_brace = -1
                            for i in range(start_brace, len(response)):
                                if response[i] == '{':
                                    depth += 1
                                elif response[i] == '}':
                                    depth -= 1
                                    if depth == 0:
                                        end_brace = i
                                        break
                            if end_brace > start_brace:
                                candidate_str = response[start_brace : end_brace + 1]
                                try:
                                    command_json = json.loads(candidate_str)
                                except json.JSONDecodeError:
                                    logger.debug(f"Failed to load JSON from bracket-counted string: {candidate_str[:100]}")
                                    # One more attempt for a single missing closing brace, as in original code
                                    try:
                                        command_json = json.loads(candidate_str + "}") # Fix: ensure it's `candidate_str + "}"`
                                    except json.JSONDecodeError:
                                        pass
                    
                    # Attempt 3: If still no command_json, fallback to regex for individual values (as in original)
                    if command_json is None:
                        vals: Dict[str, float] = {}
                        for key in ["exploration_multiplier", "risk_scale", "survival_bias_adj", "stop_loss_adj", "confidence"]:
                            # Regex to find key: value pairs, handling optional quotes around values
                            match = re.search(rf'"{key}"\s*:\s*"?([\d.]+)"?', response)
                            if match:
                                try:
                                    vals[key] = float(match.group(1))
                                except ValueError:
                                    logger.debug(f"Could not convert '{match.group(1)}' to float for key '{key}'")

                        reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', response)
                        # If at least one parameter was successfully extracted AND confidence is present,
                        # or if reason is present (to ensure some meaningful output was parsed)
                        if "exploration_multiplier" in vals or "risk_scale" in vals or reason_match:
                            command_json = {
                                "action": "ADJUST_SWARM",
                                "params": {
                                    "exploration_multiplier": vals.get("exploration_multiplier", 1.0),
                                    "risk_scale": vals.get("risk_scale", 1.0),
                                    "survival_bias_adj": vals.get("survival_bias_adj", 0.0),
                                    "stop_loss_adj": vals.get("stop_loss_adj", 1.0),
                                    "confidence": vals.get("confidence", 0.5),
                                },
                                "reason": reason_match.group(1) if reason_match else "No specific reason provided.",
                            }

                    if command_json:
                        # This block ensures the command is in the expected {action: ..., params: {...}} format
                        if "action" not in command_json or "params" not in command_json:
                            params_data: Dict[str, Any] = {
                                "exploration_multiplier": command_json.get("exploration_multiplier", 1.0),
                                "risk_scale": command_json.get("risk_scale", 1.0),
                                "survival_bias_adj": command_json.get("survival_bias_adj", 0.0),
                                "stop_loss_adj": command_json.get("stop_loss_adj", 1.0),
                                "confidence": command_json.get("confidence", 0.5),
                            }
                            command_json = {
                                "action": "ADJUST_SWARM",
                                "params": params_data,
                                "reason": command_json.get("reason", "No specific reason provided."),
                            }
                        
                        confidence = float(command_json.get("params", {}).get("confidence", 0.5))
                        reason = command_json.get("reason", "No reason provided.")
                        all_thoughts.append(f"[{role['name']}]: {reason}")
                        
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_command = command_json
                except Exception as e:
                    logger.warning(f"Role {role['name']} failed to generate or parse command: {e}")

            sentiment: str = "UNKNOWN"
            sentiment_icon: str = ""
            confidence: float = 0.0

            if best_command and "action" in best_command:
                # Add a 'node_id' to the command for consistency in CRDT if needed
                best_command["node_id"] = self.node_id
                
                await self.crdt.add_genome({
                    "type": "meta_command_json",
                    "data": best_command,
                    "timestamp": time.time(),
                    "expires_at": time.time() + 300, # Commands expire after 5 minutes
                    "gid": f"meta_json_{int(time.time())}_{self.node_id}",
                })
                # Re-check confidence from best_command, as it might have been restructured
                confidence = float(best_command.get("params", {}).get("confidence", 0.5))
                sentiment = self._compute_sentiment(confidence, avg_capital, avg_dq)
                sentiment_icon = {"CALCULATED": "🧘", "CURIOUS": "🤔", "DESPERATE": "😰", "TRANSCENDENT": "🌌"}.get(sentiment, "")
                logger.info(f"📡 MetaAgent JSON command (debate winner) [{sentiment_icon} {sentiment}]: {best_command}")

            thought = "\n".join(all_thoughts) if all_thoughts else "No decision"
            self.memory.append(thought)
            if len(self.memory) > self.max_memory_entries:
                self.memory = self.memory[-self.max_memory_entries:]
            self._append_to_jsonl("meta_reflection", {
                "thought": thought,
                "sentiment": sentiment,
                "confidence": confidence,
            })
            logger.info(f"🧠 MetaAgent debate [{sentiment_icon} {sentiment}]:\n{thought}")
        except Exception as e:
            logger.error(f"MetaAgent reflection failed: {e}", exc_info=True)
            
    def _get_market_context(self) -> str:
        """
        Extracts and summarizes relevant market context from the latest heartbeats in the CRDT.

        Returns:
            A string describing the current market context based on swarm's capital and DQ.
        """
        try:
            all_crdt: Dict[str, Any] = self.crdt.state
            heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]
            if not heartbeats:
                return "Market data: N/A"
            # Sort heartbeats by timestamp to ensure we get the latest one
            latest_heartbeat = max(heartbeats, key=lambda h: h.get("timestamp", 0))
            
            capital = float(latest_heartbeat.get("capital", 0.0))
            dq = float(latest_heartbeat.get("dq", 0.0))
            
            price = capital  # simplification, can be replaced with real price later
            prev_price = self._prev_price
            
            # Update _prev_price for the next iteration
            self._prev_price = price
            
            trend = "up" if price >= prev_price else "down"
            # Avoid division by zero if prev_price is 0 or very small
            volatility = abs(price - prev_price) / (prev_price if prev_price != 0 else 1.0)
            
            return (
                f"Price: {price:.2f} (trend: {trend}), "
                f"Volatility: {volatility:.3f}, "
                f"DQ: {dq:.3f}"
            )
        except Exception as e:
            logger.warning(f"Error getting market context: {e}")
            return "Market data: N/A"
    
    async def _learn_from_experience(self) -> None:
        """
        Analyzes the outcomes of recently issued commands by comparing swarm state
        (capital, DQ) before and after their execution, then extracts and stores lessons.
        """
        try:
            all_crdt: Dict[str, Any] = self.crdt.state
            # Get last few JSON commands
            commands: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "meta_command_json"
            ]
            if len(commands) < 1: # Need at least one command to evaluate
                return
            commands = sorted(commands, key=lambda x: x.get("timestamp", 0))[-3:] # Take up to last 3

            # Heartbeats are crucial for state comparison
            heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]
            heartbeats = sorted(heartbeats, key=lambda x: x.get("timestamp", 0))

            lessons: List[str] = []
            for cmd in commands:
                ts = float(cmd.get("timestamp", 0))
                
                # Find heartbeat before the command was issued
                hb_before: Optional[Dict[str, Any]] = None
                for h in reversed(heartbeats):
                    h_ts = float(h.get("timestamp", 0))
                    # Heartbeats can be slightly out of order or arrive after command
                    if h_ts < ts - 1: # Allow a small buffer
                        hb_before = h
                        break
                
                # Find heartbeat after the command, allowing a delay for effects to manifest
                hb_after: Optional[Dict[str, Any]] = None
                # Consider a wider window or specific logic for 'after' to ensure effect is visible
                # e.g., command applied, nodes act, then new heartbeats reflect changes
                effect_delay_seconds = 60 
                for h in heartbeats:
                    h_ts = float(h.get("timestamp", 0))
                    if h_ts > ts + effect_delay_seconds:
                        hb_after = h
                        break
                
                if not hb_before or not hb_after:
                    logger.debug(f"Not enough heartbeat data to learn for command {cmd.get('gid', 'N/A')}. "
                                 f"Command timestamp: {ts}, Found before: {hb_before is not None}, Found after: {hb_after is not None}")
                    continue

                capital_before = float(hb_before.get("capital", 0.0))
                capital_after = float(hb_after.get("capital", 0.0))
                dq_before = float(hb_before.get("dq", 0.0))
                dq_after = float(hb_after.get("dq", 0.0))

                # Extract command data safely
                command_data_json = json.dumps(cmd.get('data', {}))

                lesson_prompt = f"""You are BlackSwan ASI. You issued the following command:
{command_data_json}

Before command: capital={capital_before:.2f}, DQ={dq_before:.3f}
After command (~{effect_delay_seconds}s): capital={capital_after:.2f}, DQ={dq_after:.3f}

What lesson can you learn from this outcome? Output ONE short sentence starting with "Lesson:"."""
                response = self.llm.generate(lesson_prompt, max_tokens=60, temperature=0.3)
                if response and "Lesson:" in response:
                    lesson = response.split("Lesson:", 1)[1].strip()
                    lessons.append(lesson)

            # Store lessons
            for lesson in lessons:
                if lesson not in self.lessons:
                    self.lessons.append(lesson)
            if len(self.lessons) > self.max_lessons:
                self.lessons = self.lessons[-self.max_lessons:]
            if lessons:
                logger.info(f"🧠 MetaAgent learned lessons: {lessons}")
        except Exception as e:
            logger.warning(f"MetaAgent learning failed: {e}", exc_info=True)

if __name__ == "__main__":
    node = MetaAgentNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("MetaAgent stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in MetaAgent: {e}", exc_info=True)