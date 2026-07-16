import { useState, useMemo, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Calendar, TrendingUp, AlertCircle, Filter, BarChart3, Search, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import Navbar from '../components/Navbar'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ForecastProgress from '../components/ForecastProgress'
import DataUpload from '../components/DataUpload'
import AggregateForecastChart from '../components/AggregateForecastChart'


// SSE-based forecast generation with real-time progress (POST to support future_spends)
const generateForecastWithSSE = async (data, onProgress) => {
  return new Promise((resolve, reject) => {
    fetch('/api/forecast/generate-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(async (response) => {
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()

        for (const part of parts) {
          const line = part.trim()
          if (line.startsWith('data: ')) {
            try {
              const progress = JSON.parse(line.substring(6))
              onProgress(progress)
              if (progress.step === 'complete') { resolve(progress.data); return }
              if (progress.step === 'error') { reject(new Error(progress.message)); return }
            } catch (err) {
              reject(err); return
            }
          }
        }
      }
    }).catch(reject)
  })
}

const generateCampaignTypeForecastWithSSE = async (data, onProgress) => {
  return new Promise((resolve, reject) => {
    const params = {
      horizon: data.horizon,
      channels: JSON.stringify(data.channels)
    }
    if (data.future_spends && Object.keys(data.future_spends).length > 0) {
      params.future_spends = JSON.stringify(data.future_spends)
    }
    const url = `/api/forecast/campaign-type-stream?${new URLSearchParams(params)}`

    const eventSource = new EventSource(url)

    eventSource.onmessage = (event) => {
      try {
        const progress = JSON.parse(event.data)
        onProgress(progress)

        if (progress.step === 'complete') {
          eventSource.close()
          resolve(progress.data)
        } else if (progress.step === 'error') {
          eventSource.close()
          reject(new Error(progress.message))
        }
      } catch (err) {
        eventSource.close()
        reject(err)
      }
    }

    eventSource.onerror = (error) => {
      eventSource.close()
      reject(error)
    }
  })
}

const generateCampaignLevelForecastWithSSE = async (data, onProgress) => {
  return new Promise((resolve, reject) => {
    // Use POST for campaign-level due to complex payload
    fetch('/api/forecast/campaign-level-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(async (response) => {
      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const progress = JSON.parse(line.substring(6))
            onProgress(progress)

            if (progress.step === 'complete') {
              resolve(progress.data)
              return
            } else if (progress.step === 'error') {
              reject(new Error(progress.message))
              return
            }
          }
        }
      }
    }).catch(reject)
  })
}

const fetchAvailableCampaigns = async (channel, minDataPoints) => {
  const channelParam = channel && channel !== 'all' ? `channel=${channel}` : ''
  const minDataParam = `min_data_points=${minDataPoints}`
  const params = [channelParam, minDataParam].filter(Boolean).join('&')
  const response = await axios.get(`/api/data/campaigns?${params}`)
  return response.data.data
}

// Campaign types are fetched from the backend dynamically based on loaded data

