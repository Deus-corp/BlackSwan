"""
Evolution Engine – мутации, генетика, memory replay.
"""
import logging
import time
import os
import asyncio
from swarm_config import config
from sim.genetic_engine import Genome
from src.evolution.mutation_engine import MutationEngine
from src.security.gossip_envelope import sign_envelope
from src.economy.roi_dispatcher import ROIDispatcher
from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation

logger = logging.getLogger(__name__)


class EvolutionEngine:
    def __init__(self, node):
        self.node = node          # ссылка на SwarmNode для доступа к его методам
        self.llm = node.llm
        self.mutation_engine = node.mutation_engine

    async def tick(self, market):
        """Один шаг эволюции. Вызывается из main_loop."""
        step = self.node.step_count
        # LLM Mutation & Memory replay (раз в 100 шагов)
        if step % 100 == 0:
            await self._mutate_with_context()

        # Генетический шаг (раз в 50 шагов)
        if step % 50 == 0:
            self._genetic_step()

        # Обновление цен
        self.node._prev_prev_price = self.node._prev_price
        if market:
            self.node._prev_price = market.get("price", self.node._prev_price)

    async def _mutate_with_context(self):
        # --- Сбор внешнего контекста (новости, сигналы, ордербук) ---
        external_context = ""
        if config.internet_researcher_enabled:
            try:
                external_context = await self.node.internet_researcher.gather_context()
            except Exception:
                external_context = ""
        if self.node.tradingview_enabled and self.node.tradingview_webhook.latest_signal:
            signal = self.node.tradingview_webhook.latest_signal
            external_context += f"\nTradingView signal: {signal}\n"
        if self.node.orderbook_enabled:
            for sym, analyzer in self.node.orderbook_analyzers.items():
                metrics = await analyzer.update()
                if metrics:
                    external_context += f"\n{sym} OrderBook: {analyzer.get_context_string()}"

        # --- Расширенный рыночный контекст ---
        market_context = ""
        m = getattr(self.node, '_last_market', None)
        if m:
            price = m.get('price', 0)
            prev1 = getattr(self.node, '_prev_price', price)
            prev2 = getattr(self.node, '_prev_prev_price', price)
            trend = "up" if price >= prev1 else "down"
            market_context = (
                f"price_now={price:.4f}, "
                f"price_prev1={prev1:.4f}, "
                f"price_prev2={prev2:.4f}, "
                f"trend={trend}, "
            )

        # --- Базовый контекст узла ---
        context = (
            f"volatility={self.node._current_volatility():.3f}, "
            f"dq={self.node.survival.dq:.3f}, "
            f"capital={self.node.capital:.2f}, "
            f"niche={self.node.node_niche()}, "
        )
        if market_context:
            context += market_context
        if external_context:
            context += "\n" + external_context

        # --- Memory replay: похожие успешные стратегии ---
        if len(self.node.memory) > 0:
            vol = self.node._current_volatility()
            similar = self.node.memory.find_similar(vol, self.node.survival.dq, top_k=3)
            if similar:
                memory_lines = ["Past successful strategies in similar conditions:"]
                for i, rec in enumerate(similar):
                    params = rec.get("params", {})
                    fitness = rec.get("fitness", 0.0)
                    memory_lines.append(f"{i+1}. params={params}, fitness={fitness:.4f}")
                memory_context = "\n".join(memory_lines)
                context += "\n" + memory_context

        # --- Топ-3 гена популяции ---
        if self.node.engine.population:
            top_genomes = sorted(
                [g for g in self.node.engine.population if isinstance(g, Genome)],
                key=lambda g: self.node.engine._fitness(g.params),
                reverse=True
            )[:3]
            if top_genomes:
                top_lines = ["Top-3 genomes in population:"]
                for i, g in enumerate(top_genomes):
                    top_lines.append(
                        f"{i+1}. params={g.params}, fitness={self.node.engine._fitness(g.params):.4f}, niche={g.niche}"
                    )
                context += "\n" + "\n".join(top_lines)

        # --- Вызов LLM мутации ---
        champion = self.node.engine.champion[0] if self.node.engine.champion else self.node.current_params
        new_params = self.mutation_engine.mutate(champion, context)
        if new_params != champion:
            genome = self.node.dict_to_genome({"params": new_params})
            self.node.engine.add_genome(genome)
            from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation
            note_llm_mutation()
            
    def _genetic_step(self):
        self.node.engine.evolve_generation()
        if self.node.engine.champion[1] > 0:
            current_vol = self.node._current_volatility()
            params_to_publish = self.node.semantic.apply_rules(
                self.node.engine.champion[0], current_vol, self.node.survival.dq
            )
            genome_dict = self.node.make_genome(params_to_publish, self.node.engine.champion[1])

            if config.gossip_signing_enabled:
                self.node.gossip_seq_no += 1
                self.node.gossip_lamport_ts += 1
                meta = {
                    "envelope_version": "1.0",
                    "domain": "blackswan-gossip-v1",
                    "payload_type": "memory.fact",
                    "topic": "swarm.genome",
                    "sender_peer_id": self.node.node_id,
                    "sender_node_id": self.node.node_id,
                    "sender_pubkey": self.node.gossip_public_bytes,
                    "key_id": self.node.gossip_key_id,
                    "key_version": 1,
                    "seq_no": self.node.gossip_seq_no,
                    "lamport_ts": self.node.gossip_lamport_ts,
                    "nonce": os.urandom(16).hex(),
                    "timestamp_ms": int(time.time() * 1000),
                    "ttl_ms": 60000,
                    "expires_at_ms": int(time.time() * 1000) + 60000,
                    "parent_hashes": [],
                }
                envelope = sign_envelope(genome_dict, meta, self.node.gossip_private_key)
                asyncio.create_task(self.node.crdt.add_genome(envelope.model_dump(mode='json')))
            else:
                payload = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
                genome_dict["signature"] = self.node.crypto.sign(payload)
                genome_dict["origin_pubkey"] = self.node.crypto.public_bytes_hex
                asyncio.create_task(self.node.crdt.add_genome(genome_dict))

            if self.node.engine.champion[1] > self.node.engine._fitness(self.node.current_params):
                self.node.current_params = self.node.engine.champion[0]
                self.node.dispatcher = ROIDispatcher(config=self.node.current_params)

            self.node.memory.add(
                market_volatility=current_vol,
                dq=self.node.survival.dq,
                capital=self.node.capital,
                params=self.node.engine.champion[0],
                fitness=self.node.engine.champion[1],
            )