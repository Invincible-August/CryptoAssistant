import request from './request'

export const marketApi = {
  getKlines: (symbol: string, interval = '1h', limit = 200) =>
    request.get('/market/klines', { params: { symbol, interval, limit } }),

  getTrades: (symbol: string, limit = 100) =>
    request.get('/market/trades', { params: { symbol, limit } }),

  getOrderbook: (symbol: string) =>
    request.get('/market/orderbook', { params: { symbol } }),

  getFunding: (symbol: string) =>
    request.get('/market/funding', { params: { symbol } }),

  getOI: (symbol: string) =>
    request.get('/market/oi', { params: { symbol } }),
}