const Forecast = () => {
  const [horizon, setHorizon] = useState(30)
  const [selectedChannels, setSelectedChannels] = useState(['google', 'bing', 'meta'])
  const [selectedCampaignTypes, setSelectedCampaignTypes] = useState([])
  const [forecastLevel, setForecastLevel] = useState('channel') // 'channel', 'campaign-type', 'campaign'
  const [topNCampaigns, setTopNCampaigns] = useState(20)
  const [minDataPoints, setMinDataPoints] = useState(20)
  const [selectionMode, setSelectionMode] = useState('topN') // 'topN' | 'specific'
  const [selectedCampaignIds, setSelectedCampaignIds] = useState([])
  const [campaignSearchQuery, setCampaignSearchQuery] = useState('')
  const [availableChannels, setAvailableChannels] = useState(['google', 'bing', 'meta'])
  const [campaignTypesByChannel, setCampaignTypesByChannel] = useState({})

  // Future budget inputs
  const [useCustomBudgets, setUseCustomBudgets] = useState(false)
  const [futureSpends, setFutureSpends] = useState({ google: '', bing: '', meta: '' })

  const refreshDataState = async () => {
    try {
      const [statusRes, typesRes] = await Promise.all([
        axios.get('/api/data-status'),
        axios.get('/api/data/campaign-types')
      ])
      if (statusRes.data.success && statusRes.data.metadata?.channels) {
        const channels = statusRes.data.metadata.channels.map(ch => ch.toLowerCase())
        setAvailableChannels(channels)
        setSelectedChannels(prev => {
          const valid = prev.filter(ch => channels.includes(ch))
          return valid.length > 0 ? valid : channels
        })
        setFutureSpends(Object.fromEntries(channels.map(ch => [ch, ''])))
      }
      if (typesRes.data.success) {
        setCampaignTypesByChannel(typesRes.data.campaign_types_by_channel || {})
      }
    } catch (error) {
      console.error('Failed to fetch data state:', error)
    }
  }

  useEffect(() => {
    refreshDataState()
  }, [])

  // Progress state for SSE
  const [progressState, setProgressState] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [forecastData, setForecastData] = useState(null)
  const [campaignTypeData, setCampaignTypeData] = useState(null)
  const [campaignData, setCampaignData] = useState(null)

  const isLoadingCampaignType = isLoading && forecastLevel === 'campaign-type'
  const isLoadingCampaign = isLoading && forecastLevel === 'campaign'

  // Clear previous forecast results when forecast level changes
  useEffect(() => {
    setForecastData(null)
    setCampaignTypeData(null)
    setCampaignData(null)
  }, [forecastLevel])

  // Clear campaign-level results when switching between Top N and Specific modes
  useEffect(() => {
    if (forecastLevel === 'campaign') {
      setCampaignData(null)
    }
  }, [selectionMode, forecastLevel])

  // Fetch available campaigns when in campaign level mode (for count display and selection)
  const channelForCampaigns = selectedChannels.length === 3 ? 'all' : selectedChannels[0] || 'all'
  const { data: campaignsData, isLoading: campaignsLoading } = useQuery({
    queryKey: ['campaigns', channelForCampaigns, minDataPoints],
    queryFn: () => fetchAvailableCampaigns(channelForCampaigns, minDataPoints),
    enabled: forecastLevel === 'campaign' // Always fetch when on campaign level (not just in 'specific' mode)
  })

  const availableCampaigns = campaignsData?.campaigns || []

  // Filter campaigns by search query
  const filteredCampaigns = useMemo(() => {
    if (!campaignSearchQuery) return availableCampaigns
    const query = campaignSearchQuery.toLowerCase()
    return availableCampaigns.filter(camp =>
      camp.campaign_name.toLowerCase().includes(query) ||
      camp.campaign_id.toString().includes(query)
    )
  }, [availableCampaigns, campaignSearchQuery])

  // Get available campaign types based on selected channels
  const availableCampaignTypes = useMemo(() => {
    if (selectedChannels.length === 0) return []

    const types = new Set()
    selectedChannels.forEach(channel => {
      campaignTypesByChannel[channel]?.forEach(type => types.add(type))
    })

    return Array.from(types).sort()
  }, [selectedChannels, campaignTypesByChannel])

  // Auto-select campaign types when channels change
  useEffect(() => {
    if (forecastLevel === 'campaign-type') {
      // Keep only valid campaign types for the selected channels
      const validTypes = selectedCampaignTypes.filter(type => availableCampaignTypes.includes(type))
      if (validTypes.length !== selectedCampaignTypes.length) {
        setSelectedCampaignTypes(validTypes)
      }
      // If no types selected, auto-select some defaults
      if (validTypes.length === 0 && availableCampaignTypes.length > 0) {
        setSelectedCampaignTypes(availableCampaignTypes.slice(0, 3))
      }
    }
  }, [selectedChannels, forecastLevel, availableCampaignTypes])

  const handleGenerate = async () => {
    const params = {
      horizon,
      channels: selectedChannels
    }

    // Add future spends if custom budgets are enabled (applies to all forecast levels)
    if (useCustomBudgets) {
      const spends = {}
      selectedChannels.forEach(channel => {
        const value = parseFloat(futureSpends[channel])
        if (value && value > 0) {
          spends[channel] = value
        }
      })
      if (Object.keys(spends).length > 0) {
        params.future_spends = spends
      }
    }

    setIsLoading(true)
    setProgressState({ step: 'loading', progress: 0, message: 'Starting...' })

    try {
      if (forecastLevel === 'channel') {
        const data = await generateForecastWithSSE(params, setProgressState)
        setForecastData(data)
      } else if (forecastLevel === 'campaign-type') {
        const data = await generateCampaignTypeForecastWithSSE({
          ...params,
          campaign_types: selectedCampaignTypes
        }, setProgressState)
        setCampaignTypeData(data)
      } else if (forecastLevel === 'campaign') {
        const campaignParams = {
          ...params,
          min_data_points: minDataPoints
        }

        if (selectionMode === 'specific') {
          campaignParams.campaign_ids = selectedCampaignIds
        } else {
          campaignParams.top_n = topNCampaigns
        }

        const data = await generateCampaignLevelForecastWithSSE(campaignParams, setProgressState)
        setCampaignData(data)
      }
    } catch (error) {
      console.error('Forecast generation error:', error)
      alert(`Error generating forecast: ${error.message}`)
    } finally {
      setIsLoading(false)
      setProgressState(null)
    }
  }

  const isAnyLoading = isLoading || isLoadingCampaignType || isLoadingCampaign
  const canGenerate = selectedChannels.length > 0 &&
    (forecastLevel !== 'campaign-type' || selectedCampaignTypes.length > 0) &&
    (forecastLevel !== 'campaign' || selectionMode !== 'specific' || selectedCampaignIds.length > 0)

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="container mx-auto px-6 py-12">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-trading-cyan to-trading-blue bg-clip-text text-transparent">
            Revenue Forecasting
          </h1>
          <p className="text-gray-400">
            Generate probabilistic revenue forecasts with AI-powered insights
          </p>
        </motion.div>

        {/* Data Upload Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8"
        >
          <DataUpload onDataUploaded={refreshDataState} />
        </motion.div>

        {/* Configuration Panel */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-effect rounded-2xl p-8 mb-8"
        >
          <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2">
            <Calendar className="w-6 h-6 text-trading-cyan" />
            Forecast Configuration
          </h2>

          {/* Forecast Level Selection */}
          <div className="mb-8">
            <label className="block text-gray-300 mb-3 font-medium">Forecast Level</label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { value: 'channel', label: 'Channel Level', icon: BarChart3, desc: 'Aggregate by channel' },
                { value: 'campaign-type', label: 'Campaign Type', icon: Filter, desc: 'Group by campaign types' },
                { value: 'campaign', label: 'Top Campaigns', icon: TrendingUp, desc: 'Individual campaigns' }
              ].map((level) => (
                <button
                  key={level.value}
                  onClick={() => setForecastLevel(level.value)}
                  className={`px-6 py-4 rounded-xl font-semibold transition-all text-left ${
                    forecastLevel === level.value
                      ? 'bg-gradient-to-r from-trading-purple to-trading-cyan text-white glow-blue'
                      : 'glass-effect text-gray-300 hover:text-white hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-1">
                    <level.icon className="w-5 h-5" />
                    <span>{level.label}</span>
                  </div>
                  <p className="text-xs opacity-80">{level.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left Column: Horizon */}
            <div>
              <label className="block text-gray-300 mb-3 font-medium">Forecast Horizon</label>
              <div className="grid grid-cols-3 gap-3">
                {[30, 60, 90].map((days) => (
                  <button
                    key={days}
                    onClick={() => setHorizon(days)}
                    className={`px-6 py-4 rounded-xl font-semibold transition-all ${
                      horizon === days
                        ? 'bg-gradient-to-r from-trading-blue to-trading-cyan text-white glow-blue'
                        : 'glass-effect text-gray-300 hover:text-white hover:bg-white/10'
                    }`}
                  >
                    {days} Days
                  </button>
                ))}
              </div>
            </div>

            {/* Right Column: Dynamic Filters */}
            <div>
              {/* Channel Selection - Show for all levels */}
              <div className="mb-6">
                <label className="block text-gray-300 mb-3 font-medium">
                  {forecastLevel === 'channel' ? 'Select Channels' : 'Filter by Channel'}
                </label>

                {forecastLevel === 'channel' ? (
                  <div className="space-y-2">
                    {availableChannels.map((channel) => (
                      <label key={channel} className="flex items-center gap-3 glass-effect p-3 rounded-xl cursor-pointer hover:bg-white/10 transition-colors">
                        <input
                          type="checkbox"
                          checked={selectedChannels.includes(channel)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedChannels([...selectedChannels, channel])
                            } else {
                              setSelectedChannels(selectedChannels.filter(c => c !== channel))
                            }
                          }}
                          className="w-5 h-5 accent-trading-cyan"
                        />
                        <span className="text-white font-medium uppercase">{channel}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <select
                    value={selectedChannels.length === availableChannels.length ? 'all' : selectedChannels[0] || 'all'}
                    onChange={(e) => {
                      if (e.target.value === 'all') {
                        setSelectedChannels(availableChannels)
                      } else {
                        setSelectedChannels([e.target.value])
                      }
                    }}
                    className="w-full glass-effect px-4 py-3 rounded-xl text-white bg-transparent border border-gray-700 focus:border-trading-cyan focus:outline-none"
                  >
                    <option value="all" className="bg-trading-darker">All Channels</option>
                    {availableChannels.map(channel => (
                      <option key={channel} value={channel} className="bg-trading-darker">
                        {channel.charAt(0).toUpperCase() + channel.slice(1)} Ads
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Future Budget Inputs - Visible at all forecast levels */}
              {true && (
                <div className="mt-6">
                <div className="flex items-center justify-between mb-3">
                  <label className="block text-gray-300 font-medium">
                    Future Budget (Optional)
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={useCustomBudgets}
                      onChange={(e) => setUseCustomBudgets(e.target.checked)}
                      className="w-4 h-4 accent-trading-cyan"
                    />
                    <span className="text-sm text-gray-400">Use custom budgets</span>
                  </label>
                </div>

                {!useCustomBudgets && (
                  <div className="glass-effect p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 mb-4">
                    <p className="text-xs text-gray-400">
                      <strong className="text-trading-cyan">Using historical averages:</strong> System will use last 30 days average spend per channel. Enable custom budgets to specify future amounts.
                    </p>
                  </div>
                )}

                {useCustomBudgets && (
                  <div className="space-y-3">
                    {availableChannels.map((channel) => (
                      <div key={channel} className="glass-effect p-4 rounded-xl">
                        <label className="block text-sm text-gray-400 mb-2 uppercase font-semibold">
                          {channel} Ads — Total Budget ({horizon} days)
                        </label>
                        <div className="relative">
                          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                          <input
                            type="number"
                            placeholder="e.g., 25000"
                            value={futureSpends[channel]}
                            onChange={(e) => setFutureSpends({
                              ...futureSpends,
                              [channel]: e.target.value
                            })}
                            className="w-full pl-8 pr-4 py-3 bg-trading-darker border border-gray-700 rounded-lg text-white focus:border-trading-cyan focus:outline-none"
                            min="0"
                            step="1000"
                          />
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          Total spend for {horizon} days — leave empty to use historical average
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              )}

              {/* Campaign Type Selection - Only for campaign-type level */}
              {forecastLevel === 'campaign-type' && (
                <div>
                  <label className="block text-gray-300 mb-3 font-medium">
                    Select Campaign Types
                    <span className="text-xs text-gray-500 ml-2">
                      ({availableCampaignTypes.length} available)
                    </span>
                  </label>
                  <div className="glass-effect p-4 rounded-xl max-h-64 overflow-y-auto space-y-2">
                    {availableCampaignTypes.length > 0 ? (
                      availableCampaignTypes.map((type) => (
                        <label key={type} className="flex items-center gap-3 p-2 rounded-lg cursor-pointer hover:bg-white/5 transition-colors">
                          <input
                            type="checkbox"
                            checked={selectedCampaignTypes.includes(type)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedCampaignTypes([...selectedCampaignTypes, type])
                              } else {
                                setSelectedCampaignTypes(selectedCampaignTypes.filter(t => t !== type))
                              }
                            }}
                            className="w-4 h-4 accent-trading-cyan"
                          />
                          <span className="text-white font-medium text-sm">{type}</span>
                        </label>
                      ))
                    ) : (
                      <p className="text-gray-500 text-sm text-center py-4">
                        Select a channel first to see available campaign types
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Campaign Level Filters */}
              {forecastLevel === 'campaign' && (
                <div>
                  <label className="block text-gray-300 mb-3 font-medium">Campaign Filters</label>
                  <div className="space-y-4">
                    {/* Info Box */}
                    <div className="glass-effect p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
                      <p className="text-sm text-gray-300 mb-3">
                        <strong className="text-trading-cyan">Note:</strong> Campaigns need sufficient historical data for accurate forecasting. The minimum requirement ensures model reliability.
                      </p>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="glass-effect p-2 rounded">
                          <span className="text-gray-500">Available:</span>
                          <span className="text-trading-cyan font-semibold ml-1">
                            {campaignsLoading ? (
                              <span className="inline-block animate-pulse">Loading...</span>
                            ) : campaignsData ? (
                              `${campaignsData.total_count} campaigns`
                            ) : (
                              '~105 campaigns'
                            )}
                          </span>
                        </div>
                        <div className="glass-effect p-2 rounded">
                          <span className="text-gray-500">Dataset:</span>
                          <span className="text-trading-cyan font-semibold ml-1">886 days</span>
                        </div>
                      </div>
                    </div>

                    {/* Selection Mode Toggle */}
                    <div>
                      <label className="block text-gray-400 text-sm mb-2">Selection Mode</label>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => setSelectionMode('topN')}
                          className={`px-4 py-2 rounded-xl font-medium text-sm transition-all ${
                            selectionMode === 'topN'
                              ? 'bg-gradient-to-r from-trading-blue to-trading-cyan text-white'
                              : 'glass-effect text-gray-400 hover:text-white'
                          }`}
                        >
                          Top N Campaigns
                        </button>
                        <button
                          onClick={() => setSelectionMode('specific')}
                          className={`px-4 py-2 rounded-xl font-medium text-sm transition-all ${
                            selectionMode === 'specific'
                              ? 'bg-gradient-to-r from-trading-blue to-trading-cyan text-white'
                              : 'glass-effect text-gray-400 hover:text-white'
                          }`}
                        >
                          Select Specific
                        </button>
                      </div>
                    </div>

                    {/* Top N Selector */}
                    {selectionMode === 'topN' && (
                      <div>
                        <label className="block text-gray-400 text-sm mb-2">Show Top N Campaigns</label>
                        <select
                          value={topNCampaigns}
                          onChange={(e) => setTopNCampaigns(Number(e.target.value))}
                          className="w-full glass-effect px-4 py-2 rounded-xl text-white bg-transparent border border-gray-700 focus:border-trading-cyan focus:outline-none"
                        >
                          <option value={10} className="bg-trading-darker">Top 10</option>
                          <option value={20} className="bg-trading-darker">Top 20</option>
                          <option value={30} className="bg-trading-darker">Top 30</option>
                          <option value={50} className="bg-trading-darker">Top 50</option>
                          <option value={0} className="bg-trading-darker">All Campaigns</option>
                        </select>
                      </div>
                    )}

                    {/* Specific Campaign Selector */}
                    {selectionMode === 'specific' && (
                      <div>
                        <label className="block text-gray-400 text-sm mb-2">
                          Select Campaigns
                          <span className="text-xs text-gray-600 ml-2">
                            ({selectedCampaignIds.length} selected)
                          </span>
                        </label>

                        {/* Search Box */}
                        <div className="relative mb-2">
                          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-500" />
                          <input
                            type="text"
                            placeholder="Search campaigns..."
                            value={campaignSearchQuery}
                            onChange={(e) => setCampaignSearchQuery(e.target.value)}
                            className="w-full glass-effect pl-10 pr-4 py-2 rounded-xl text-white bg-transparent border border-gray-700 focus:border-trading-cyan focus:outline-none text-sm"
                          />
                        </div>

                        {/* Campaign List */}
                        <div className="glass-effect p-3 rounded-xl max-h-64 overflow-y-auto space-y-1 custom-scrollbar">
                          {campaignsLoading ? (
                            <p className="text-gray-500 text-sm text-center py-4">Loading campaigns...</p>
                          ) : filteredCampaigns.length > 0 ? (
                            filteredCampaigns.map((campaign) => (
                              <label
                                key={campaign.campaign_id}
                                className="flex items-start gap-3 p-2 rounded-lg cursor-pointer hover:bg-white/5 transition-colors"
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedCampaignIds.includes(campaign.campaign_id)}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setSelectedCampaignIds([...selectedCampaignIds, campaign.campaign_id])
                                    } else {
                                      setSelectedCampaignIds(selectedCampaignIds.filter(id => id !== campaign.campaign_id))
                                    }
                                  }}
                                  className="w-4 h-4 accent-trading-cyan mt-0.5"
                                />
                                <div className="flex-1 min-w-0">
                                  <p className="text-white font-medium text-sm truncate">{campaign.campaign_name}</p>
                                  <div className="flex gap-2 mt-1">
                                    <span className="text-xs px-2 py-0.5 bg-trading-cyan/20 text-trading-cyan rounded-full uppercase">
                                      {campaign.channel}
                                    </span>
                                    <span className="text-xs px-2 py-0.5 bg-trading-purple/20 text-trading-purple rounded-full">
                                      {campaign.campaign_type}
                                    </span>
                                    <span className="text-xs text-gray-500">{campaign.data_points} days</span>
                                  </div>
                                  <p className="text-xs text-gray-500 mt-1">
                                    Revenue: ${(campaign.total_revenue / 1000).toFixed(1)}K | ROAS: {campaign.roas.toFixed(2)}x
                                  </p>
                                </div>
                              </label>
                            ))
                          ) : (
                            <p className="text-gray-500 text-sm text-center py-4">
                              {campaignSearchQuery ? 'No campaigns found matching your search' : 'No campaigns available'}
                            </p>
                          )}
                        </div>

                        {/* Clear Selection */}
                        {selectedCampaignIds.length > 0 && (
                          <button
                            onClick={() => setSelectedCampaignIds([])}
                            className="mt-2 w-full px-3 py-2 glass-effect rounded-xl text-sm text-gray-400 hover:text-white transition-colors flex items-center justify-center gap-2"
                          >
                            <X className="w-4 h-4" />
                            Clear Selection ({selectedCampaignIds.length})
                          </button>
                        )}
                      </div>
                    )}

                    {/* Min Data Points */}
                    <div>
                      <label className="block text-gray-400 text-sm mb-2">
                        Minimum Historical Data (Days)
                        <span className="text-xs text-gray-600 ml-2">Required for model training</span>
                      </label>
                      <select
                        value={minDataPoints}
                        onChange={(e) => setMinDataPoints(Number(e.target.value))}
                        className="w-full glass-effect px-4 py-2 rounded-xl text-white bg-transparent border border-gray-700 focus:border-trading-cyan focus:outline-none"
                      >
                        <option value={20} className="bg-trading-darker">20 days (Recommended)</option>
                        <option value={30} className="bg-trading-darker">30 days</option>
                        <option value={60} className="bg-trading-darker">60 days</option>
                        <option value={90} className="bg-trading-darker">90 days</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Generate Button */}
          <button
            onClick={handleGenerate}
            disabled={isAnyLoading || !canGenerate}
            className="mt-8 w-full md:w-auto px-8 py-4 bg-gradient-to-r from-trading-blue to-trading-cyan rounded-xl font-semibold flex items-center justify-center gap-2 hover:scale-105 transition-transform glow-blue disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            {isAnyLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                <div className="flex flex-col items-start ml-3">
                  <span>Generating Forecast...</span>
                  <span className="text-xs opacity-80">
                    {forecastLevel === 'campaign'
                      ? `Processing ${selectionMode === 'specific' ? selectedCampaignIds.length : topNCampaigns} campaigns • ~${Math.ceil((selectionMode === 'specific' ? selectedCampaignIds.length : topNCampaigns) * 0.5)}s`
                      : 'This may take 10-15 seconds'}
                  </span>
                </div>
              </>
            ) : (
              <>
                <Zap className="w-5 h-5" />
                Generate Forecast
              </>
            )}
          </button>

          {!canGenerate && !isAnyLoading && (
            <p className="mt-3 text-sm text-yellow-500 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {selectedChannels.length === 0
                ? 'Please select at least one channel'
                : forecastLevel === 'campaign-type'
                ? 'Please select at least one campaign type'
                : selectionMode === 'specific'
                ? 'Please select at least one campaign'
                : 'Invalid selection'}
            </p>
          )}
        </motion.div>

        {/* Inline Progress - Shows when loading */}
        <ForecastProgress
          isVisible={isAnyLoading}
          forecastLevel={forecastLevel}
          campaignCount={
            forecastLevel === 'campaign'
              ? selectionMode === 'specific'
                ? selectedCampaignIds.length
                : topNCampaigns === 0
                ? campaignsData?.total_count || 105
                : topNCampaigns
              : 0
          }
          progressState={progressState}
        />

        {/* Forecast Results - Shows after loading completes */}
        <AnimatePresence mode="wait">
          {/* Channel-Level Results */}
          {forecastData && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-8"
            >
              {/* Aggregate Period Bar Chart — per channel */}
              <AggregateForecastChart
                horizon={horizon}
                title={`Channel Revenue Forecast (${horizon}-Day Period)`}
                items={Object.entries(forecastData.forecast.channels).map(([channel, data]) => ({
                  name: channel.charAt(0).toUpperCase() + channel.slice(1),
                  channel,
                  expected: data.summary.total_revenue,
                  lower: data.summary.lower_bound,
                  upper: data.summary.upper_bound,
                }))}
              />

              {/* Aggregate Forecast */}
              <div className="glass-effect rounded-2xl p-8">
                <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2">
                  <TrendingUp className="w-6 h-6 text-trading-green" />
                  Aggregate Forecast ({horizon} Days)
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  <div className="glass-effect p-6 rounded-xl border-2 border-trading-green/30">
                    <p className="text-gray-400 text-sm mb-2">Predicted Revenue</p>
                    <p className="text-3xl font-bold text-white">
                      ${(forecastData.forecast.aggregate.total_revenue / 1000).toFixed(1)}K
                    </p>
                  </div>
                  <div className="glass-effect p-6 rounded-xl">
                    <p className="text-gray-400 text-sm mb-2">Lower Bound (10%)</p>
                    <p className="text-2xl font-semibold text-trading-cyan">
                      ${(forecastData.forecast.aggregate.lower_bound / 1000).toFixed(1)}K
                    </p>
                  </div>
                  <div className="glass-effect p-6 rounded-xl">
                    <p className="text-gray-400 text-sm mb-2">Upper Bound (90%)</p>
                    <p className="text-2xl font-semibold text-trading-purple">
                      ${(forecastData.forecast.aggregate.upper_bound / 1000).toFixed(1)}K
                    </p>
                  </div>
                </div>

                {forecastData.forecast.aggregate.blended_roas && (
                  <div className="glass-effect p-6 rounded-xl bg-gradient-to-r from-trading-green/10 to-trading-cyan/10">
                    <p className="text-gray-400 text-sm mb-2">Predicted Blended ROAS</p>
                    <p className="text-4xl font-bold text-trading-green">
                      {forecastData.forecast.aggregate.blended_roas.toFixed(2)}x
                    </p>
                  </div>
                )}
              </div>

              {/* Channel-Level Forecasts */}
              {Object.entries(forecastData.forecast.channels).map(([channel, data]) => (
                <div key={channel} className="glass-effect rounded-2xl p-8">
                  <h3 className="text-xl font-semibold mb-6 uppercase text-trading-cyan">{channel} Forecast</h3>

                  {/* Revenue Range */}
                  <div className="mb-6">
                    <p className="text-gray-400 text-sm mb-3 font-medium">Revenue Forecast (Probabilistic Range)</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="glass-effect p-4 rounded-xl">
                        <p className="text-gray-400 text-xs mb-1">Lower Bound (10%)</p>
                        <p className="text-xl font-semibold text-trading-cyan">
                          ${(data.summary.lower_bound / 1000).toFixed(1)}K
                        </p>
                      </div>
                      <div className="glass-effect p-4 rounded-xl border-2 border-trading-green/30">
                        <p className="text-gray-400 text-xs mb-1">Expected Revenue</p>
                        <p className="text-2xl font-bold text-white">
                          ${(data.summary.total_revenue / 1000).toFixed(1)}K
                        </p>
                      </div>
                      <div className="glass-effect p-4 rounded-xl">
                        <p className="text-gray-400 text-xs mb-1">Upper Bound (90%)</p>
                        <p className="text-xl font-semibold text-trading-purple">
                          ${(data.summary.upper_bound / 1000).toFixed(1)}K
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Budget / Spend */}
                  {data.summary.budget_used != null && (
                    <div className="mb-6">
                      <p className="text-gray-400 text-sm mb-3 font-medium">Budget / Spend</p>
                      <div className="glass-effect p-4 rounded-xl flex items-center justify-between">
                        <div>
                          <p className="text-gray-400 text-xs mb-1">Total Spend ({horizon} days)</p>
                          <p className="text-2xl font-bold text-white">
                            ${(data.summary.budget_used / 1000).toFixed(1)}K
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            ${(data.summary.budget_used / horizon).toFixed(0)}/day avg
                          </p>
                        </div>
                        <span className={`text-xs px-3 py-1.5 rounded-full font-medium ${
                          data.summary.custom_spend
                            ? 'bg-trading-cyan/20 text-trading-cyan'
                            : 'bg-gray-700/50 text-gray-400'
                        }`}>
                          {data.summary.custom_spend ? 'Custom Budget' : 'Historical Avg'}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* ROAS Range */}
                  <div className="mb-6">
                    <p className="text-gray-400 text-sm mb-3 font-medium">ROAS Forecast (Probabilistic Range)</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="glass-effect p-4 rounded-xl">
                        <p className="text-gray-400 text-xs mb-1">Lower ROAS (10%)</p>
                        <p className="text-xl font-semibold text-trading-cyan">
                          {data.summary.roas_lower?.toFixed(2) || 'N/A'}x
                        </p>
                      </div>
                      <div className="glass-effect p-4 rounded-xl border-2 border-trading-green/30">
                        <p className="text-gray-400 text-xs mb-1">Expected ROAS</p>
                        <p className="text-2xl font-bold text-trading-green">
                          {data.summary.roas_expected?.toFixed(2) || 'N/A'}x
                        </p>
                      </div>
                      <div className="glass-effect p-4 rounded-xl">
                        <p className="text-gray-400 text-xs mb-1">Upper ROAS (90%)</p>
                        <p className="text-xl font-semibold text-trading-purple">
                          {data.summary.roas_upper?.toFixed(2) || 'N/A'}x
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {/* Executive AI Summary - Display at bottom after all data */}
              {forecastData.forecast.ai_executive_summary && (
                <div className="glass-effect rounded-2xl p-8 bg-gradient-to-br from-trading-blue/5 to-trading-cyan/5 border-2 border-trading-cyan/30">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-xl bg-trading-cyan/20">
                      <Zap className="w-7 h-7 text-trading-cyan" />
                    </div>
                    <div className="flex-1">
                      <h2 className="text-2xl font-semibold mb-4 text-trading-cyan">📊 Executive AI Analysis</h2>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <MarkdownRenderer content={forecastData.forecast.ai_executive_summary} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </motion.div>
          )}

          {/* Campaign-Type Level Results */}
          {campaignTypeData && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-8"
            >
              {/* Aggregate Period Bar Chart — per campaign type */}
              <AggregateForecastChart
                horizon={horizon}
                title={`Campaign Type Revenue Forecast (${horizon}-Day Period)`}
                items={Object.entries(campaignTypeData.forecast.campaign_types).flatMap(([channel, types]) =>
                  Object.entries(types).map(([ctype, data]) => ({
                    name: `${channel.charAt(0).toUpperCase() + channel.slice(1)} · ${ctype}`,
                    channel,
                    expected: data.summary.total_revenue,
                    lower: data.summary.lower_bound,
                    upper: data.summary.upper_bound,
                  }))
                )}
              />

              <div className="glass-effect rounded-2xl p-8">
                <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2">
                  <TrendingUp className="w-6 h-6 text-trading-purple" />
                  Campaign Type Forecasts ({horizon} Days)
                </h2>

                {Object.entries(campaignTypeData.forecast.campaign_types).map(([channel, types]) => (
                  <div key={channel} className="mb-8 last:mb-0">
                    <h3 className="text-xl font-semibold mb-4 uppercase text-trading-cyan flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-trading-cyan"></span>
                      {channel}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {Object.entries(types).map(([type, data]) => (
                        <div key={type} className="glass-effect p-5 rounded-xl hover:scale-105 transition-transform border border-gray-700/50 hover:border-trading-cyan/50">
                          <h4 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">{type}</h4>
                          <div className="space-y-3">
                            <div>
                              <p className="text-xs text-gray-500 mb-1">Revenue Range</p>
                              <p className="text-lg font-bold text-white">
                                ${(data.summary.lower_bound / 1000).toFixed(1)}K - ${(data.summary.upper_bound / 1000).toFixed(1)}K
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500 mb-1">Expected Revenue</p>
                              <p className="text-xl font-bold text-trading-cyan">
                                ${(data.summary.total_revenue / 1000).toFixed(1)}K
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500 mb-1">ROAS Range</p>
                              <p className="text-base font-semibold text-trading-green">
                                {data.summary.roas_lower?.toFixed(2) || 'N/A'}x - {data.summary.roas_upper?.toFixed(2) || 'N/A'}x
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Executive AI Summary - Display at bottom after all data */}
              {campaignTypeData.forecast.ai_executive_summary && (
                <div className="glass-effect rounded-2xl p-8 bg-gradient-to-br from-trading-blue/5 to-trading-purple/5 border-2 border-trading-purple/30">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-xl bg-trading-purple/20">
                      <Zap className="w-7 h-7 text-trading-purple" />
                    </div>
                    <div className="flex-1">
                      <h2 className="text-2xl font-semibold mb-4 text-trading-purple">📊 Executive AI Analysis</h2>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <MarkdownRenderer content={campaignTypeData.forecast.ai_executive_summary} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </motion.div>
          )}

          {/* Campaign-Level Results */}
          {campaignData && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-8"
            >
              {/* Aggregate Period Bar Chart — top 10 campaigns by expected revenue */}
              <AggregateForecastChart
                horizon={horizon}
                title={`Top Campaign Revenue Forecast (${horizon}-Day Period)`}
                items={campaignData.forecast.campaigns.slice(0, 10).map(c => ({
                  name: c.campaign_name.length > 22
                    ? c.campaign_name.slice(0, 20) + '…'
                    : c.campaign_name,
                  channel: c.channel,
                  expected: c.forecast.total_revenue,
                  lower: c.forecast.lower_bound,
                  upper: c.forecast.upper_bound,
                }))}
              />

              <div className="glass-effect rounded-2xl p-8">
                <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2">
                  <TrendingUp className="w-6 h-6 text-trading-green" />
                  Campaign-Level Forecasts ({campaignData.forecast.total_campaigns} Campaigns, {horizon} Days)
                </h2>

                <div className="mb-4 glass-effect p-3 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <p className="text-sm text-gray-300">
                    {selectionMode === 'topN'
                      ? `Showing top ${topNCampaigns === 0 ? 'all' : topNCampaigns} campaigns with at least ${minDataPoints} days of historical data, ranked by predicted revenue.`
                      : `Showing ${selectedCampaignIds.length} selected campaigns with at least ${minDataPoints} days of historical data.`
                    }
                    <span className="block mt-1 text-xs text-trading-cyan">
                      💡 Executive AI portfolio analysis provided above
                    </span>
                  </p>
                </div>

                <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
                  {campaignData.forecast.campaigns.map((campaign, idx) => (
                    <div key={campaign.campaign_id} className="glass-effect p-6 rounded-xl hover:bg-white/5 transition-colors border border-gray-700/30">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-white mb-2">{campaign.campaign_name}</h3>
                          <div className="flex gap-2 flex-wrap">
                            <span className="text-xs px-3 py-1 bg-trading-cyan/20 text-trading-cyan rounded-full uppercase font-medium">
                              {campaign.channel}
                            </span>
                            <span className="text-xs px-3 py-1 bg-trading-purple/20 text-trading-purple rounded-full uppercase font-medium">
                              {campaign.campaign_type}
                            </span>
                          </div>
                        </div>
                        <span className="text-2xl font-bold text-gray-500">#{idx + 1}</span>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Expected Revenue</p>
                          <p className="text-xl font-bold text-white">
                            ${(campaign.forecast.total_revenue / 1000).toFixed(1)}K
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Revenue Range</p>
                          <p className="text-sm font-semibold text-trading-cyan">
                            ${(campaign.forecast.lower_bound / 1000).toFixed(1)}K - ${(campaign.forecast.upper_bound / 1000).toFixed(1)}K
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Expected ROAS</p>
                          <p className="text-xl font-bold text-trading-green">
                            {campaign.forecast.roas_expected?.toFixed(2) || 'N/A'}x
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-1">ROAS Range</p>
                          <p className="text-sm font-semibold text-trading-purple">
                            {campaign.forecast.roas_lower?.toFixed(2) || 'N/A'}x - {campaign.forecast.roas_upper?.toFixed(2) || 'N/A'}x
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Executive AI Summary - Display at bottom after all data */}
              {campaignData.forecast.ai_executive_summary && (
                <div className="glass-effect rounded-2xl p-8 bg-gradient-to-br from-trading-blue/5 to-trading-green/5 border-2 border-trading-green/30">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-xl bg-trading-green/20">
                      <Zap className="w-7 h-7 text-trading-green" />
                    </div>
                    <div className="flex-1">
                      <h2 className="text-2xl font-semibold mb-4 text-trading-green">📊 Executive AI Analysis</h2>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <MarkdownRenderer content={campaignData.forecast.ai_executive_summary} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(6, 182, 212, 0.5);
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(6, 182, 212, 0.7);
        }
      `}</style>
    </div>
  )
}

export default Forecast
