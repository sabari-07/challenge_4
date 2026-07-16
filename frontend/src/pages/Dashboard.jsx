import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  TrendingUp, DollarSign, Target, Zap, ArrowRight, Activity,
  BarChart3, ChevronDown, ChevronUp, CheckCircle, Database,
  Upload, AlertCircle, RefreshCw
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

import Navbar from '../components/Navbar'
import MetricCard from '../components/MetricCard'
import RevenueChart from '../components/RevenueChart'
import ChannelBreakdown from '../components/ChannelBreakdown'

const CHANNEL_COLORS = {
  google: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/40', dot: 'bg-blue-400' },
  bing:   { bg: 'bg-cyan-500/20',  text: 'text-cyan-400',  border: 'border-cyan-500/40',  dot: 'bg-cyan-400'  },
  meta:   { bg: 'bg-purple-500/20',text: 'text-purple-400',border: 'border-purple-500/40',dot: 'bg-purple-400' },
}

const FEATURES = [
  {
    icon: <Zap className="w-6 h-6" />,
    title: 'Probabilistic Forecasting',
    desc: 'Prophet-powered 30/60/90-day revenue forecasts with P10–P90 confidence intervals per channel.',
    color: 'text-trading-cyan',
    bg: 'from-trading-cyan/10 to-transparent',
  },
  {
    icon: <Target className="w-6 h-6" />,
    title: 'Budget Optimization',
    desc: 'SLSQP-based optimizer that maximizes blended ROAS across Google, Bing, and Meta under a fixed spend constraint.',
    color: 'text-trading-purple',
    bg: 'from-trading-purple/10 to-transparent',
  },
  {
    icon: <BarChart3 className="w-6 h-6" />,
    title: 'Campaign-Level Insights',
    desc: 'Drill into individual campaigns or campaign types with per-unit revenue and ROAS forecasts.',
    color: 'text-trading-blue',
    bg: 'from-trading-blue/10 to-transparent',
  },
  {
    icon: <Activity className="w-6 h-6" />,
    title: 'AI Executive Summaries',
    desc: 'Cohere command-r-plus synthesises every forecast into a plain-English decision brief automatically.',
    color: 'text-trading-green',
    bg: 'from-trading-green/10 to-transparent',
  },
]

const fetchDataSummary = () => axios.get('/api/data/summary').then(r => r.data.data)
const fetchHistoricalData = (days) => axios.get(`/api/data/historical?days=${days}`).then(r => r.data.data)
const fetchDataStatus = () => axios.get('/api/data-status').then(r => r.data)

