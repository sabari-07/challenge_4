import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, Sector } from 'recharts'
import { TrendingUp, DollarSign, CreditCard, Target, BarChart3 } from 'lucide-react'

const COLORS = {
  google: '#3b82f6',
  bing: '#06b6d4',
  meta: '#a855f7'
}

const SHADOW_COLORS = {
  google: '#1e40af',
  bing: '#0891b2',
  meta: '#7c3aed'
}

const GRADIENTS = {
  google: 'from-blue-600 to-blue-800',
  bing: 'from-cyan-500 to-cyan-700',
  meta: 'from-purple-600 to-purple-800'
}

// Custom active shape for 3D pie chart with enhanced depth
const renderActiveShape = (props) => {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload } = props
  const channelName = payload.name.toLowerCase()

  return (
    <g filter="url(#glow)">
      {/* Shadow layer for depth */}
      <Sector
        cx={cx}
        cy={cy + 8}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 15}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={SHADOW_COLORS[channelName]}
        opacity={0.3}
      />
      {/* Main segment with gradient */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 15}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={`url(#gradient-${channelName})`}
      />
      {/* Inner ring highlight */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 8}
        outerRadius={innerRadius}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.8}
      />
      {/* Outer edge highlight */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={outerRadius + 13}
        outerRadius={outerRadius + 15}
        startAngle={startAngle}
        endAngle={endAngle}
        fill="rgba(255, 255, 255, 0.3)"
      />
    </g>
  )
}

// Custom render for 3D effect on all segments
const render3DShape = (props) => {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload } = props
  const channelName = payload.name.toLowerCase()

  return (
    <g>
      {/* Bottom shadow for 3D depth */}
      <Sector
        cx={cx}
        cy={cy + 6}
        innerRadius={innerRadius}
        outerRadius={outerRadius}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={SHADOW_COLORS[channelName]}
        opacity={0.4}
      />
      {/* Main segment with gradient */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={`url(#gradient-${channelName})`}
      />
      {/* Top highlight for glossy effect */}
      <Sector
        cx={cx}
        cy={cy - 2}
        innerRadius={innerRadius}
        outerRadius={outerRadius}
        startAngle={startAngle}
        endAngle={endAngle}
        fill="rgba(255, 255, 255, 0.15)"
        opacity={0.6}
      />
    </g>
  )
}

