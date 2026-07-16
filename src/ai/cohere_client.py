"""
Cohere AI Client for Marketing Analytics Insights
"""
import cohere
import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class CohereClient:
    """Client for Cohere AI API"""

    def __init__(self):
        self.api_key = os.getenv('COHERE_API_KEY')
        if not self.api_key:
            raise ValueError("COHERE_API_KEY environment variable is required")

        self.model = os.getenv('COHERE_MODEL', 'command-r-plus-08-2024')
        self.client = cohere.ClientV2(api_key=self.api_key)
        logger.info(f"Initialized Cohere client with model: {self.model}")

    def generate_insights(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate AI insights using Cohere"""
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )

            # Extract text content from response
            if hasattr(response, 'message') and hasattr(response.message, 'content'):
                if isinstance(response.message.content, list):
                    # Handle list of content blocks
                    return ''.join([
                        block.text if hasattr(block, 'text') else str(block)
                        for block in response.message.content
                    ])
                else:
                    return response.message.content[0].text if response.message.content else ""

            return str(response)

        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return f"⚠️ AI insights unavailable — could not reach Cohere API ({type(e).__name__}: {str(e)})"

    def analyze_forecast(self, historical_data: Dict, forecast_data: Dict,
                        channel: str) -> str:
        """Generate causal analysis for forecast"""
        prompt = f"""You are a digital marketing analytics expert. Analyze this forecast and provide insights.

**Channel**: {channel.upper()}

**Historical Performance (Last 30 days)**:
- Revenue: ${historical_data.get('revenue', 0):,.2f}
- Spend: ${historical_data.get('spend', 0):,.2f}
- ROAS: {historical_data.get('roas', 0):.2f}
- Trend: {historical_data.get('trend', 'stable')}

**Forecast (Next {forecast_data.get('horizon', 30)} days)**:
- Predicted Revenue: ${forecast_data.get('predicted_revenue', 0):,.2f}
- Range: ${forecast_data.get('lower_bound', 0):,.2f} - ${forecast_data.get('upper_bound', 0):,.2f}
- Predicted ROAS: {forecast_data.get('predicted_roas', 0):.2f}
- Uncertainty: {forecast_data.get('uncertainty_pct', 0):.1f}%

**Context**:
- Month: {forecast_data.get('month', 'N/A')}
- Seasonality: {forecast_data.get('seasonality', 'normal')}

Provide a concise analysis (3-4 sentences) covering:
1. **Explanation**: Why this forecast makes sense given historical trends
2. **Key Risk**: One specific risk factor to watch
3. **Recommendation**: One actionable recommendation to optimize performance

Be specific, use numbers, and be concise."""

        return self.generate_insights(prompt)

    def detect_anomalies(self, data_summary: Dict) -> str:
        """Detect and explain anomalies in historical data"""
        prompt = f"""Analyze this marketing data for anomalies and unusual patterns.

**Data Summary**:
{json.dumps(data_summary, indent=2)}

Identify:
1. Any unusual spikes or drops in revenue/spend
2. ROAS volatility patterns
3. Potential causes (seasonality, external events, campaign changes)

Provide 2-3 specific findings with dates and metrics."""

        return self.generate_insights(prompt)

    def suggest_budget_allocation(self, channel_performance: Dict,
                                 total_budget: float) -> str:
        """Suggest optimal budget allocation"""
        prompt = f"""You are a marketing optimization expert. Suggest budget allocation strategy.

**Total Budget**: ${total_budget:,.2f}

**Channel Performance**:
{json.dumps(channel_performance, indent=2)}

Provide:
1. Recommended budget split across channels (with $ amounts)
2. Rationale based on historical ROAS and efficiency
3. Expected total ROAS with this allocation

Be specific with numbers and keep it concise (4-5 sentences)."""

        return self.generate_insights(prompt)

    def explain_uncertainty(self, forecast_data: Dict) -> str:
        """Explain sources of forecast uncertainty"""
        prompt = f"""Explain the uncertainty in this revenue forecast to a marketing manager.

**Forecast Details**:
- Predicted Revenue: ${forecast_data.get('mean', 0):,.2f}
- Uncertainty Range: ${forecast_data.get('lower', 0):,.2f} - ${forecast_data.get('upper', 0):,.2f}
- Confidence Level: {forecast_data.get('confidence', 80)}%

**Contributing Factors**:
- Historical Volatility: {forecast_data.get('volatility', 'moderate')}
- Data Quality: {forecast_data.get('data_quality', 'good')}
- Forecast Horizon: {forecast_data.get('horizon', 30)} days

Explain in 2-3 sentences:
1. What this uncertainty means practically
2. Main factors contributing to it
3. How to reduce it

Use business language, not statistical jargon."""

        return self.generate_insights(prompt)

    def generate_executive_summary(self, full_forecast: Dict) -> str:
        """Generate executive summary of entire forecast"""
        prompt = f"""Create an executive summary of this multi-channel revenue forecast.

**Forecast Overview**:
{json.dumps(full_forecast, indent=2)}

Provide a concise executive summary (5-6 sentences) covering:
1. Overall revenue projection
2. Channel performance highlights
3. Key opportunities
4. Main risks
5. Strategic recommendation

Write for a CMO audience - strategic, not technical."""

        return self.generate_insights(prompt)

    def generate_channel_level_summary(self, all_channels_data: Dict, horizon: int) -> str:
        """Generate one executive summary for all channel-level forecasts"""

        # Extract aggregate and channel data
        aggregate = all_channels_data.get('aggregate', {})
        channels = all_channels_data.get('channels', all_channels_data)

        prompt = f"""You are a digital marketing analytics expert. Provide an executive summary for this multi-channel forecast.

**Forecast Horizon**: {horizon} days

**Aggregate Forecast (USE THESE EXACT NUMBERS)**:
- Total Predicted Revenue: ${aggregate.get('total_revenue', 0):,.2f}
- Lower Bound (P10): ${aggregate.get('lower_bound', 0):,.2f}
- Upper Bound (P90): ${aggregate.get('upper_bound', 0):,.2f}
- Blended ROAS: {aggregate.get('blended_roas_expected', 0):.2f}x
- ROAS Range: {aggregate.get('blended_roas_lower', 0):.2f}x - {aggregate.get('blended_roas_upper', 0):.2f}x
- Total Spend: ${aggregate.get('total_spend', 0):,.2f}

**Individual Channels Performance**:
{json.dumps(channels, indent=2)}

Provide a strategic executive summary (4-5 sentences) covering:
1. **Overall Performance**: Use the EXACT aggregate metrics provided above (revenue ${aggregate.get('total_revenue', 0):,.2f} and ROAS {aggregate.get('blended_roas_expected', 0):.2f}x)
2. **Channel Comparison**: Which channels are performing strongest/weakest based on their ROAS and revenue
3. **Key Insights**: Critical trends, patterns, or concerns across channels (mention specific declining/increasing trends)
4. **Strategic Recommendation**: One actionable recommendation for cross-channel optimization

CRITICAL RULES:
- Use aggregate metrics EXACTLY as provided - do NOT recalculate by summing channels
- Reference the specific ROAS values from the data
- Be precise with numbers (use exact revenue and ROAS figures)
- Use business language and focus on actionable insights"""

        return self.generate_insights(prompt)

    def generate_campaign_type_summary(self, all_campaign_types_data: Dict, horizon: int) -> str:
        """Generate one executive summary for all campaign-type forecasts"""
        prompt = f"""You are a digital marketing analytics expert. Provide an executive summary for campaign type performance across all channels.

**Forecast Horizon**: {horizon} days

**All Campaign Types Performance**:
{json.dumps(all_campaign_types_data, indent=2)}

Provide a strategic executive summary (4-5 sentences) covering:
1. **Type Performance**: Which campaign types (SEARCH, PERFORMANCE_MAX, DISPLAY, etc.) are driving the most revenue
2. **ROAS Comparison**: Which types have the best/worst ROAS and efficiency
3. **Channel-Type Insights**: Notable patterns in how campaign types perform across different channels
4. **Optimization Recommendation**: One specific recommendation for campaign type budget reallocation

Be specific with campaign types and numbers, focus on actionable insights."""

        return self.generate_insights(prompt)

    def generate_campaign_level_summary(self, all_campaigns_data: Dict, horizon: int, total_campaigns: int) -> str:
        """Generate one executive summary for all campaign-level forecasts"""
        prompt = f"""You are a digital marketing analytics expert. Provide an executive summary for campaign-level performance.

**Forecast Horizon**: {horizon} days
**Total Campaigns Analyzed**: {total_campaigns}

**Campaign Performance Overview**:
{json.dumps(all_campaigns_data, indent=2)}

Provide a strategic executive summary (4-5 sentences) covering:
1. **Portfolio Overview**: Total forecasted revenue across all campaigns and distribution pattern
2. **Top Performers**: Highlight the strongest campaigns by revenue and ROAS
3. **Risk Areas**: Identify campaigns with high uncertainty or declining trends
4. **Portfolio Recommendation**: One actionable recommendation for campaign portfolio optimization

Be specific with campaign names and numbers, focus on portfolio-level insights."""

        return self.generate_insights(prompt, max_tokens=3000)


if __name__ == "__main__":
    # Test Cohere client
    client = CohereClient()

    test_historical = {
        'revenue': 45000,
        'spend': 15000,
        'roas': 3.0,
        'trend': 'increasing'
    }

    test_forecast = {
        'predicted_revenue': 52000,
        'lower_bound': 48000,
        'upper_bound': 56000,
        'predicted_roas': 3.2,
        'uncertainty_pct': 15.4,
        'horizon': 30,
        'month': 'July',
        'seasonality': 'normal'
    }

    insights = client.analyze_forecast(test_historical, test_forecast, 'google')
    print("AI Insights:")
    print(insights)
