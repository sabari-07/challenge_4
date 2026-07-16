import { useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  ComposedChart, Bar, ErrorBar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import { TrendingUp } from 'lucide-react'

const CHANNEL_COLORS = {
  google: '#3b82f6',
  bing: '#06b6d4',
  meta: '#8b5cf6',
}
const PALETTE = ['#3b82f6', '#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#f97316', '#a78bfa']

const getColor = (channel, index) =>
  (channel && CHANNEL_COLORS[channel]) || PALETTE[index % PALETTE.length]

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div className="glass-effect-strong rounded-lg p-4 border border-white/20 min-w-[180px]">
      <p className="text-sm font-semibold text-white mb-3 truncate">{d.name}</p>
      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between gap-6">
          <span className="text-gray-400">Expected</span>
          <span className="text-white font-bold">${(d.expected / 1000).toFixed(1)}K</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-400">P10 (Low)</span>
          <span className="text-trading-cyan">${(d.lower / 1000).toFixed(1)}K</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-400">P90 (High)</span>
          <span className="text-trading-purple">${(d.upper / 1000).toFixed(1)}K</span>
        </div>
        <div className="border-t border-white/10 pt-1.5 flex justify-between gap-6">
          <span className="text-gray-400">Range</span>
          <span className="text-gray-300 text-xs">${(d.lower / 1000).toFixed(1)}K – ${(d.upper / 1000).toFixed(1)}K</span>
        </div>
      </div>
    </div>
  )
}

const AggregateForecastChart = ({ items, horizon, title }) => {
  const chartData = useMemo(() =>
    items.map((item, i) => ({
      ...item,
      errorY: [
        Math.max(0, item.expected - item.lower),
        Math.max(0, item.upper - item.expected),
      ],
      color: getColor(item.channel, i),
    })),
    [items]
  )

  if (!chartData.length) return null

  // Rotate labels when there are many items
  const rotateLabels = chartData.length > 5

  return (
    <motion.div
      className="glass-effect rounded-2xl p-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h2 className="text-2xl font-bold mb-1 flex items-center gap-2">
        <TrendingUp className="w-6 h-6 text-trading-cyan" />
        {title || `${horizon}-Day Revenue Forecast`}
      </h2>
      <p className="text-sm text-gray-400 mb-6">
        Aggregate period totals · Error bars show P10–P90 probabilistic range
      </p>

      <ResponsiveContainer width="100%" height={rotateLabels ? 420 : 360}>
        <ComposedChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: rotateLabels ? 80 : 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis
            dataKey="name"
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.65)', fontSize: rotateLabels ? 10 : 12 }}
            angle={rotateLabels ? -40 : 0}
            textAnchor={rotateLabels ? 'end' : 'middle'}
            interval={0}
          />
          <YAxis
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.65)', fontSize: 12 }}
            tickFormatter={v => `$${(v / 1000).toFixed(0)}K`}
            width={65}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
          <Bar dataKey="expected" name="Expected Revenue" radius={[6, 6, 0, 0]} maxBarSize={72}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.color} fillOpacity={0.85} />
            ))}
            <ErrorBar
              dataKey="errorY"
              width={8}
              strokeWidth={2}
              stroke="rgba(255,255,255,0.75)"
            />
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend chips */}
      <div className="flex flex-wrap gap-2 mt-4 justify-center">
        {chartData.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-gray-300">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: item.color }} />
            {item.name}
          </div>
        ))}
      </div>
    </motion.div>
  )
}

export default AggregateForecastChart
