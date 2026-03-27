import request from './request'

export const indicatorApi = {
  list: (source?: string) =>
    request.get('/indicators/', { params: source ? { source } : {} }),

  getMeta: (key: string) => request.get(`/indicators/${key}/meta`),

  calculate: (data: {
    indicator_key: string
    symbol: string
    exchange?: string
    market_type?: string
    timeframe?: string
    params?: Record<string, any>
  }) => request.post('/indicators/calculate', data),

  getResults: (symbol: string, indicatorKey: string, limit = 50) =>
    request.get('/indicators/results', {
      params: { symbol, indicator_key: indicatorKey, limit },
    }),
}
