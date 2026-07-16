import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BarChart3, TrendingUp, Target, Megaphone } from 'lucide-react'

const Navbar = () => {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <BarChart3 className="w-5 h-5" /> },
    { path: '/forecast', label: 'Forecast', icon: <TrendingUp className="w-5 h-5" /> },
    { path: '/budget-optimizer', label: 'Budget Optimizer', icon: <Target className="w-5 h-5" /> },
  ]

  return (
    <nav className="sticky top-0 z-50 glass-effect-strong border-b border-white/10">
      <div className="container mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <motion.div
              className="w-10 h-10 rounded-xl bg-gradient-to-br from-trading-blue to-trading-cyan flex items-center justify-center glow-blue"
              whileHover={{ scale: 1.05, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              <Megaphone className="text-white w-6 h-6" />
            </motion.div>
            <span className="text-2xl font-bold bg-gradient-to-r from-trading-cyan to-trading-blue bg-clip-text text-transparent">
              RevenueIQ
            </span>
          </Link>

          {/* Nav Items */}
          <div className="flex items-center gap-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Link key={item.path} to={item.path}>
                  <motion.div
                    className={`px-6 py-2 rounded-lg flex items-center gap-2 transition-all ${
                      isActive
                        ? 'bg-gradient-to-r from-trading-blue to-trading-cyan text-white glow-blue'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    }`}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    {item.icon}
                    <span className="font-medium">{item.label}</span>
                  </motion.div>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
