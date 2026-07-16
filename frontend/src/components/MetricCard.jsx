import React from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown } from 'lucide-react'

const MetricCard = ({ title, value, change, positive, icon, loading }) => {
  if (loading) {
    return (
      <div className="glass-effect rounded-2xl p-6 animate-pulse">
        <div className="h-6 bg-white/10 rounded w-2/3 mb-4"></div>
        <div className="h-10 bg-white/10 rounded w-1/2"></div>
      </div>
    )
  }

  return (
    <motion.div
      className="glass-effect rounded-2xl p-6 hover:scale-105 transition-transform cursor-pointer"
      whileHover={{ y: -5 }}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="text-gray-400 text-sm font-medium mb-2">{title}</p>
          <h3 className="text-4xl font-bold text-white mb-2">{value}</h3>
          <div className={`flex items-center gap-1 text-sm ${positive ? 'text-trading-green' : 'text-trading-red'}`}>
            {positive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            <span className="font-medium">{change}</span>
          </div>
        </div>
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
          positive ? 'bg-trading-green/20 text-trading-green' : 'bg-trading-red/20 text-trading-red'
        }`}>
          {icon}
        </div>
      </div>
    </motion.div>
  )
}

export default MetricCard
