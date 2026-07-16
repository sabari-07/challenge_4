import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { format, parseISO } from 'date-fns'
import { TrendingUp } from 'lucide-react'

const CHANNEL_COLORS = {
  google: '#3b82f6',
  bing: '#06b6d4',
  meta: '#8b5cf6'
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const lines = payload.filter(p => !String(p.dataKey).endsWith('_base') && !String(p.dataKey).endsWith('_band'))
  return (
    <div className="glass-effect-strong rounded-lg p-4 border border-white/20">
      <p className="text-sm text-gray-400 mb-2">{label ? format(parseISO(label), 'MMM dd, yyyy') : ''}</p>
      {lines.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 mb-1">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-white font-medium">{String(entry.name).toUpperCase()}:</span>
          <span className="text-trading-cyan">${Number(entry.value).toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

const ForecastChart = ({ forecastData, horizon }) => {
  const { chartData, activeChannels } = useMemo(() => {
    if (!forecastData?.forecast?.channels) return { chartData: [], activeChannels: [] }

    const channels = Object.keys(forecastData.forecast.channels)
    const dateMap = {}

    channels.forEach(channel => {
      const daily = forecastData.forecast.channels[channel]?.daily_forecast || []
      daily.forEach(day => {
        if (!day.date) return  // skip rows where date was sanitized to null
        if (!dateMap[day.date]) dateMap[day.date] = { date: day.date }
        const lower = Math.max(0, Math.round(day.yhat_lower ?? 0))
        const upper = Math.max(0, Math.round(day.yhat_upper ?? 0))
        dateMap[day.date][channel] = Math.max(0, Math.round(day.yhat ?? 0))
        dateMap[day.date][`${channel}_base`] = lower
        dateMap[day.date][`${channel}_band`] = Math.max(0, upper - lower)
      })
    })

    return {
      chartData: Object.values(dateMap)
        .filter(row => row.date)
        .sort((a, b) => a.date.localeCompare(b.date)),
      activeChannels: channels
    }
  }, [forecastData])

  if (!chartData.length) return null

  return (
    <motion.div
      className="glass-effect rounded-2xl p-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h2 className="text-2xl font-bold mb-1 flex items-center gap-2">
        <TrendingUp className="w-6 h-6 text-trading-cyan" />
        Daily Revenue Forecast ({horizon}-Day Horizon)
      </h2>
      <p className="text-sm text-gray-400 mb-6">Shaded bands show P10–P90 confidence intervals per channel</p>

      <ResponsiveContainer width="100%" height={420}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            {activeChannels.map(channel => (
              <linearGradient key={channel} id={`fcGrad_${channel}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHANNEL_COLORS[channel] || '#888'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={CHANNEL_COLORS[channel] || '#888'} stopOpacity={0.05} />
              </linearGradient>
            ))}
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />

          <XAxis
            dataKey="date"
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.65)', fontSize: 12 }}
            tickFormatter={(v) => { try { return format(parseISO(v), 'MMM dd') } catch { return '' } }}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.65)', fontSize: 12 }}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
            width={60}
          />

          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="circle"
            formatter={(value) => String(value).toUpperCase()}
          />

          {activeChannels.map(channel => (
            <React.Fragment key={channel}>
              <Area
                type="monotone"
                dataKey={`${channel}_base`}
                stackId={channel}
                stroke="none"
                fill="transparent"
                legendType="none"
                hide
              />
              <Area
                type="monotone"
                dataKey={`${channel}_band`}
                stackId={channel}
                stroke="none"
                fill={`url(#fcGrad_${channel})`}
                legendType="none"
                hide
              />
              <Line
                type="monotone"
                dataKey={channel}
                stroke={CHANNEL_COLORS[channel] || '#888'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                name={channel}
              />
            </React.Fragment>
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

export default ForecastChart
