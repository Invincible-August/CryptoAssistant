import request from './request'

export const factorApi = {
  list: (source?: string) =>
    request.get('/factors/', { params: source ? { source } : {} }),

  getMeta: (key: string) => request.get(`/factors/${key}/meta`),

  calculate: (data: {
    factor_key: string
    symbol: string
    exchange?: string
    market_type?: string
    timeframe?: string
    params?: Record<string, any>
  }) => request.post('/factors/calculate', data),

  getResults: (symbol: string, factorKey: string, limit = 50) =>
    request.get('/factors/results', {
      params: { symbol, factor_key: factorKey, limit },
    }),
}
