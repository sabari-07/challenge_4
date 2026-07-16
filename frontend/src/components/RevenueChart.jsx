import React from 'react'
import { motion } from 'framer-motion'
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { format, parseISO } from 'date-fns'

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="glass-effect-strong rounded-lg p-4 border border-white/20">
        <p className="text-sm text-gray-400 mb-2">{format(parseISO(label), 'MMM dd, yyyy')}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }}></div>
            <span className="text-white font-medium">{entry.name}:</span>
            <span className="text-trading-cyan">${entry.value.toLocaleString()}</span>
          </div>
        ))}
      </div>
    )
  }
  return null
}

const RevenueChart = ({ data, loading, dateRange }) => {
  if (loading || !data) {
    return (
      <div className="glass-effect rounded-2xl p-8 animate-pulse">
        <div className="h-8 bg-white/10 rounded w-1/3 mb-6"></div>
        <div className="h-[400px] bg-white/5 rounded"></div>
      </div>
    )
  }

  // Process data for chart
  const chartData = data.reduce((acc, item) => {
    const existing = acc.find(d => d.date === item.date)
    if (existing) {
      existing[item.channel] = item.revenue
    } else {
      acc.push({
        date: item.date,
        [item.channel]: item.revenue
      })
    }
    return acc
  }, [])

  const channels = ['google', 'bing', 'meta']
  const colors = {
    google: '#1e40af',
    bing: '#06b6d4',
    meta: '#8b5cf6'
  }

  // Dynamic heading based on date range
  const getDateRangeLabel = (days) => {
    if (days === 30) return 'Last 30 Days'
    if (days === 90) return 'Last 90 Days'
    if (days === 180) return 'Last 6 Months'
    if (days === 365) return 'Last Year'
    if (days === 886) return 'All Time (886 days)'
    return `Last ${days} Days`
  }

  return (
    <motion.div
      className="glass-effect rounded-2xl p-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h2 className="text-2xl font-bold mb-6">Revenue Trend ({getDateRangeLabel(dateRange || 90)})</h2>

      <ResponsiveContainer width="100%" height={400}>
        <AreaChart data={chartData}>
          <defs>
            {channels.map(channel => (
              <linearGradient key={channel} id={`color${channel}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={colors[channel]} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={colors[channel]} stopOpacity={0}/>
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis
            dataKey="date"
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: 'rgba(255,255,255,0.7)' }}
            tickFormatter={(value) => format(parseISO(value), 'MMM dd')}
          />
          <YAxis
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: 'rgba(255,255,255,0.7)' }}
            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="circle"
          />
          {channels.map(channel => (
            <Area
              key={channel}
              type="monotone"
              dataKey={channel}
              stroke={colors[channel]}
              fill={`url(#color${channel})`}
              strokeWidth={2}
              name={channel.toUpperCase()}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

export default RevenueChart
