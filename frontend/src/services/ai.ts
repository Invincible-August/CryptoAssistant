import request from './request'

export const aiApi = {
  analyze: (data: {
    symbol: string
    exchange?: string
    market_type?: string
    custom_prompt?: string
  }) => request.post('/ai/analyze', data),

  suggestIndicator: (symbol: string) =>
    request.post('/ai/suggest-indicator', null, { params: { symbol } }),

  suggestFactor: (symbol: string) =>
    request.post('/ai/suggest-factor', null, { params: { symbol } }),

  listRecords: (symbol?: string, limit = 20) =>
    request.get('/ai/records', { params: { symbol, limit } }),

  feedback: (data: {
    record_id: number
    feedback_type: string
    feedback_text: string
  }) => request.post('/ai/feedback', data),
}
