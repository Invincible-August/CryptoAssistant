"""
Build Lightweight Charts–compatible series payloads from indicator result DataFrames.

This module bridges indicator plugin output (pandas) and the JSON shape expected
by the frontend (time/value series, optional per-bar colors for histograms).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Type

import pandas as pd
from loguru import logger

from app.indicators.base import BaseIndicator
from app.lightweight_charts_compat.chart_mapping import (
    get_indicator_chart_config,
    indicator_to_tv_overlay,
    indicator_to_tv_pane,
)


def _resolve_field_template(field_template: str, params: Dict[str, Any]) -> str:
    """
    Replace placeholders like '{period}' in field template using validated params.

    Args:
        field_template: Series field name, possibly containing {placeholders}.
        params: Validated indicator parameters.

    Returns:
        Resolved column name to read from the result DataFrame.
    """
    resolved: str = field_template
    for key, value in params.items():
        resolved = resolved.replace("{" + key + "}", str(value))
    return resolved


def _column_to_time_value_list(
    result_df: pd.DataFrame,
    value_column: str,
    histogram_colors: bool,
    color_positive: str,
    color_negative: str,
) -> List[Dict[str, Any]]:
    """
    Convert a result column to [{time, value}] or histogram points with color.

    Args:
        result_df: Indicator calculate() output.
        value_column: Numeric column name.
        histogram_colors: If True, set 'color' per bar from value sign.
        color_positive: Histogram color for value >= 0.
        color_negative: Histogram color for value < 0.

    Returns:
        Points compatible with indicator_to_tv_* input (time as datetime or unix).
    """
    from app.lightweight_charts_compat.chart_mapping import _to_unix_timestamp  # noqa: SLF001

    rows: List[Dict[str, Any]] = []
    if value_column not in result_df.columns:
        logger.warning("指标列不存在，跳过: %s", value_column)
        return rows

    for _, row in result_df.iterrows():
        raw_time = row.get("open_time")
        val = row.get(value_column)
        if raw_time is None or val is None:
            continue
        if isinstance(val, (float, int)) and pd.isna(val):
            continue
        ts = _to_unix_timestamp(raw_time)
        if ts is None:
            continue
        point: Dict[str, Any] = {
            "time": raw_time,
            "value": float(val),
        }
        if histogram_colors:
            point["color"] = (
                color_positive if float(val) >= 0.0 else color_negative
            )
        rows.append(point)
    return rows


def build_indicator_chart_payloads(
    indicator_cls: Type[BaseIndicator],
    indicator_key: str,
    result_df: pd.DataFrame,
    validated_params: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split indicator output into main-chart overlays and sub-chart groups.

    Uses display_config.series when present; otherwise falls back to a single
    series derived from chart_mapping defaults and the first numeric column.

    Args:
        indicator_cls: Indicator class.
        indicator_key: Registered indicator key.
        result_df: Output of calculate().
        validated_params: Params returned by validate_params().

    Returns:
        Tuple of (overlay_series_list, subchart_groups).
        Each subchart group is {"title": str, "series": [ {...}, ... ]}.
    """
    overlays: List[Dict[str, Any]] = []
    subcharts: List[Dict[str, Any]] = []

    chart_defaults = get_indicator_chart_config(indicator_key)
    display_cfg = getattr(indicator_cls, "display_config", None) or {}
    series_specs = display_cfg.get("series")

    if series_specs:
        sub_series: List[Dict[str, Any]] = []
        main_series: List[Dict[str, Any]] = []
        for spec in series_specs:
            field_t = spec.get("field", "")
            resolved_col = _resolve_field_template(field_t, validated_params)
            stype = spec.get("type", "line")
            is_hist = stype == "histogram"
            cp = spec.get("color_positive", "#F44336")
            cn = spec.get("color_negative", "#4CAF50")
            line_color = spec.get(
                "color", chart_defaults.get("default_color", "#9E9E9E")
            )
            points = _column_to_time_value_list(
                result_df,
                resolved_col,
                histogram_colors=is_hist,
                color_positive=cp,
                color_negative=cn,
            )
            if not points:
                continue

            panel = display_cfg.get("panel", "main")
            name = spec.get("name", resolved_col)
            if is_hist:
                series_obj = indicator_to_tv_pane(
                    points,
                    series_name=name,
                    chart_type="histogram",
                    color=line_color,
                )
            else:
                series_obj = indicator_to_tv_overlay(
                    points,
                    series_name=name,
                    color=line_color,
                    line_width=2,
                )

            if panel == "sub":
                sub_series.append(series_obj)
            else:
                main_series.append(series_obj)

        if sub_series:
            subcharts.append(
                {
                    "title": indicator_cls.name or indicator_key,
                    "series": sub_series,
                }
            )
        overlays.extend(main_series)
        return overlays, subcharts

    # ---- Fallback: single series from first numeric column ----
    numeric_cols = [
        c
        for c in result_df.columns
        if c != "open_time" and pd.api.types.is_numeric_dtype(result_df[c])
    ]
    if not numeric_cols:
        return overlays, subcharts

    value_col = numeric_cols[0]
    points = _column_to_time_value_list(
        result_df,
        value_col,
        histogram_colors=False,
        color_positive="#F44336",
        color_negative="#4CAF50",
    )
    if not points:
        return overlays, subcharts

    display_type = chart_defaults.get("display_type", "overlay")
    if display_type == "overlay":
        overlays.append(
            indicator_to_tv_overlay(
                points,
                series_name=indicator_key,
                color=chart_defaults.get("default_color", "#9E9E9E"),
                line_width=chart_defaults.get("line_width", 1),
            )
        )
    else:
        subcharts.append(
            {
                "title": indicator_cls.name or indicator_key,
                "series": [
                    indicator_to_tv_pane(
                        points,
                        series_name=indicator_key,
                        chart_type=chart_defaults.get("chart_type", "line"),
                        color=chart_defaults.get("default_color", "#9E9E9E"),
                    )
                ],
            }
        )

    return overlays, subcharts

