import request from './request'

/** Backend /chart/bundle payload (Lightweight Charts). */
export interface ChartSeriesPayload {
  name: string
  type: 'line' | 'histogram'
  data: Array<{ time: number; value: number; color?: string }>
  options?: Record<string, unknown>
}

export interface ChartSubchartGroup {
  title: string
  series: ChartSeriesPayload[]
}

export interface ChartBundle {
  config: {
    chart_options?: Record<string, unknown>
    candlestick_options?: Record<string, unknown>
    symbol?: string
    interval?: string
  }
  candlestick: Array<{
    time: number
    open: number
    high: number
    low: number
    close: number
  }>
  overlays: ChartSeriesPayload[]
  subcharts: ChartSubchartGroup[]
  markers?: unknown[]
  meta?: {
    klines_loaded?: number
    failed_indicators?: Array<{ indicator_key: string; reason: string }>
  }
}

export const chartApi = {
  getBundle: (params: {
    symbol: string
    timeframe?: string
    exchange?: string
    market_type?: string
    limit?: number
    indicators?: string
    theme?: string
    source_mode?: 'cache' | 'live'
    force_refresh?: boolean
    use_proxy?: boolean
  }) => request.get<{ data: ChartBundle }>('/chart/bundle', { params }),
}
