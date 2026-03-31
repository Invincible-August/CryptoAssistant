import { useEffect, useRef } from 'react'
import {
  ColorType,
  createChart,
  CrosshairMode,
  type IChartApi,
  type Time,
} from 'lightweight-charts'
import type { ChartBundle } from '../../services/chart'

type Props = {
  bundle: ChartBundle | null
  mainHeight?: number
  subchartHeight?: number
}

/**
 * Renders K线 + 主图叠加线 + 多个副图（每组可含多条 line/histogram），
 * 数据格式与后端 /chart/bundle 一致。
 */
export default function LightweightChartBoard({
  bundle,
  mainHeight = 420,
  subchartHeight = 160,
}: Props) {
  const mainRef = useRef<HTMLDivElement>(null)
  const subsRef = useRef<HTMLDivElement>(null)
  const chartsRef = useRef<IChartApi[]>([])

  useEffect(() => {
    const mainEl = mainRef.current
    const subsEl = subsRef.current
    if (!bundle || !mainEl || !subsEl) return

    chartsRef.current.forEach((c) => c.remove())
    chartsRef.current = []
    mainEl.innerHTML = ''
    subsEl.innerHTML = ''

    const candleOpts = bundle.config?.candlestick_options ?? {}
    const rawChartOpts = bundle.config?.chart_options ?? {}
    const ro = rawChartOpts as {
      layout?: { background?: { type?: string; color?: string }; textColor?: string }
      grid?: object
      timeScale?: object
      crosshair?: object
      rightPriceScale?: object
    }
    const bg = ro.layout?.background?.color ?? '#1e1e2d'
    const textColor = ro.layout?.textColor ?? '#d1d4dc'

    const mainChart = createChart(mainEl, {
      width: mainEl.clientWidth,
      height: mainHeight,
      layout: {
        background: { type: ColorType.Solid, color: bg },
        textColor,
      },
      grid: (ro.grid ?? {}) as object,
      crosshair: {
        mode: CrosshairMode.Normal,
        ...(ro.crosshair as object),
      },
      timeScale: (ro.timeScale ?? {}) as object,
      rightPriceScale: (ro.rightPriceScale ?? { borderVisible: true }) as object,
    })

    chartsRef.current.push(mainChart)

    const candle = mainChart.addCandlestickSeries({
      upColor: (candleOpts as { upColor?: string }).upColor ?? '#26a69a',
      downColor: (candleOpts as { downColor?: string }).downColor ?? '#ef5350',
      borderVisible: false,
      wickUpColor: (candleOpts as { wickUpColor?: string }).wickUpColor ?? '#26a69a',
      wickDownColor: (candleOpts as { wickDownColor?: string }).wickDownColor ?? '#ef5350',
    })
    candle.setData(
      bundle.candlestick.map((b) => ({
        ...b,
        time: b.time as Time,
      })),
    )

    bundle.overlays?.forEach((ov) => {
      if (ov.type !== 'line') return
      const lw = Number(ov.options?.lineWidth)
      const line = mainChart.addLineSeries({
        color: (ov.options?.color as string) ?? '#2196f3',
        lineWidth: lw === 1 || lw === 2 || lw === 3 || lw === 4 ? lw : 2,
        priceLineVisible: false,
      })
      line.setData(
        ov.data.map((p) => ({ ...p, time: p.time as Time })),
      )
    })

    const subCharts: IChartApi[] = []
    bundle.subcharts?.forEach((group) => {
      const row = document.createElement('div')
      row.style.marginTop = '8px'
      const title = document.createElement('div')
      title.textContent = group.title
      title.style.color = textColor
      title.style.fontSize = '12px'
      title.style.marginBottom = '4px'
      row.appendChild(title)

      const pane = document.createElement('div')
      pane.style.width = '100%'
      pane.style.height = `${subchartHeight}px`
      row.appendChild(pane)
      subsEl.appendChild(row)

      const sc = createChart(pane, {
        width: pane.clientWidth,
        height: subchartHeight,
        layout: {
          background: { type: ColorType.Solid, color: bg },
          textColor,
        },
        grid: (ro.grid ?? {}) as object,
        crosshair: { mode: CrosshairMode.Normal },
        timeScale: (ro.timeScale ?? {}) as object,
        rightPriceScale: { borderVisible: true },
      })
      chartsRef.current.push(sc)
      subCharts.push(sc)

      group.series?.forEach((s) => {
        if (s.type === 'line') {
          const lw = Number(s.options?.lineWidth)
          const ls = sc.addLineSeries({
            color: (s.options?.color as string) ?? '#9e9e9e',
            lineWidth: lw === 1 || lw === 2 || lw === 3 || lw === 4 ? lw : 2,
            priceLineVisible: false,
          })
          ls.setData(s.data.map((p) => ({ ...p, time: p.time as Time })))
        } else if (s.type === 'histogram') {
          const hs = sc.addHistogramSeries({
            color: (s.options?.color as string) ?? '#26a69a',
            priceLineVisible: false,
          })
          hs.setData(
            s.data.map((p) => ({
              time: p.time as Time,
              value: p.value,
              color: p.color,
            })),
          )
        }
      })
    })

    const syncSubs = () => {
      const range = mainChart.timeScale().getVisibleLogicalRange()
      if (!range) return
      subCharts.forEach((c) => {
        c.timeScale().setVisibleLogicalRange(range)
      })
    }
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(syncSubs)
    syncSubs()

    mainChart.timeScale().fitContent()
    subCharts.forEach((c) => c.timeScale().fitContent())

    const onResize = () => {
      mainChart.applyOptions({ width: mainEl.clientWidth })
      mainChart.timeScale().fitContent()
      subCharts.forEach((c, i) => {
        const pane = subsEl.children[i]?.querySelector('div:last-child') as HTMLElement | null
        if (pane) {
          c.applyOptions({ width: pane.clientWidth })
          c.timeScale().fitContent()
        }
      })
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      chartsRef.current.forEach((c) => c.remove())
      chartsRef.current = []
      mainEl.innerHTML = ''
      subsEl.innerHTML = ''
    }
  }, [bundle, mainHeight, subchartHeight])

  if (!bundle) {
    return null
  }

  return (
    <div style={{ width: '100%' }}>
      <div ref={mainRef} style={{ width: '100%', minHeight: mainHeight }} />
      <div ref={subsRef} style={{ width: '100%' }} />
    </div>
  )
}
