"""Конфигурация SwarmNode с параметрами по умолчанию."""
import os
import uuid

class SwarmConfig:
    def __init__(self):
        self.NODE_ID = os.environ.get("NODE_ID", str(uuid.uuid4()))
        self.PORT = int(os.environ.get("PORT", 8000))
        self.PEERS = [p for p in os.environ.get("PEERS", "").split(",") if p]
        self.MARKET_URL = os.environ.get("MARKET_URL")
        self.BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
        self.FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))
        self.GOSSIP_INTERVAL = 1.5
        self.MAX_STATE = 200
        self.TTL = 300
        self.MAX_IMPORT = 2
        self.IMPORT_COOLDOWN = 5
        self.EXPECTED_RETURN_RATE = 0.1 * 0.05
        self.MAX_NORMALIZED_CAPITAL = 10000.0