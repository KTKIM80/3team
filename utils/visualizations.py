import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

class ChartGenerator:
    def __init__(self):
        self.color_palette = px.colors.qualitative.Set3
    
    def create_time_series_plot(self, analysis_results):
        """Create interactive time series plot"""
        data = analysis_results['analysis_data']
        
        # Create subplots with secondary y-axis
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Economic Indicators (Normalized)', 'Export Sales'),
            vertical_spacing=0.15,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}]]
        )
        
        # Normalize indicators for better comparison (excluding Export_Sales)
        indicators = [col for col in data.columns if col != 'Export_Sales']
        normalized_data = data[indicators].copy()
        
        for col in indicators:
            if data[col].std() != 0:
                normalized_data[col] = (data[col] - data[col].mean()) / data[col].std()
        
        # Plot normalized indicators
        for i, indicator in enumerate(indicators):
            fig.add_trace(
                go.Scatter(
                    x=normalized_data.index,
                    y=normalized_data[indicator],
                    mode='lines',
                    name=indicator,
                    line=dict(color=self.color_palette[i % len(self.color_palette)]),
                    hovertemplate=f'<b>{indicator}</b><br>Date: %{{x}}<br>Normalized Value: %{{y:.2f}}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # Plot export sales
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data['Export_Sales'],
                mode='lines+markers',
                name='Export Sales',
                line=dict(color='red', width=3),
                marker=dict(size=6),
                hovertemplate='<b>Export Sales</b><br>Date: %{x}<br>Sales: %{y:,.0f}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            height=600,
            title_text="Time Series Analysis: Economic Indicators vs Export Sales",
            title_x=0.5,
            showlegend=True,
            hovermode='x unified'
        )
        
        # Update x-axis labels
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Normalized Values", row=1, col=1)
        fig.update_yaxes(title_text="Export Sales", row=2, col=1)
        
        return fig
    
    def create_correlation_heatmap(self, correlation_matrix):
        """Create correlation heatmap using seaborn"""
        plt.figure(figsize=(12, 8))
        
        # Create mask for upper triangle (optional)
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
        
        # Create heatmap
        sns.heatmap(
            correlation_matrix,
            mask=mask,
            annot=True,
            cmap='RdBu_r',
            center=0,
            square=True,
            fmt='.3f',
            cbar_kws={"shrink": .8},
            linewidths=0.5
        )
        
        plt.title('Correlation Matrix: Economic Indicators vs Export Sales', 
                  fontsize=14, fontweight='bold', pad=20)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        
        return plt.gcf()
    
    def create_lag_analysis_plot(self, lag_analysis):
        """Create lag correlation analysis plot"""
        fig = go.Figure()
        
        for i, (indicator, lag_corr) in enumerate(lag_analysis.items()):
            lags = list(lag_corr.keys())
            correlations = list(lag_corr.values())
            
            fig.add_trace(
                go.Scatter(
                    x=lags,
                    y=correlations,
                    mode='lines+markers',
                    name=indicator,
                    line=dict(color=self.color_palette[i % len(self.color_palette)]),
                    marker=dict(size=8),
                    hovertemplate=f'<b>{indicator}</b><br>Lag: %{{x}} months<br>Correlation: %{{y:.3f}}<extra></extra>'
                )
            )
        
        # Add reference lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Update layout
        fig.update_layout(
            title="Time Lag Correlation Analysis",
            title_x=0.5,
            xaxis_title="Lag (months)",
            yaxis_title="Correlation Coefficient",
            height=500,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Add annotations for lag interpretation
        fig.add_annotation(
            x=-10, y=0.9,
            text="← Indicator leads Export",
            showarrow=False,
            font=dict(size=10, color="gray")
        )
        
        fig.add_annotation(
            x=10, y=0.9,
            text="Export leads Indicator →",
            showarrow=False,
            font=dict(size=10, color="gray")
        )
        
        return fig
    
    def create_correlation_comparison_chart(self, correlations_data):
        """Create bar chart comparing correlations"""
        indicators = list(correlations_data.keys())
        correlations = [data['correlation'] for data in correlations_data.values()]
        
        # Color bars based on correlation strength and direction
        colors = []
        for corr in correlations:
            if corr > 0.7:
                colors.append('darkgreen')
            elif corr > 0.5:
                colors.append('green')
            elif corr > 0.3:
                colors.append('lightgreen')
            elif corr > -0.3:
                colors.append('gray')
            elif corr > -0.5:
                colors.append('lightcoral')
            elif corr > -0.7:
                colors.append('red')
            else:
                colors.append('darkred')
        
        fig = go.Figure(data=[
            go.Bar(
                x=indicators,
                y=correlations,
                marker_color=colors,
                hovertemplate='<b>%{x}</b><br>Correlation: %{y:.3f}<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title="Correlation Strength Comparison",
            title_x=0.5,
            xaxis_title="Economic Indicators",
            yaxis_title="Correlation with Export Sales",
            height=400,
            xaxis_tickangle=-45
        )
        
        # Add reference line at y=0
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        return fig
