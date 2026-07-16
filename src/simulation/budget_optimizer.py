"""
Budget Optimization and Scenario Simulation
"""
import pandas as pd
import numpy as np
from scipy.optimize import minimize, LinearConstraint
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class BudgetOptimizer:
    """Optimize budget allocation across channels"""

    def __init__(self):
        self.spend_response_curves = {}

    def fit_spend_response_curve(self, df: pd.DataFrame, channel: str):
        """Fit spend-revenue response curve for a channel"""
        channel_data = df[df['channel'] == channel].copy()

        # Aggregate by day
        daily = channel_data.groupby('date').agg({
            'spend': 'sum',
            'revenue': 'sum'
        }).reset_index()

        # Fit logarithmic model: Revenue = a * log(Spend + 1) + b
        from sklearn.linear_model import LinearRegression

        X = np.log(daily['spend'].values + 1).reshape(-1, 1)
        y = daily['revenue'].values

        model = LinearRegression()
        model.fit(X, y)

        self.spend_response_curves[channel] = {
            'type': 'logarithmic',
            'coef': float(model.coef_[0]),
            'intercept': float(model.intercept_),
            'historical_avg_spend': float(daily['spend'].mean()),
            'historical_avg_revenue': float(daily['revenue'].mean()),
            'historical_roas': float(daily['revenue'].sum() / daily['spend'].sum()) if daily['spend'].sum() > 0 else 0
        }

        logger.info(f"Fitted spend response curve for {channel}: coef={model.coef_[0]:.2f}")

    def predict_revenue(self, channel: str, spend: float) -> float:
        """Predict revenue for given spend"""
        if channel not in self.spend_response_curves:
            raise ValueError(f"No curve fitted for channel {channel}")

        curve = self.spend_response_curves[channel]

        if curve['type'] == 'logarithmic':
            revenue = curve['coef'] * np.log(spend + 1) + curve['intercept']
        else:
            revenue = spend * curve['historical_roas']

        return max(0, revenue)

    def optimize_allocation(self, total_budget: float, channels: List[str],
                           min_roas: float = None) -> Dict:
        """Optimize budget allocation across channels"""
        logger.info(f"Optimizing allocation for budget ${total_budget:,.2f}")

        # Initial guess (equal split)
        x0 = np.array([total_budget / len(channels)] * len(channels))

        # Objective: maximize total revenue (minimize negative revenue)
        def objective(spends):
            total_revenue = sum(self.predict_revenue(ch, sp) for ch, sp in zip(channels, spends))
            return -total_revenue

        # Constraints
        constraints = []

        # Budget constraint: sum of spends = total budget
        constraints.append({
            'type': 'eq',
            'fun': lambda x: np.sum(x) - total_budget
        })

        # ROAS constraint if provided
        if min_roas is not None:
            def roas_constraint(spends):
                total_revenue = sum(self.predict_revenue(ch, sp) for ch, sp in zip(channels, spends))
                total_spend = np.sum(spends)
                return total_revenue - (min_roas * total_spend)

            constraints.append({
                'type': 'ineq',
                'fun': roas_constraint
            })

        # Bounds: each channel gets at least 5% of budget
        bounds = [(total_budget * 0.05, total_budget * 0.8) for _ in channels]

        # Optimize
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")

        # Calculate results
        optimal_spends = result.x
        predicted_revenues = [self.predict_revenue(ch, sp) for ch, sp in zip(channels, optimal_spends)]
        total_revenue = sum(predicted_revenues)
        blended_roas = total_revenue / total_budget if total_budget > 0 else 0

        return {
            'allocation': {
                ch: {
                    'spend': float(spend),
                    'predicted_revenue': float(rev),
                    'roas': float(rev / spend) if spend > 0 else 0,
                    'percentage': float(spend / total_budget * 100)
                }
                for ch, spend, rev in zip(channels, optimal_spends, predicted_revenues)
            },
            'total_budget': float(total_budget),
            'total_predicted_revenue': float(total_revenue),
            'blended_roas': float(blended_roas),
            'optimization_status': result.success
        }

    def simulate_scenario(self, budget_scenario: Dict[str, float]) -> Dict:
        """Simulate outcome for given budget scenario"""
        results = {}
        total_revenue = 0
        total_spend = 0

        for channel, spend in budget_scenario.items():
            if channel in self.spend_response_curves:
                revenue = self.predict_revenue(channel, spend)
                roas = revenue / spend if spend > 0 else 0

                results[channel] = {
                    'spend': float(spend),
                    'predicted_revenue': float(revenue),
                    'roas': float(roas)
                }

                total_revenue += revenue
                total_spend += spend

        results['total'] = {
            'spend': float(total_spend),
            'predicted_revenue': float(total_revenue),
            'blended_roas': float(total_revenue / total_spend) if total_spend > 0 else 0
        }

        return results

    def calculate_marginal_roas(self, channel: str, current_spend: float,
                                increment: float = 1000) -> float:
        """Calculate marginal ROAS for additional spend"""
        current_revenue = self.predict_revenue(channel, current_spend)
        new_revenue = self.predict_revenue(channel, current_spend + increment)

        marginal_revenue = new_revenue - current_revenue
        marginal_roas = marginal_revenue / increment if increment > 0 else 0

        return float(marginal_roas)

    def get_spend_response_data(self, channel: str, spend_range: Tuple[float, float],
                               points: int = 50) -> pd.DataFrame:
        """Get spend-response curve data for visualization"""
        if channel not in self.spend_response_curves:
            return pd.DataFrame()

        spends = np.linspace(spend_range[0], spend_range[1], points)
        revenues = [self.predict_revenue(channel, s) for s in spends]
        roas_values = [r / s if s > 0 else 0 for r, s in zip(revenues, spends)]

        return pd.DataFrame({
            'spend': spends,
            'revenue': revenues,
            'roas': roas_values
        })


if __name__ == "__main__":
    from src.data.loader import DataLoader
    from src.data.preprocessor import DataPreprocessor

    # Load data
    loader = DataLoader("./data")
    df = loader.load_all_channels()

    preprocessor = DataPreprocessor()
    df = preprocessor.prepare_for_forecasting(df)

    # Fit curves
    optimizer = BudgetOptimizer()
    for channel in ['google', 'bing', 'meta']:
        optimizer.fit_spend_response_curve(df, channel)

    # Optimize allocation
    result = optimizer.optimize_allocation(50000, ['google', 'bing', 'meta'], min_roas=2.0)

    print("Optimal Allocation:")
    print(json.dumps(result, indent=2))

    # Calculate marginal ROAS
    for channel in ['google', 'bing', 'meta']:
        current = result['allocation'][channel]['spend']
        marginal = optimizer.calculate_marginal_roas(channel, current)
        print(f"{channel} marginal ROAS at ${current:,.0f}: {marginal:.2f}")
