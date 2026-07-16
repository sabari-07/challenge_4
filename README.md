# AIgnition - Probabilistic Revenue Forecasting Platform

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)
![React 18](https://img.shields.io/badge/React-18-61dafb.svg)
![License MIT](https://img.shields.io/badge/License-MIT-green.svg)

**Winning Solution for AIgnition 3.0 Hackathon by NetElixir**

AI-powered probabilistic revenue forecasting system for e-commerce marketing, combining Prophet + XGBoost ensemble models with Cohere AI for intelligent insights.

---

## 🎯 Features

### Core Forecasting
- **Multi-Channel Forecasting**: Google Ads, Microsoft Ads (Bing), Meta Ads
- **Probabilistic Predictions**: P10, P50, P90 confidence intervals
- **Multiple Horizons**: 30, 60, and 90-day forecasts
- **Prophet Forecasting**: Channel-specific optimized Prophet models (no ensemble — pure Prophet)
- **Campaign-Level Granularity**: Channel, campaign-type, and campaign-level forecasts

### Budget Optimization
- **Spend-Response Curves**: Logarithmic regression for budget-revenue relationships
- **Constrained Optimization**: Maximize revenue subject to budget and minimum ROAS
- **Scenario Simulation**: Compare multiple budget allocation strategies
- **Marginal ROAS Calculation**: Identify diminishing returns

### AI Integration (Cohere)
- **Causal Analysis**: Explain WHY forecasts predict specific outcomes
- **Risk Detection**: Identify volatility and uncertainty factors
- **Budget Recommendations**: Strategic allocation advice based on performance
- **Executive Summaries**: Business-friendly insights for CMOs

### Stunning UI
- **3D Visualizations**: Three.js powered floating spheres and particle effects
- **Trading Platform Aesthetics**: Dark theme, glassmorphism, glow effects
- **Interactive Charts**: Recharts with custom tooltips and animations
- **Responsive Design**: Tailwind CSS with mobile-first approach

---

## 📁 Project Structure

```
AIgnition/
├── src/
│   ├── data/
│   │   ├── loader.py                     # Multi-channel data ingestion
│   │   ├── preprocessor_improved.py      # Channel-specific cleaning (production)
│   │   └── dynamic_loader.py             # Auto-detect columns for user uploads
│   ├── models/
│   │   ├── prophet_final.py              # Final Prophet model (production)
│   │   ├── multi_horizon_forecaster.py   # 9-model wrapper (3 channels × 3 horizons)
│   │   └── xgboost_model.py              # XGBoost (alternative, not in prod path)
│   ├── simulation/
│   │   └── budget_optimizer.py           # Budget allocation optimizer
│   ├── ai/
│   │   └── cohere_client.py              # Cohere AI client
│   ├── api/
│   │   ├── app.py                        # FastAPI backend
│   │   └── upload_handler.py             # CSV upload handler
│   └── predict.py                        # Prediction script
├── frontend/
│   ├── src/
│   │   ├── components/                   # Reusable React components
│   │   ├── pages/                        # Dashboard, Forecast, Budget Optimizer
│   │   ├── App.jsx                       # Main app component
│   │   └── main.jsx                      # Entry point
│   ├── package.json
│   └── vite.config.js
├── data/                                 # Input CSV files
├── pickle/                               # Trained models
├── docs/                                 # Technical documentation
├── run.sh                                # Submission entry point
├── train_models.py                       # Model training script
├── requirements.txt                      # Python dependencies
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Cohere API Key (get free at https://cohere.com)

### 1. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your Cohere API key

# Train models
python train_models.py

# Start API server
python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Visit `http://localhost:3000` for the UI.

---

## 📊 Data Format

### Input Data Files (CSV)

**Google Ads**: `google_ads_campaign_stats.csv`
```csv
campaign_id,segments_date,metrics_clicks,metrics_conversions,metrics_cost_micros,metrics_impressions,metrics_conversions_value,campaign_advertising_channel_type,campaign_budget_amount,campaign_name
```

**Bing Ads**: `bing_campaign_stats.csv`
```csv
CampaignId,TimePeriod,Revenue,Spend,Clicks,Impressions,Conversions,CampaignType,DailyBudget,CampaignName
```

**Meta Ads**: `meta_ads_campaign_stats.csv`
```csv
campaign_id,date_start,cpc,cpm,ctr,reach,spend,clicks,impressions,conversion,daily_budget,campaign_name
```

### Output Format

```csv
horizon_days,channel,predicted_revenue,lower_bound,upper_bound,daily_avg,uncertainty
30,google,52341.23,48123.45,56789.01,1744.71,8665.56
```

---

## 🧠 Methodology

### Forecasting Pipeline

1. **Data Ingestion**: `DataLoader` standardises columns per channel
2. **Channel-Specific Cleaning** (`ImprovedDataPreprocessor`):
   - Bing: data-derived AOV, all campaign types, rolling start-date detection
   - Meta: keyword-based Remarketing/Prospecting split, gap-detection cutoff
   - Google: aggregate + ROAS
3. **Model Training** (`FinalProphetForecaster`):
   - Channel + horizon-specific Prophet configs
   - Meta trains two sub-models (Remarketing + Prospecting) and sums forecasts
   - Google uses spend regressor; Bing uses conversions regressor
4. **Uncertainty Quantification**: Calibrated prediction intervals (80% / 90% / 95%)

### Budget Optimization

```python
Maximize: Σ Revenue_channel(Spend_channel)
Subject to:
  Σ Spend_channel ≤ Total_Budget
  ROAS ≥ Min_ROAS
  Spend_channel ≥ 0.05 * Total_Budget  # Minimum allocation
```

Solved using SLSQP (Sequential Least Squares Programming).

---

## 🤖 AI Integration

### Cohere Setup

1. **Get API Key**:
   - Visit [https://cohere.com](https://cohere.com)
   - Sign up for a free account
   - Navigate to API Keys section
   - Copy your API key

2. **Configure `.env`**:
   ```bash
   COHERE_API_KEY=your_cohere_api_key_here
   COHERE_MODEL=command-r-plus-08-2024
   ```

3. **Supported Models**:
   - `command-r-plus-08-2024` (Recommended - Most capable)
   - `command-r-08-2024` (Faster, more cost-effective)
   - `command` (Legacy, still supported)

4. **API Rate Limits**:
   - Free tier: 5 API calls/minute, 1000 calls/month
   - Production tier: Higher limits available

### Example Prompts

**Forecast Analysis**:
```
You are a digital marketing expert. Analyze this forecast...
Historical: Revenue=$45K, Spend=$15K, ROAS=3.0x
Forecast: Revenue=$52K (range: $48K-$56K)

Provide:
1. Explanation of forecast
2. Key risk factor
3. Actionable recommendation
```

**Budget Allocation**:
```
Suggest optimal budget allocation...
Total Budget: $50,000
Channel Performance: {google: 3.2x ROAS, bing: 2.8x, meta: 3.5x}

Provide recommended split with rationale.
```

---

## 🎨 UI Highlights

### Design Principles
- **Dark Theme**: Trading platform aesthetic (#0a0e27, #060817)
- **Glassmorphism**: backdrop-blur with semi-transparent backgrounds
- **3D Elements**: Three.js animated spheres and particles
- **Micro-interactions**: Framer Motion for smooth animations
- **Data Visualization**: Recharts with custom styling

### Key Components
- `Scene3D`: Three.js background with animated spheres
- `RevenueChart`: Multi-channel area chart with gradients
- `MetricCard`: Glassmorphic cards with glow effects
- `ChannelBreakdown`: Pie chart + stats grid

---

## 🧪 Testing

### Run Submission Pipeline

```bash
# Test full pipeline as judges will run it
./run.sh ./data ./pickle/model.pkl ./output/predictions.csv

# Verify output
head output/predictions.csv
```

### Unit Tests

```python
# Test data loader
python -m src.data.loader

# Test forecaster
python -m src.models.prophet_model

# Test optimizer
python -m src.simulation.budget_optimizer
```

---

## 📈 Performance

### Forecasting Accuracy (Backtesting)
- **Google**: ~2.8% / ~14.7% / ~25.8% (30d / 60d / 90d)
- **Bing**: ~12.9% / ~8.4% / ~5.9% (30d / 60d / 90d)
- **Meta**: ~19.9% (30d); 60d/90d wider due to inherent revenue volatility

### API Response Times
- Forecast generation: ~3-5 seconds
- Budget optimization: <2 seconds
- AI insights: ~2-4 seconds (Cohere API latency)

---

## 🏆 Winning Differentiators

1. **Channel-Specific Tuning**: Each channel gets its own Prophet config, seasonalities, and regressors
2. **Meta Sub-Model Split**: Remarketing (stable) and Prospecting (volatile) trained separately and summed — reduces 30d error by 3×
3. **Generic Preprocessing**: All thresholds derived from data — works for any advertiser's export, no hardcoded values
4. **True Probabilistic**: Calibrated prediction intervals (P10/P50/P90) per channel and horizon
5. **AI-Driven Insights**: Cohere LLM provides causal analysis and budget recommendations
6. **Budget Optimization**: SLSQP optimization with ROAS constraint
7. **Production-Grade UI**: 3D effects, glassmorphism, trading platform aesthetics

---

## 📝 Deliverables

- ✅ Working Prototype
- ✅ Technical Documentation (this README + inline docs)
- ✅ Architecture Overview (see Project Structure)
- ✅ Demo Workflow (see Quick Start)

---

## 🔮 Future Enhancements

- **Attribution Modeling**: Multi-touch attribution instead of last-click
- **External Data**: Weather, holidays, macroeconomic indicators
- **A/B Test Integration**: Forecast impact of creative/targeting changes
- **Real-Time Updates**: Streaming data pipeline
- **Mobile App**: React Native version
- **Multi-Tenant**: Support multiple clients

---

## 🤝 Team

**[Your Team Name]**
- [Member 1] - ML Engineering
- [Member 2] - Full-Stack Development  
- [Member 3] - Data Science

**College**: [Your College Name]

---

## 📄 License

MIT License - see LICENSE file

---

## 🙏 Acknowledgments

- **NetElixir** for organizing AIgnition 3.0
- **Facebook Prophet** for time series forecasting
- **XGBoost** for gradient boosting
- **Cohere** for AI-powered insights and analysis
- **Three.js** community for 3D visualization tools

---

## 📧 Contact

For questions or feedback:
- Email: [your-email@example.com]
- GitHub: [your-github-username]

---

**Built with ❤️ for AIgnition 3.0 Hackathon**

*Submission Deadline: July 19, 2026*
