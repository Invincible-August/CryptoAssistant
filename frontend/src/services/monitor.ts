import request from './request'

export interface MonitorWatch {
  id: number
  exchange: string
  symbol: string
  market_type: string
  event_type: string
  watch_status: string
  config_json?: Record<string, unknown> | null
  created_at: string
}

export interface MonitorWatchCreatePayload {
  exchange: string
  symbol: string
  market_type: string
  event_type: string
  config_json?: Record<string, unknown>
}

export const monitorApi = {
  listWatches: () => request.get('/monitor/watches'),
  addWatch: (payload: MonitorWatchCreatePayload) =>
    request.post('/monitor/watches', payload),
  deleteWatch: (watchId: number) => request.delete(`/monitor/watches/${watchId}`),
}

