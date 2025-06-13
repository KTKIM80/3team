import pandas as pd
import numpy as np
from scipy.stats import pearsonr
import streamlit as st

class CorrelationAnalyzer:
    def __init__(self):
        self.lag_range = range(-6, 7)  # -6 to +6 months
    
    def calculate_correlations(self, fred_data, export_data, selected_indicators):
        """Calculate correlations between export sales and selected indicators"""
        correlations = {}
        
        for indicator in selected_indicators:
            if indicator in fred_data.columns:
                try:
                    # Ensure both series have the same index
                    indicator_series = fred_data[indicator].dropna()
                    export_series = export_data['Export_Sales'].dropna()
                    
                    # Find common dates
                    common_dates = indicator_series.index.intersection(export_series.index)
                    
                    if len(common_dates) >= 3:  # Minimum 3 points for correlation
                        ind_values = indicator_series.loc[common_dates]
                        exp_values = export_series.loc[common_dates]
                        
                        correlation, p_value = pearsonr(ind_values, exp_values)
                        
                        if not np.isnan(correlation):
                            correlations[indicator] = {
                                'correlation': correlation,
                                'p_value': p_value,
                                'n_observations': len(common_dates)
                            }
                except Exception as e:
                    st.warning(f"Could not calculate correlation for {indicator}: {str(e)}")
                    continue
        
        return correlations
    
    def calculate_lag_correlations(self, fred_data, export_data, selected_indicators):
        """Calculate time-lagged correlations"""
        lag_results = {}
        
        for indicator in selected_indicators:
            if indicator in fred_data.columns:
                lag_correlations = {}
                
                indicator_series = fred_data[indicator].dropna()
                export_series = export_data['Export_Sales'].dropna()
                
                for lag in self.lag_range:
                    try:
                        if lag > 0:
                            # Positive lag: export leads indicator
                            shifted_export = export_series.shift(lag)
                            common_dates = indicator_series.index.intersection(shifted_export.index)
                            
                            if len(common_dates) >= 3:
                                ind_values = indicator_series.loc[common_dates]
                                exp_values = shifted_export.loc[common_dates]
                                
                                # Remove NaN values
                                valid_mask = ~(np.isnan(ind_values) | np.isnan(exp_values))
                                if valid_mask.sum() >= 3:
                                    correlation, _ = pearsonr(
                                        ind_values[valid_mask], 
                                        exp_values[valid_mask]
                                    )
                                    if not np.isnan(correlation):
                                        lag_correlations[lag] = correlation
                        
                        elif lag < 0:
                            # Negative lag: indicator leads export
                            shifted_indicator = indicator_series.shift(-lag)
                            common_dates = shifted_indicator.index.intersection(export_series.index)
                            
                            if len(common_dates) >= 3:
                                ind_values = shifted_indicator.loc[common_dates]
                                exp_values = export_series.loc[common_dates]
                                
                                # Remove NaN values
                                valid_mask = ~(np.isnan(ind_values) | np.isnan(exp_values))
                                if valid_mask.sum() >= 3:
                                    correlation, _ = pearsonr(
                                        ind_values[valid_mask], 
                                        exp_values[valid_mask]
                                    )
                                    if not np.isnan(correlation):
                                        lag_correlations[lag] = correlation
                        
                        else:  # lag == 0
                            # No lag: simultaneous correlation
                            common_dates = indicator_series.index.intersection(export_series.index)
                            
                            if len(common_dates) >= 3:
                                ind_values = indicator_series.loc[common_dates]
                                exp_values = export_series.loc[common_dates]
                                
                                correlation, _ = pearsonr(ind_values, exp_values)
                                if not np.isnan(correlation):
                                    lag_correlations[lag] = correlation
                    
                    except Exception:
                        continue
                
                if lag_correlations:
                    lag_results[indicator] = lag_correlations
        
        return lag_results
    
    def get_top_correlations(self, correlations, top_n=5):
        """Get top N correlations sorted by absolute value"""
        correlation_list = []
        
        for indicator, corr_data in correlations.items():
            correlation_list.append({
                'Indicator': indicator,
                'Correlation': corr_data['correlation'],
                'P_Value': corr_data['p_value'],
                'N_Observations': corr_data['n_observations']
            })
        
        # Sort by absolute correlation value
        correlation_df = pd.DataFrame(correlation_list)
        correlation_df['Abs_Correlation'] = correlation_df['Correlation'].abs()
        correlation_df = correlation_df.sort_values('Abs_Correlation', ascending=False)
        
        return correlation_df.head(top_n)[['Indicator', 'Correlation', 'P_Value', 'N_Observations']]
    
    def get_top_lagged_correlations(self, lag_results, top_n=3):
        """Get top N lagged correlations"""
        lagged_list = []
        
        for indicator, lag_corr in lag_results.items():
            for lag, correlation in lag_corr.items():
                lagged_list.append({
                    'Indicator': indicator,
                    'Lag (months)': lag,
                    'Correlation': correlation,
                    'Abs_Correlation': abs(correlation)
                })
        
        # Sort by absolute correlation value
        lagged_df = pd.DataFrame(lagged_list)
        lagged_df = lagged_df.sort_values('Abs_Correlation', ascending=False)
        
        return lagged_df.head(top_n)[['Indicator', 'Lag (months)', 'Correlation']]
    
    def create_correlation_matrix(self, fred_data, export_data, selected_indicators):
        """Create correlation matrix for heatmap"""
        # Select only the indicators that we want to analyze
        available_indicators = [ind for ind in selected_indicators if ind in fred_data.columns]
        
        # Combine data
        combined_data = pd.concat([
            fred_data[available_indicators],
            export_data[['Export_Sales']]
        ], axis=1)
        
        # Calculate correlation matrix
        correlation_matrix = combined_data.corr()
        
        return correlation_matrix
    
    def run_full_analysis(self, fred_data, export_data, selected_indicators, lookback_window):
        """Run complete correlation and lag analysis"""
        try:
            # Filter data to lookback window
            end_date = min(fred_data.index.max(), export_data.index.max())
            start_date = end_date - pd.DateOffset(months=lookback_window)
            
            fred_filtered = fred_data.loc[start_date:end_date]
            export_filtered = export_data.loc[start_date:end_date]
            
            # Calculate correlations
            correlations = self.calculate_correlations(fred_filtered, export_filtered, selected_indicators)
            
            # Calculate lag correlations
            lag_correlations = self.calculate_lag_correlations(fred_filtered, export_filtered, selected_indicators)
            
            # Get top correlations
            top_correlations = self.get_top_correlations(correlations)
            
            # Get top lagged correlations
            top_lagged_correlations = self.get_top_lagged_correlations(lag_correlations)
            
            # Create correlation matrix
            correlation_matrix = self.create_correlation_matrix(fred_filtered, export_filtered, selected_indicators)
            
            # Prepare data for time series plot
            analysis_data = pd.concat([
                fred_filtered[selected_indicators],
                export_filtered[['Export_Sales']]
            ], axis=1).dropna()
            
            return {
                'correlations': correlations,
                'lag_analysis': lag_correlations,
                'top_correlations': top_correlations,
                'top_lagged_correlations': top_lagged_correlations,
                'correlation_matrix': correlation_matrix,
                'analysis_data': analysis_data,
                'lookback_window': lookback_window,
                'analysis_period': f"{start_date.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')}"
            }
            
        except Exception as e:
            raise Exception(f"Analysis failed: {str(e)}")
