"""
Backtest strategy preset loader.

Scans ``backend/config/backtest_strategies/*.yaml`` for strategy definitions
compatible with :func:`app.backtest.strategy_adapter.adapt_strategy_config`.
"""
from __future__ import annotations

import copy
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


def _backend_root() -> Path:
    """Directory that contains ``app/`` and ``config/``."""
    return Path(__file__).resolve().parent.parent.parent


def default_strategies_dir() -> Path:
    """Directory holding ``*.yaml`` preset files."""
    return _backend_root() / "config" / "backtest_strategies"


def deep_merge_strategy_dict(
    base: Dict[str, Any],
    override: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Deep-merge strategy_config: ``override`` wins on leaf conflicts.

    Nested dicts are merged recursively; lists and scalars are replaced
    when the key exists in ``override``.

    Args:
        base: Typically loaded from a preset YAML file.
        override: Optional request-body overrides.

    Returns:
        New merged dictionary (does not mutate inputs).
    """
    if not override:
        return copy.deepcopy(base)
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge_strategy_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class BacktestStrategyPresetService:
    """
    Cached listing + lookup of strategy preset YAML files.

    Uses directory mtime and per-file mtimes so new files appear without restart.
    """

    def __init__(
        self,
        directory: Optional[Path] = None,
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        """
        Args:
            directory: Override presets directory.
            cache_ttl_seconds: TTL for in-memory list cache.
        """
        self._directory = directory or default_strategies_dir()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._lock = threading.RLock()
        self._list_cache: Optional[List[Dict[str, Any]]] = None
        self._list_cache_key: Optional[float] = None
        self._cache_mono: float = 0.0
        self._full_cache: Dict[str, Dict[str, Any]] = {}

    def _ensure_dir(self) -> None:
        """Create the strategies directory if it does not exist."""
        self._directory.mkdir(parents=True, exist_ok=True)

    def _scan_disk(self) -> List[Dict[str, Any]]:
        """
        Read all ``*.yaml`` / ``*.yml`` files and build summary rows.

        Returns:
            List of dicts with id, display_name, description, file path.
        """
        self._ensure_dir()
        summaries: List[Dict[str, Any]] = []
        self._full_cache.clear()
        paths = sorted(
            {p.resolve() for p in self._directory.glob("*.yaml")}
            | {p.resolve() for p in self._directory.glob("*.yml")}
        )
        for path in paths:
            self._ingest_file(Path(path), summaries)
        return summaries

    def _ingest_file(self, path: Path, summaries: List[Dict[str, Any]]) -> None:
        """Parse one YAML file and append summary + full cache entry."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"Failed to read strategy preset {path}: {exc}")
            return
        if not isinstance(raw, dict):
            logger.warning(f"Strategy preset root must be a mapping: {path}")
            return
        preset_id = str(raw.get("id", "")).strip()
        display_name = str(raw.get("display_name", "")).strip()
        if not preset_id or not display_name:
            logger.warning(f"Preset missing id/display_name, skip: {path}")
            return
        strategy_cfg = raw.get("strategy_config")
        if not isinstance(strategy_cfg, dict):
            logger.warning(f"Preset strategy_config must be a dict: {path}")
            return
        description = str(raw.get("description", "")).strip()
        full = {
            "id": preset_id,
            "display_name": display_name,
            "description": description,
            "strategy_config": strategy_cfg,
        }
        self._full_cache[preset_id] = full
        summaries.append(
            {
                "id": preset_id,
                "display_name": display_name,
                "description": description,
            }
        )

    def _cache_fingerprint(self) -> float:
        """Heuristic fingerprint: max mtime of directory entries."""
        self._ensure_dir()
        mtimes = [self._directory.stat().st_mtime]
        for p in self._directory.iterdir():
            if p.is_file() and p.suffix.lower() in (".yaml", ".yml"):
                mtimes.append(p.stat().st_mtime)
        return max(mtimes) if mtimes else 0.0

    def list_summaries(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        Return preset summaries for UI dropdowns.

        Args:
            force_reload: Bypass TTL and rescan disk immediately.

        Returns:
            List of ``{id, display_name, description}``.
        """
        with self._lock:
            now = time.monotonic()
            fp = self._cache_fingerprint()
            if (
                not force_reload
                and self._list_cache is not None
                and self._list_cache_key == fp
                and (now - self._cache_mono) < self._cache_ttl_seconds
            ):
                return copy.deepcopy(self._list_cache)

            rows = self._scan_disk()
            self._list_cache = rows
            self._list_cache_key = fp
            self._cache_mono = now
            return copy.deepcopy(rows)

    def get_preset_by_id(self, preset_id: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load a full preset document by ``id``.

        Args:
            preset_id: The ``id`` field inside the YAML file.
            force_reload: When True, rescan before lookup.

        Returns:
            Dict with display_name, description, strategy_config.

        Raises:
            KeyError: If no preset matches ``preset_id``.
        """
        _ = self.list_summaries(force_reload=force_reload)
        entry = self._full_cache.get(preset_id)
        if entry is None:
            raise KeyError(preset_id)
        return {
            "id": entry["id"],
            "display_name": entry["display_name"],
            "description": entry["description"],
            "strategy_config": copy.deepcopy(entry["strategy_config"]),
        }


_preset_service_singleton: Optional[BacktestStrategyPresetService] = None


def get_backtest_strategy_preset_service() -> BacktestStrategyPresetService:
    """Process-wide preset service singleton."""
    global _preset_service_singleton
    if _preset_service_singleton is None:
        _preset_service_singleton = BacktestStrategyPresetService()
    return _preset_service_singleton