const ChannelBreakdown = ({ summary, loading }) => {
  const [activeIndex, setActiveIndex] = useState(null)
  const [selectedChannel, setSelectedChannel] = useState(null)

  if (loading || !summary) {
    return (
      <div className="glass-effect rounded-2xl p-8 animate-pulse">
        <div className="h-8 bg-white/10 rounded w-1/3 mb-6"></div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="h-80 bg-white/5 rounded"></div>
          <div className="lg:col-span-2 space-y-4">
            <div className="h-24 bg-white/5 rounded"></div>
            <div className="h-24 bg-white/5 rounded"></div>
            <div className="h-24 bg-white/5 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  const channelData = Object.entries(summary.channels).map(([name, data]) => ({
    name: name.toUpperCase(),
    value: data.total_revenue,
    spend: data.total_spend,
    roas: data.avg_roas,
    percentage: 0
  }))

  // Calculate percentages
  const totalRevenue = channelData.reduce((sum, ch) => sum + ch.value, 0)
  channelData.forEach(ch => {
    ch.percentage = ((ch.value / totalRevenue) * 100).toFixed(1)
  })

  // Sort by revenue (descending)
  channelData.sort((a, b) => b.value - a.value)

  const onPieEnter = (_, index) => {
    setActiveIndex(index)
  }

  const onPieLeave = () => {
    setActiveIndex(null)
  }

  return (
    <motion.div
      className="glass-effect rounded-2xl p-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-trading-cyan" />
            Channel Performance Breakdown
          </h2>
          <p className="text-gray-400 text-sm">Revenue distribution across all channels</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-400">Total Revenue</p>
          <p className="text-2xl font-bold text-white">${(totalRevenue / 1000).toFixed(1)}K</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Enhanced 3D Pie Chart */}
        <div className="flex flex-col items-center">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <defs>
                {/* Radial gradients for 3D effect */}
                <radialGradient id="gradient-google" cx="30%" cy="30%">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={1} />
                  <stop offset="50%" stopColor="#3b82f6" stopOpacity={1} />
                  <stop offset="100%" stopColor="#1e40af" stopOpacity={1} />
                </radialGradient>
                <radialGradient id="gradient-bing" cx="30%" cy="30%">
                  <stop offset="0%" stopColor="#67e8f9" stopOpacity={1} />
                  <stop offset="50%" stopColor="#06b6d4" stopOpacity={1} />
                  <stop offset="100%" stopColor="#0891b2" stopOpacity={1} />
                </radialGradient>
                <radialGradient id="gradient-meta" cx="30%" cy="30%">
                  <stop offset="0%" stopColor="#c084fc" stopOpacity={1} />
                  <stop offset="50%" stopColor="#a855f7" stopOpacity={1} />
                  <stop offset="100%" stopColor="#7c3aed" stopOpacity={1} />
                </radialGradient>
                {/* Glow filter for active state */}
                <filter id="glow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
              </defs>
              <Pie
                activeIndex={activeIndex}
                activeShape={renderActiveShape}
                shape={render3DShape}
                data={channelData}
                cx="50%"
                cy="45%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
                onMouseEnter={onPieEnter}
                onMouseLeave={onPieLeave}
                animationBegin={0}
                animationDuration={1000}
                animationEasing="ease-out"
              >
                {channelData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={`url(#gradient-${entry.name.toLowerCase()})`}
                    className="cursor-pointer transition-all drop-shadow-2xl"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth={2}
                  />
                ))}
              </Pie>
              <Tooltip
                offset={30}
                allowEscapeViewBox={{ x: true, y: true }}
                wrapperStyle={{ zIndex: 1000 }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload
                    return (
                      <div className="glass-effect-strong rounded-xl p-4 border border-white/20 min-w-[200px] shadow-2xl">
                        <p className="text-white font-semibold mb-3 text-lg">{data.name}</p>
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-gray-400 text-sm">Revenue:</span>
                            <span className="text-trading-cyan font-semibold">${(data.value / 1000).toFixed(1)}K</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400 text-sm">Share:</span>
                            <span className="text-white font-semibold">{data.percentage}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400 text-sm">ROAS:</span>
                            <span className="text-trading-green font-semibold">{data.roas.toFixed(2)}x</span>
                          </div>
                        </div>
                      </div>
                    )
                  }
                  return null
                }}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Total Revenue Label - Below Chart */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="mt-4 text-center"
          >
            <div className="relative inline-block">
              <div className="absolute inset-0 bg-trading-cyan/20 blur-xl rounded-full"></div>
              <div className="relative bg-trading-darker/90 backdrop-blur-sm rounded-2xl px-8 py-5 border-2 border-trading-cyan/30 shadow-lg shadow-trading-cyan/20">
                <p className="text-gray-400 text-xs mb-2 uppercase tracking-widest font-medium">Total Revenue</p>
                <p className="text-4xl font-bold bg-gradient-to-r from-trading-cyan via-trading-blue to-trading-purple bg-clip-text text-transparent">
                  ${(totalRevenue / 1000).toFixed(1)}K
                </p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Enhanced Channel Stats Cards */}
        <div className="lg:col-span-2 space-y-4">
          {channelData.map((channel, index) => (
            <motion.div
              key={channel.name}
              className={`relative overflow-hidden rounded-xl p-5 cursor-pointer transition-all border-2 ${
                selectedChannel === channel.name
                  ? 'border-trading-cyan bg-gradient-to-r ' + GRADIENTS[channel.name.toLowerCase()] + ' shadow-lg shadow-trading-cyan/20'
                  : 'border-transparent glass-effect hover:border-white/20'
              }`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              whileHover={{ scale: 1.02, y: -2 }}
              onClick={() => setSelectedChannel(selectedChannel === channel.name ? null : channel.name)}
            >
              {/* Background Gradient Overlay */}
              <div className={`absolute inset-0 bg-gradient-to-r ${GRADIENTS[channel.name.toLowerCase()]} opacity-0 hover:opacity-10 transition-opacity`}></div>

              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-4 h-4 rounded-full ring-4 ring-white/20"
                      style={{ backgroundColor: COLORS[channel.name.toLowerCase()] }}
                    ></div>
                    <div>
                      <h3 className="font-bold text-xl text-white">{channel.name}</h3>
                      <p className="text-sm text-gray-400">{channel.percentage}% of total revenue</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-2 text-trading-green bg-trading-green/10 px-3 py-1 rounded-full">
                      <TrendingUp className="w-4 h-4" />
                      <span className="font-bold text-sm">{channel.roas.toFixed(2)}x</span>
                    </div>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-white/5 rounded-lg p-3 backdrop-blur-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <DollarSign className="w-4 h-4 text-trading-cyan" />
                      <p className="text-gray-400 text-xs font-medium">Revenue</p>
                    </div>
                    <p className="text-white font-bold text-lg">${(channel.value / 1000).toFixed(1)}K</p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 backdrop-blur-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <CreditCard className="w-4 h-4 text-trading-purple" />
                      <p className="text-gray-400 text-xs font-medium">Spend</p>
                    </div>
                    <p className="text-white font-bold text-lg">${(channel.spend / 1000).toFixed(1)}K</p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 backdrop-blur-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <Target className="w-4 h-4 text-trading-green" />
                      <p className="text-gray-400 text-xs font-medium">Efficiency</p>
                    </div>
                    <p className="text-white font-bold text-lg">{((channel.value / channel.spend - 1) * 100).toFixed(0)}%</p>
                  </div>
                </div>

                {/* Expandable Details */}
                <AnimatePresence>
                  {selectedChannel === channel.name && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-4 pt-4 border-t border-white/10"
                    >
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-400">Daily Avg Revenue:</span>
                          <span className="text-white font-semibold">${((channel.value / 30) / 1000).toFixed(2)}K</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Daily Avg Spend:</span>
                          <span className="text-white font-semibold">${((channel.spend / 30) / 1000).toFixed(2)}K</span>
                        </div>
                        <div className="flex justify-between col-span-2">
                          <span className="text-gray-400">Profit Margin:</span>
                          <span className="text-trading-green font-semibold">{((1 - channel.spend / channel.value) * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Quick Stats Footer */}
      <div className="mt-6 pt-6 border-t border-white/10">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-gray-400 text-sm mb-1">Best Performer</p>
            <p className="text-trading-green font-bold">{channelData[0].name}</p>
            <p className="text-xs text-gray-500">{channelData[0].percentage}% share</p>
          </div>
          <div>
            <p className="text-gray-400 text-sm mb-1">Highest ROAS</p>
            <p className="text-trading-cyan font-bold">{[...channelData].sort((a, b) => b.roas - a.roas)[0].name}</p>
            <p className="text-xs text-gray-500">{[...channelData].sort((a, b) => b.roas - a.roas)[0].roas.toFixed(2)}x</p>
          </div>
          <div>
            <p className="text-gray-400 text-sm mb-1">Total Spend</p>
            <p className="text-trading-purple font-bold">${(channelData.reduce((sum, ch) => sum + ch.spend, 0) / 1000).toFixed(1)}K</p>
            <p className="text-xs text-gray-500">Across all channels</p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default ChannelBreakdown
