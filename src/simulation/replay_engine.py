# src/simulation/replay_engine.py
"""
Заглушка Replay Engine для воспроизведения событий.
В будущем будет загружать EventStore и симулировать исторические решения.
"""

class ReplayEngine:
    """Воспроизводит историю событий для проверки стратегий."""

    def __init__(self, event_store):
        self.event_store = event_store

    def replay_run(self, run_id: str):
        """Заглушка: просто печатает количество событий."""
        events = list(self.event_store.iter_events())
        print(f"Replay would process {len(events)} events for run {run_id}")
        return {"status": "stub", "events_count": len(events)}