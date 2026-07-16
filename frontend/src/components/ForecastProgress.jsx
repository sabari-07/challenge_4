import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Database, Brain, TrendingUp, CheckCircle, Loader2, Target, LineChart } from 'lucide-react'

const FORECAST_STEP_CONFIG = {
  loading:     { label: 'Loading Data',           icon: Database },
  training:    { label: 'Training Models',         icon: TrendingUp },
  forecasting: { label: 'Generating Forecasts',    icon: Zap },
  ai_insights: { label: 'Generating AI Insights',  icon: Brain },
}

const BUDGET_STEP_CONFIG = {
  loading:     { label: 'Loading Channel Data',    icon: Database },
  fitting:     { label: 'Fitting Spend Curves',    icon: LineChart },
  optimizing:  { label: 'Running Optimisation',    icon: Target },
  ai_insights: { label: 'AI Budget Analysis',      icon: Brain },
}

const ForecastProgress = ({ isVisible, forecastLevel, campaignCount = 0, progressState, mode = 'forecast', title }) => {
  const stepConfig = mode === 'budget' ? BUDGET_STEP_CONFIG : FORECAST_STEP_CONFIG

  const currentStep = progressState?.step || 'loading'
  const currentProgress = progressState?.progress || 0
  const currentMessage = progressState?.message || 'Starting...'
  const currentItem = progressState?.current || ''
  const currentCount = progressState?.count || ''

  const steps = Object.keys(stepConfig)

  // Calculate overall progress (0-100)
  const calculateOverallProgress = () => {
    if (!progressState) return 0

    const stepIndex = steps.indexOf(currentStep)
    if (stepIndex === -1) return 0

    // Each step is 25% of total progress
    const baseProgress = (stepIndex / steps.length) * 100
    const stepProgress = (currentProgress / 100) * (100 / steps.length)

    return Math.min(100, baseProgress + stepProgress)
  }

  const overallProgress = calculateOverallProgress()

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="glass-effect rounded-2xl p-8 mb-8"
        >
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="flex-shrink-0"
            >
              <Zap className="w-10 h-10 text-trading-cyan" />
            </motion.div>
            <div className="flex-1">
              <h3 className="text-xl font-bold text-white mb-1">
                {title || (mode === 'budget' ? 'Optimizing Budget' : 'Generating Forecast')}
              </h3>
              <p className="text-gray-400 text-sm">
                {currentMessage}
              </p>
              {currentItem && (
                <p className="text-trading-cyan text-xs mt-1">
                  {currentItem} {currentCount && `(${currentCount})`}
                </p>
              )}
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-trading-cyan">{Math.round(overallProgress)}%</p>
              <p className="text-xs text-gray-500">Overall</p>
            </div>
          </div>

          {/* Progress Steps */}
          <div className="space-y-3 mb-6">
            {steps.map((stepKey) => {
              const stepInfo = stepConfig[stepKey]
              const isCurrentStep = currentStep === stepKey
              const currentStepIndex = steps.indexOf(currentStep)
              const thisStepIndex = steps.indexOf(stepKey)
              const isCompleted = thisStepIndex < currentStepIndex || (isCurrentStep && currentProgress === 100)
              const isActive = isCurrentStep && currentProgress < 100

              return (
                <ProcessStep
                  key={stepKey}
                  step={stepInfo}
                  isActive={isActive}
                  isCompleted={isCompleted}
                  progress={isCurrentStep ? currentProgress : (isCompleted ? 100 : 0)}
                />
              )
            })}
          </div>

          {/* Overall Progress Bar */}
          <div>
            <div className="flex justify-between text-xs text-gray-400 mb-2">
              <span>Overall Progress</span>
              <span>{Math.round(overallProgress)}%</span>
            </div>
            <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: '0%' }}
                animate={{ width: `${overallProgress}%` }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className="h-full bg-gradient-to-r from-trading-blue via-trading-cyan to-trading-purple"
              />
            </div>
          </div>

          {/* Tip */}
          {forecastLevel === 'campaign' && campaignCount > 20 && (
            <div className="mt-4 glass-effect p-3 rounded-xl bg-blue-500/10 border border-blue-500/20">
              <p className="text-xs text-gray-400 text-center">
                💡 Tip: Fewer campaigns = faster forecasts. Try "Top 10" for quick results!
              </p>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

const ProcessStep = ({ step, isActive, isCompleted, progress }) => {
  const Icon = step.icon

  return (
    <div className="flex items-center gap-3 p-3 glass-effect rounded-xl">
      {/* Icon */}
      <motion.div
        animate={isActive ? {
          scale: [1, 1.1, 1],
          opacity: [0.7, 1, 0.7]
        } : {}}
        transition={isActive ? {
          duration: 1.5,
          repeat: Infinity,
          ease: "easeInOut"
        } : {}}
        className="flex-shrink-0"
      >
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
          isCompleted
            ? 'bg-trading-green/20'
            : isActive
            ? 'bg-trading-cyan/20'
            : 'bg-gray-700/50'
        }`}>
          {isCompleted ? (
            <CheckCircle className="w-5 h-5 text-trading-green" />
          ) : isActive ? (
            <Loader2 className="w-5 h-5 text-trading-cyan animate-spin" />
          ) : (
            <Icon className="w-5 h-5 text-gray-500" />
          )}
        </div>
      </motion.div>

      {/* Step Info */}
      <div className="flex-1">
        <p className={`font-medium text-sm ${
          isCompleted ? 'text-trading-green' : isActive ? 'text-white' : 'text-gray-500'
        }`}>
          {step.label}
        </p>
        <div className="h-1.5 bg-gray-700/50 rounded-full mt-1.5 overflow-hidden">
          <motion.div
            initial={{ width: '0%' }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className={`h-full ${
              isCompleted
                ? 'bg-trading-green'
                : isActive
                ? 'bg-trading-cyan'
                : 'bg-gray-700'
            }`}
          />
        </div>
      </div>

      {/* Status Icon */}
      {isCompleted && (
        <motion.div
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
        >
          <CheckCircle className="w-5 h-5 text-trading-green" />
        </motion.div>
      )}
    </div>
  )
}

export default ForecastProgress
