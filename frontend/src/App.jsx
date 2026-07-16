import React, { Suspense, lazy, Component } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { motion } from 'framer-motion'
import Scene3D from './components/Scene3D'

class Scene3DErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { crashed: false }
  }
  static getDerivedStateFromError() {
    return { crashed: true }
  }
  render() {
    if (this.state.crashed) return null
    return this.props.children
  }
}

// Lazy load pages
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Forecast = lazy(() => import('./pages/Forecast'))
const BudgetOptimizer = lazy(() => import('./pages/BudgetOptimizer'))

// Loading component
const LoadingScreen = () => (
  <div className="min-h-screen flex items-center justify-center bg-trading-darker">
    <motion.div
      className="flex flex-col items-center space-y-4"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="relative">
        <div className="w-16 h-16 border-4 border-trading-blue border-t-transparent rounded-full animate-spin"></div>
        <div className="absolute inset-0 w-16 h-16 border-4 border-trading-cyan border-b-transparent rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1s' }}></div>
      </div>
      <h2 className="text-2xl font-bold bg-gradient-to-r from-trading-blue to-trading-cyan bg-clip-text text-transparent">
        RevenueIQ
      </h2>
      <p className="text-gray-400 text-sm">Loading forecasting engine...</p>
    </motion.div>
  </div>
)

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-trading-darker grid-background">
        {/* Fixed 3D Background Scene - Visible on all pages */}
        <div className="fixed inset-0 z-0 pointer-events-none">
          <Scene3DErrorBoundary>
            <Scene3D />
          </Scene3DErrorBoundary>
        </div>

        {/* Main Content - Above 3D Scene */}
        <div className="relative z-10">
          <Suspense fallback={<LoadingScreen />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/forecast" element={<Forecast />} />
              <Route path="/budget-optimizer" element={<BudgetOptimizer />} />
            </Routes>
          </Suspense>
        </div>
      </div>
    </Router>
  )
}

export default App
