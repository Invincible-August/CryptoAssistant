import request from './request'

/**
 * Task lifecycle status returned by `GET /market/import/{task_id}`.
 */
export type MarketImportStatus = 'pending' | 'running' | 'completed' | 'failed'

/**
 * Payload for `POST /market/import`.
 * Datetimes must be timezone-aware ISO-8601 strings (e.g. ending with `Z`).
 */
export interface MarketImportCreatePayload {
  name?: string
  exchange: string
  market_type: string
  symbol: string
  timeframe: string
  start_date: string
  end_date: string
  import_types: string[]
}

/**
 * Normalized `result_json` shape produced by the import worker (best-effort typing).
 */
export interface MarketImportResultJson {
  summary?: {
    import_types_requested?: string[]
    import_types_completed?: string[]
    rows_total?: number
  }
  type_results?: Record<string, unknown>
  errors?: unknown[]
}

/**
 * Single task row returned by `GET /market/import/{task_id}` (`ResponseBase.data`).
 */
export interface MarketImportTaskData {
  id: number
  name?: string | null
  created_by?: number | null
  exchange: string
  market_type: string
  symbol: string
  timeframe: string
  start_date: string
  end_date: string
  import_types: string[]
  status: MarketImportStatus
  progress: number
  result_json?: MarketImportResultJson | null
  last_error?: string | null
  created_at: string
  updated_at?: string | null
  finished_at?: string | null
}

/**
 * API wrapper for market historical import tasks.
 */
export const marketImportApi = {
  /**
   * Create a background import task; returns `{ data: { task_id } }` on success.
   */
  create: (payload: MarketImportCreatePayload) => request.post('/market/import', payload),

  /**
   * Poll task status, progress, and `result_json`.
   */
  getTask: (taskId: number) => request.get(`/market/import/${taskId}`),
}
