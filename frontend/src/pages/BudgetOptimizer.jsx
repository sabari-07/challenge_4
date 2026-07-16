import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Target, DollarSign, Zap, PieChart } from 'lucide-react'
import axios from 'axios'
import Navbar from '../components/Navbar'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ForecastProgress from '../components/ForecastProgress'

const BudgetOptimizer = () => {
  const [totalBudget, setTotalBudget] = useState(50000)
  const [minRoas, setMinRoas] = useState(2.0)
  const [availableChannels, setAvailableChannels] = useState(['google', 'bing', 'meta'])
  const [isLoading, setIsLoading] = useState(false)
  const [progressState, setProgressState] = useState(null)
  const [optimizationData, setOptimizationData] = useState(null)

  useEffect(() => {
    axios.get('/api/data-status').then(res => {
      if (res.data.success && res.data.metadata?.channels) {
        setAvailableChannels(res.data.metadata.channels.map(ch => ch.toLowerCase()))
      }
    }).catch(() => {})
  }, [])

  const handleOptimize = async () => {
    setIsLoading(true)
    setOptimizationData(null)
    setProgressState({ step: 'loading', progress: 0, message: 'Starting...' })

    try {
      const response = await fetch('/api/budget/optimize-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          total_budget: totalBudget,
          channels: availableChannels,
          min_roas: minRoas > 0 ? minRoas : null
        })
      })

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
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.substring(6))
            if (event.step === 'complete') {
              setOptimizationData(event.data)
              setProgressState(null)
            } else if (event.step === 'error') {
              throw new Error(event.message)
            } else {
              setProgressState(event)
            }
          } catch (err) {
            throw err
          }
        }
      }
    } catch (error) {
      console.error('Optimisation error:', error)
      alert(`Error: ${error.message}`)
    } finally {
      setIsLoading(false)
      setProgressState(null)
    }
  }

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="container mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-trading-purple to-trading-cyan bg-clip-text text-transparent">
            Budget Optimizer
          </h1>
          <p className="text-gray-400">
            AI-powered budget allocation to maximize revenue and ROAS
          </p>
        </motion.div>

        {/* Configuration */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-effect rounded-2xl p-8 mb-8"
        >
          <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2">
            <DollarSign className="w-6 h-6 text-trading-green" />
            Optimization Parameters
          </h2>

          <div className="space-y-6">
            {/* Total Budget */}
            <div>
              <label className="block text-gray-300 mb-3 font-medium">
                Total Budget: ${totalBudget.toLocaleString()}
              </label>
              <input
                type="range"
                min="10000"
                max="200000"
                step="5000"
                value={totalBudget}
                onChange={(e) => setTotalBudget(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-trading-cyan"
              />
              <div className="flex justify-between text-sm text-gray-500 mt-2">
                <span>$10K</span>
                <span>$200K</span>
              </div>
            </div>

            {/* Min ROAS */}
            <div>
              <label className="block text-gray-300 mb-3 font-medium">
                Minimum ROAS: {minRoas > 0 ? `${minRoas.toFixed(1)}x` : <span className="text-gray-500 font-normal">No constraint <span className="text-xs">(Optional)</span></span>}
              </label>
              <input
                type="range"
                min="0"
                max="5"
                step="0.1"
                value={minRoas}
                onChange={(e) => setMinRoas(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-trading-purple"
              />
              <div className="flex justify-between text-sm text-gray-500 mt-2">
                <span>No minimum <span className="text-xs text-gray-600">(optional)</span></span>
                <span>5.0x</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleOptimize}
            disabled={isLoading}
            className="mt-8 px-8 py-4 bg-gradient-to-r from-trading-purple to-trading-cyan rounded-xl font-semibold flex items-center gap-2 hover:scale-105 transition-transform glow-blue disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Optimizing...
              </>
            ) : (
              <>
                <Target className="w-5 h-5" />
                Optimize Allocation
              </>
            )}
          </button>
        </motion.div>

        {/* Progress */}
        <ForecastProgress
          isVisible={isLoading}
          mode="budget"
          progressState={progressState}
        />

        {/* Results */}
        {optimizationData && !isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            {/* Summary */}
            <div className="glass-effect rounded-2xl p-8">
              <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2">
                <PieChart className="w-6 h-6 text-trading-cyan" />
                Optimal Allocation
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="glass-effect p-6 rounded-xl">
                  <p className="text-gray-400 text-sm mb-2">Total Budget</p>
                  <p className="text-3xl font-bold text-white">
                    ${optimizationData.optimization.total_budget.toLocaleString()}
                  </p>
                </div>
                <div className="glass-effect p-6 rounded-xl">
                  <p className="text-gray-400 text-sm mb-2">Predicted Revenue</p>
                  <p className="text-3xl font-bold text-trading-green">
                    ${(optimizationData.optimization.total_predicted_revenue / 1000).toFixed(1)}K
                  </p>
                </div>
                <div className="glass-effect p-6 rounded-xl">
                  <p className="text-gray-400 text-sm mb-2">Blended ROAS</p>
                  <p className="text-3xl font-bold text-trading-cyan">
                    {optimizationData.optimization.blended_roas.toFixed(2)}x
                  </p>
                </div>
              </div>

              {/* Channel Allocations */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {Object.entries(optimizationData.optimization.allocation).map(([channel, data]) => (
                  <motion.div
                    key={channel}
                    className="glass-effect p-6 rounded-xl hover:scale-105 transition-transform"
                    whileHover={{ y: -5 }}
                  >
                    <h3 className="text-lg font-semibold uppercase mb-4 text-trading-cyan">
                      {channel}
                    </h3>
                    <div className="space-y-3">
                      <div>
                        <p className="text-gray-400 text-xs mb-1">Allocated Budget</p>
                        <p className="text-2xl font-bold text-white">
                          ${(data.spend / 1000).toFixed(1)}K
                        </p>
                        <p className="text-sm text-gray-500">
                          {data.percentage.toFixed(1)}% of total
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-400 text-xs mb-1">Expected Revenue</p>
                        <p className="text-xl font-semibold text-trading-green">
                          ${(data.predicted_revenue / 1000).toFixed(1)}K
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-400 text-xs mb-1">ROAS</p>
                        <p className="text-xl font-semibold text-trading-purple">
                          {data.roas.toFixed(2)}x
                        </p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* AI Recommendation */}
            {optimizationData.ai_recommendation && (
              <div className="glass-effect p-8 rounded-2xl bg-gradient-to-r from-trading-blue/10 to-trading-purple/10 border-l-4 border-trading-purple">
                <div className="flex items-start gap-3">
                  <Zap className="w-6 h-6 text-trading-purple flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <h3 className="text-xl font-semibold text-trading-purple mb-3">
                      AI Recommendation
                    </h3>
                    <MarkdownRenderer content={optimizationData.ai_recommendation} />
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  )
}

export default BudgetOptimizer