const Dashboard = () => {
  const navigate = useNavigate()
  const [showAnalytics, setShowAnalytics] = useState(false)
  const [dateRange, setDateRange] = useState(90)

  const { data: dataStatus, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['dataStatus'],
    queryFn: fetchDataStatus,
    refetchInterval: 15000,
  })

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['dataSummary'],
    queryFn: fetchDataSummary,
    enabled: showAnalytics,
  })

  const { data: historicalData, isLoading: histDataLoading } = useQuery({
    queryKey: ['historicalData', dateRange],
    queryFn: () => fetchHistoricalData(dateRange),
    enabled: showAnalytics,
  })

  const totalRevenue = summary ? Object.values(summary.channels).reduce((s, ch) => s + ch.total_revenue, 0) : 0
  const totalSpend   = summary ? Object.values(summary.channels).reduce((s, ch) => s + ch.total_spend, 0) : 0
  const avgRoas = totalSpend > 0 ? totalRevenue / totalSpend : 0

  const activeChannels = dataStatus?.metadata?.channels?.map(c => c.toLowerCase()) || []
  const usingUploaded  = dataStatus?.using_uploaded_data || false
  const uploadedFiles  = dataStatus?.uploaded_files || []

  return (
    <div className="min-h-screen">
      <Navbar />

      {/* ── Hero ── */}
      <div className="relative overflow-hidden">
        <div className="relative z-10 container mx-auto px-6 py-20">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h1 className="text-6xl font-bold mb-6 bg-gradient-to-r from-trading-cyan via-trading-blue to-trading-purple bg-clip-text text-transparent">
              RevenueIQ
            </h1>
            <p className="text-xl text-gray-300 max-w-2xl mx-auto">
              AI-powered probabilistic revenue forecasting for e-commerce paid advertising — Google, Bing &amp; Meta.
            </p>
          </motion.div>

          {/* Quick actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="flex flex-wrap justify-center gap-4 mb-16"
          >
            <button
              onClick={() => navigate('/forecast')}
              className="px-8 py-4 bg-gradient-to-r from-trading-blue to-trading-cyan rounded-xl font-semibold flex items-center gap-2 hover:scale-105 transition-transform glow-blue"
            >
              <Zap className="w-5 h-5" />
              Generate Forecast
              <ArrowRight className="w-5 h-5" />
            </button>
            <button
              onClick={() => navigate('/budget-optimizer')}
              className="px-8 py-4 glass-effect-strong rounded-xl font-semibold flex items-center gap-2 hover:scale-105 transition-transform"
            >
              <Target className="w-5 h-5" />
              Optimize Budget
            </button>
          </motion.div>
        </div>
      </div>

      <div className="container mx-auto px-6 space-y-10 pb-16">

        {/* ── Feature Cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h2 className="text-2xl font-bold text-white mb-6">Platform Capabilities</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.35 + i * 0.07 }}
                className={`glass-effect rounded-2xl p-6 bg-gradient-to-br ${f.bg} border border-white/5`}
              >
                <div className={`${f.color} mb-4`}>{f.icon}</div>
                <h3 className={`font-semibold text-base mb-2 ${f.color}`}>{f.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* ── Dataset Status ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-effect rounded-2xl p-6"
        >
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <Database className="w-5 h-5 text-trading-cyan" />
              <h2 className="text-lg font-semibold text-white">Active Dataset</h2>
              {statusLoading
                ? <span className="text-xs text-gray-500 animate-pulse">Loading…</span>
                : (
                  <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                    usingUploaded
                      ? 'bg-trading-green/20 text-trading-green border border-trading-green/30'
                      : 'bg-trading-cyan/20 text-trading-cyan border border-trading-cyan/30'
                  }`}>
                    {usingUploaded ? 'Uploaded Data' : 'Default Dataset'}
                  </span>
                )
              }
            </div>
            <button
              onClick={() => refetchStatus()}
              className="text-gray-500 hover:text-trading-cyan transition-colors"
              title="Refresh status"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {/* Per-channel status */}
          <div className="flex flex-wrap gap-3 mb-4">
            {(['google', 'bing', 'meta']).map(ch => {
              const active = activeChannels.includes(ch)
              const c = CHANNEL_COLORS[ch]
              return (
                <div
                  key={ch}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-all ${
                    active
                      ? `${c.bg} ${c.text} ${c.border}`
                      : 'bg-white/5 text-gray-600 border-gray-700/50'
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${active ? c.dot : 'bg-gray-600'}`} />
                  <span className="uppercase">{ch}</span>
                  {active
                    ? <CheckCircle className="w-3.5 h-3.5" />
                    : <AlertCircle className="w-3.5 h-3.5" />
                  }
                </div>
              )
            })}
          </div>

          {/* Uploaded file list */}
          {usingUploaded && uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-1">
              {uploadedFiles.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-gray-400">
                  <Upload className="w-3.5 h-3.5 text-trading-green flex-shrink-0" />
                  <span className="truncate">{typeof f === 'string' ? f : f.filename || f.name || JSON.stringify(f)}</span>
                </div>
              ))}
            </div>
          )}

          {!usingUploaded && (
            <p className="text-xs text-gray-500 mt-2">
              Using built-in historical data (Jan 2024 – Jun 2026). Upload your own CSVs on the Forecast page to override.
            </p>
          )}

          {dataStatus?.metadata?.date_range && (
            <div className="mt-4 pt-4 border-t border-white/10 grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-500 text-xs mb-1">Date Range</p>
                <p className="text-white font-medium">
                  {dataStatus.metadata.date_range.start
                    ? `${dataStatus.metadata.date_range.start?.slice(0, 10)} → ${dataStatus.metadata.date_range.end?.slice(0, 10)}`
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-gray-500 text-xs mb-1">Total Records</p>
                <p className="text-white font-medium">{dataStatus.total_records?.toLocaleString() ?? '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs mb-1">Channels Loaded</p>
                <p className="text-white font-medium">{activeChannels.length} / 3</p>
              </div>
            </div>
          )}
        </motion.div>

        {/* ── Detailed Analytics Toggle ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
        >
          <button
            onClick={() => setShowAnalytics(v => !v)}
            className="w-full glass-effect rounded-2xl px-8 py-5 flex items-center justify-between hover:bg-white/5 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <BarChart3 className="w-5 h-5 text-trading-cyan" />
              <span className="text-lg font-semibold text-white">Detailed Analytics</span>
              <span className="text-xs text-gray-500">Revenue trend, channel breakdown &amp; key insights</span>
            </div>
            <div className="flex items-center gap-2 text-trading-cyan group-hover:text-white transition-colors">
              <span className="text-sm font-medium">{showAnalytics ? 'Hide' : 'View'}</span>
              {showAnalytics ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </div>
          </button>

          <AnimatePresence>
            {showAnalytics && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.4, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <div className="pt-6 space-y-10">
                  {/* Metric Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <MetricCard
                      title="Total Revenue"
                      value={`$${(totalRevenue / 1000).toFixed(1)}K`}
                      change="+12.5%"
                      positive={true}
                      icon={<DollarSign className="w-6 h-6" />}
                      loading={summaryLoading}
                    />
                    <MetricCard
                      title="Total Spend"
                      value={`$${(totalSpend / 1000).toFixed(1)}K`}
                      change="+8.2%"
                      positive={true}
                      icon={<Activity className="w-6 h-6" />}
                      loading={summaryLoading}
                    />
                    <MetricCard
                      title="Blended ROAS"
                      value={avgRoas.toFixed(2) + 'x'}
                      change="+0.3"
                      positive={true}
                      icon={<TrendingUp className="w-6 h-6" />}
                      loading={summaryLoading}
                    />
                  </div>

                  {/* Revenue Trend */}
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-xl font-semibold text-white">Revenue Trend</h2>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-400">Period:</span>
                        <select
                          value={dateRange}
                          onChange={(e) => setDateRange(Number(e.target.value))}
                          className="glass-effect px-4 py-2 rounded-xl text-white bg-transparent border border-gray-700 focus:border-trading-cyan focus:outline-none text-sm"
                        >
                          <option value={30}  className="bg-trading-darker">Last 30 Days</option>
                          <option value={90}  className="bg-trading-darker">Last 90 Days</option>
                          <option value={180} className="bg-trading-darker">Last 6 Months</option>
                          <option value={365} className="bg-trading-darker">Last Year</option>
                          <option value={886} className="bg-trading-darker">All Time (886 days)</option>
                        </select>
                      </div>
                    </div>
                    <RevenueChart data={historicalData} loading={histDataLoading} dateRange={dateRange} />
                  </div>

                  {/* Channel Breakdown */}
                  <ChannelBreakdown summary={summary} loading={summaryLoading} />

                  {/* Key Insights */}
                  {summary && (
                    <div className="glass-effect rounded-2xl p-8">
                      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                        <Zap className="w-6 h-6 text-trading-cyan" />
                        Key Insights
                      </h2>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="glass-effect p-6 rounded-xl">
                          <h3 className="font-semibold text-lg mb-2 text-trading-cyan">Top Performing Channel</h3>
                          <p className="text-gray-300">
                            {Object.entries(summary.channels).sort((a, b) => b[1].avg_roas - a[1].avg_roas)[0][0].toUpperCase()} leads with{' '}
                            {Object.entries(summary.channels).sort((a, b) => b[1].avg_roas - a[1].avg_roas)[0][1].avg_roas.toFixed(2)}x ROAS
                          </p>
                        </div>
                        <div className="glass-effect p-6 rounded-xl">
                          <h3 className="font-semibold text-lg mb-2 text-trading-purple">Data Coverage</h3>
                          <p className="text-gray-300">
                            {summary.date_range.days} days of historical data from {summary.date_range.start} to {summary.date_range.end}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

      </div>

      <footer className="container mx-auto px-6 py-8 text-center text-gray-500">
        <p>© 2026 RevenueIQ. Powered by Cohere AI.</p>
      </footer>
    </div>
  )
}

export default Dashboard
