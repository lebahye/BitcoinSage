"""
Polymarket Live Feed - Reads real-time edge signals from arb scanner Redis Streams.

The arb scanner bots (scanner-btc-15min, scanner-eth-15min) publish live
arbitrage opportunities to Redis Streams. This module reads that data
and feeds it into the BitcoinSage dashboard.

Redis: localhost:6379 (maps to redis-master Docker container)
Streams: edges:btc-15min, edges:eth-15min
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class PolymarketLiveFeed:
    """
    Reads live arbitrage edge signals from the Polymarket arb scanner Redis Streams.
    Falls back gracefully if Redis is unavailable.
    """

    STREAMS = {
        "btc-15min": "edges:btc-15min",
        "eth-15min": "edges:eth-15min",
    }
    HEARTBEAT_KEYS = {
        "btc-15min": "heartbeat:scanner-btc-15min",
        "eth-15min": "heartbeat:scanner-eth-15min",
    }
    HEARTBEAT_STALE_SECONDS = 30  # Scanner considered dead if no heartbeat in 30s

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client: Optional[object] = None
        self._connected = False
        self._connect()

    def _connect(self):
        if not REDIS_AVAILABLE:
            return
        try:
            self._client = redis.from_url(self.redis_url, decode_responses=True, socket_timeout=2)
            self._client.ping()
            self._connected = True
        except Exception:
            self._connected = False
            self._client = None

    @property
    def is_connected(self) -> bool:
        if not self._connected or not self._client:
            self._connect()
        return self._connected

    def get_latest_edges(self, count: int = 20) -> Dict[str, List[dict]]:
        """
        Get the most recent edge signals from all scanner streams.
        Returns dict keyed by scanner name with list of edge signal dicts.
        """
        if not self.is_connected:
            return {name: [] for name in self.STREAMS}

        result = {}
        for name, stream_key in self.STREAMS.items():
            try:
                msgs = self._client.xrevrange(stream_key, count=count)
                edges = []
                for msg_id, fields in msgs:
                    try:
                        data = json.loads(fields.get("data", "{}"))
                        data["_stream_id"] = msg_id
                        edges.append(data)
                    except (json.JSONDecodeError, AttributeError):
                        continue
                result[name] = edges
            except Exception:
                result[name] = []

        return result

    def get_scanner_health(self) -> Dict[str, dict]:
        """
        Check scanner liveness via heartbeat keys.
        Returns dict with status and age for each scanner.
        """
        if not self.is_connected:
            return {name: {"status": "offline", "age_seconds": None}
                    for name in self.HEARTBEAT_KEYS}

        health = {}
        for name, key in self.HEARTBEAT_KEYS.items():
            try:
                val = self._client.get(key)
                if val:
                    try:
                        ts = float(val)
                        age = time.time() - ts
                        status = "live" if age < self.HEARTBEAT_STALE_SECONDS else "stale"
                    except (ValueError, TypeError):
                        age = None
                        status = "live"
                    health[name] = {"status": status, "age_seconds": round(age, 1) if age else None}
                else:
                    health[name] = {"status": "offline", "age_seconds": None}
            except Exception:
                health[name] = {"status": "error", "age_seconds": None}

        return health

    def get_stream_stats(self) -> Dict[str, dict]:
        """Get stream length and recent activity stats."""
        if not self.is_connected:
            return {}

        stats = {}
        for name, stream_key in self.STREAMS.items():
            try:
                length = self._client.xlen(stream_key)
                stats[name] = {"total_signals": length}
            except Exception:
                stats[name] = {"total_signals": 0}
        return stats

    def get_summary(self) -> dict:
        """
        High-level summary for dashboard display:
        - Scanner health
        - Recent edge count
        - Best edge seen recently
        - Connection status
        """
        if not self.is_connected:
            return {
                "connected": False,
                "message": "Redis not available — arb system offline or unreachable",
                "scanners": {},
                "recent_edges": 0,
                "best_edge_pct": None,
            }

        health = self.get_scanner_health()
        edges = self.get_latest_edges(count=50)

        all_edges = []
        for name, edge_list in edges.items():
            all_edges.extend(edge_list)

        best_edge = None
        if all_edges:
            try:
                best_edge = max(
                    float(e.get("edge_pct", 0)) for e in all_edges
                    if e.get("edge_pct") is not None
                )
            except (ValueError, TypeError):
                pass

        return {
            "connected": True,
            "scanners": health,
            "recent_edges": len(all_edges),
            "best_edge_pct": round(best_edge, 3) if best_edge else None,
            "streams": self.get_stream_stats(),
        }
