"""
Plugin runtime configuration service.

Reads and writes ``backend/config/plugin_runtime.yaml`` to control which
factors and indicators are marked as disabled (not loaded for calculation
pipelines). Disabled plugins remain registered in memory for discovery;
API list endpoints expose ``load_enabled`` for UI state.
"""
from __future__ import annotations

import copy
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from loguru import logger


def _backend_root() -> Path:
    """Resolve the backend package root (directory containing ``app/``)."""
    return Path(__file__).resolve().parent.parent.parent


def default_plugin_runtime_path() -> Path:
    """Return the canonical path to ``plugin_runtime.yaml``."""
    return _backend_root() / "config" / "plugin_runtime.yaml"


_DEFAULT_DOCUMENT: Dict[str, Any] = {
    "disabled_factors": [],
    "disabled_indicators": [],
}


class PluginRuntimeService:
    """
    Thread-safe reader/writer for plugin runtime YAML with short mtime cache.

    Attributes:
        _path: Filesystem path to the YAML file.
        _cache_ttl_seconds: How long to reuse parsed data without stat() check.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        """
        Initialize the service.

        Args:
            path: Optional override path; defaults to ``config/plugin_runtime.yaml``.
            cache_ttl_seconds: In-memory cache duration to reduce disk reads.
        """
        self._path = path or default_plugin_runtime_path()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._lock = threading.RLock()
        self._cached_doc: Optional[Dict[str, Any]] = None
        self._cached_mtime: Optional[float] = None
        self._cache_time_monotonic: float = 0.0

    def _ensure_file_exists(self) -> None:
        """Create parent dirs and a default YAML file if missing."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.is_file():
            self._atomic_write(_DEFAULT_DOCUMENT)
            logger.info(f"Created default plugin runtime config: {self._path}")

    def _atomic_write(self, document: Dict[str, Any]) -> None:
        """Serialize ``document`` to YAML atomically."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(
            document,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(self._path)

    def _load_raw_from_disk(self) -> Dict[str, Any]:
        """Read and parse YAML from disk (no cache)."""
        self._ensure_file_exists()
        raw_text = self._path.read_text(encoding="utf-8")
        loaded = yaml.safe_load(raw_text)
        if not isinstance(loaded, dict):
            logger.warning(
                "plugin_runtime.yaml root is not a mapping; using defaults"
            )
            return copy.deepcopy(_DEFAULT_DOCUMENT)
        merged = copy.deepcopy(_DEFAULT_DOCUMENT)
        merged.update(loaded)
        # Normalize list fields
        for key in ("disabled_factors", "disabled_indicators"):
            val = merged.get(key)
            if val is None:
                merged[key] = []
            elif not isinstance(val, list):
                merged[key] = [str(val)]
            else:
                merged[key] = [str(x).strip() for x in val if str(x).strip()]
        return merged

    def get_document(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Return the merged runtime document (copy).

        Args:
            force_reload: When True, bypass TTL cache and re-read from disk.

        Returns:
            Dict with ``disabled_factors`` and ``disabled_indicators`` lists.
        """
        with self._lock:
            now = time.monotonic()
            if (
                not force_reload
                and self._cached_doc is not None
                and (now - self._cache_time_monotonic) < self._cache_ttl_seconds
            ):
                return copy.deepcopy(self._cached_doc)

            self._ensure_file_exists()
            mtime = self._path.stat().st_mtime
            if (
                not force_reload
                and self._cached_doc is not None
                and self._cached_mtime == mtime
                and (now - self._cache_time_monotonic) < self._cache_ttl_seconds
            ):
                return copy.deepcopy(self._cached_doc)

            doc = self._load_raw_from_disk()
            self._cached_doc = doc
            self._cached_mtime = mtime
            self._cache_time_monotonic = now
            return copy.deepcopy(doc)

    def get_disabled_factors(self) -> Set[str]:
        """Return the set of disabled factor keys."""
        doc = self.get_document()
        return set(doc.get("disabled_factors", []))

    def get_disabled_indicators(self) -> Set[str]:
        """Return the set of disabled indicator keys."""
        doc = self.get_document()
        return set(doc.get("disabled_indicators", []))

    def is_factor_load_enabled(self, factor_key: str) -> bool:
        """True if the factor is allowed to run in pipelines and calculate API."""
        return factor_key not in self.get_disabled_factors()

    def is_indicator_load_enabled(self, indicator_key: str) -> bool:
        """True if the indicator is allowed to run in pipelines and calculate API."""
        return indicator_key not in self.get_disabled_indicators()

    def set_factor_disabled(self, factor_key: str, disabled: bool) -> Dict[str, Any]:
        """
        Add or remove a factor key from the disabled list and persist.

        Args:
            factor_key: Registered ``factor_key`` string.
            disabled: When True, add to disabled list; when False, remove.

        Returns:
            The persisted document (copy).
        """
        with self._lock:
            doc = self._load_raw_from_disk()
            factors: List[str] = list(doc.get("disabled_factors", []))
            fk = factor_key.strip()
            if disabled:
                if fk not in factors:
                    factors.append(fk)
            else:
                factors = [x for x in factors if x != fk]
            doc["disabled_factors"] = factors
            self._atomic_write(doc)
            self._cached_doc = doc
            self._cached_mtime = self._path.stat().st_mtime
            self._cache_time_monotonic = time.monotonic()
            return copy.deepcopy(doc)

    def set_indicator_disabled(
        self, indicator_key: str, disabled: bool
    ) -> Dict[str, Any]:
        """
        Add or remove an indicator key from the disabled list and persist.

        Args:
            indicator_key: Registered ``indicator_key`` string.
            disabled: When True, add to disabled list; when False, remove.

        Returns:
            The persisted document (copy).
        """
        with self._lock:
            doc = self._load_raw_from_disk()
            keys: List[str] = list(doc.get("disabled_indicators", []))
            ik = indicator_key.strip()
            if disabled:
                if ik not in keys:
                    keys.append(ik)
            else:
                keys = [x for x in keys if x != ik]
            doc["disabled_indicators"] = keys
            self._atomic_write(doc)
            self._cached_doc = doc
            self._cached_mtime = self._path.stat().st_mtime
            self._cache_time_monotonic = time.monotonic()
            return copy.deepcopy(doc)


_plugin_runtime_singleton: Optional[PluginRuntimeService] = None


def get_plugin_runtime_service() -> PluginRuntimeService:
    """Return the process-wide :class:`PluginRuntimeService` singleton."""
    global _plugin_runtime_singleton
    if _plugin_runtime_singleton is None:
        _plugin_runtime_singleton = PluginRuntimeService()
    return _plugin_runtime_singleton
