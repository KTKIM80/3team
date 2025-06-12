import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
from fredapi import Fred
import io
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from utils.fred_data import FredDataManager
from utils.analysis import CorrelationAnalyzer
from utils.visualizations import ChartGenerator

# Page configuration
st.set_page_config(
    page_title="EPT Group Financial Analytics Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'fred_data' not in st.session_state:
    st.session_state.fred_data = None
if 'export_data' not in st.session_state:
    st.session_state.export_data = None
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}

def main():
    st.title("📈 EPT Group Financial Analytics Dashboard")
    st.markdown("**Correlating FRED Economic Indicators with Export Sales Data**")
    
    # Initialize managers
    fred_manager = FredDataManager()
    analyzer = CorrelationAnalyzer()
    chart_generator = ChartGenerator()
    
    # Sidebar for controls
    with st.sidebar:
        st.header("📊 Analysis Controls")
        
        # FRED Data Section
        st.subheader("🏦 Economic Indicators")
        if st.button("📥 Load FRED Data", type="primary"):
            with st.spinner("Loading economic indicators from FRED..."):
                try:
                    st.session_state.fred_data = fred_manager.load_fred_data()
                    st.success("✅ FRED data loaded successfully!")
                except Exception as e:
                    st.error(f"❌ Error loading FRED data: {str(e)}")
        
        # File Upload Section
        st.subheader("📁 Export Sales Data")
        uploaded_file = st.file_uploader(
            "Upload EPT Group Excel file",
            type=['xlsx', 'xls'],
            help="Upload Excel file containing export sales data with date and sales columns"
        )
        
        if uploaded_file is not None:
            try:
                with st.spinner("Processing export data..."):
                    st.session_state.export_data = fred_manager.process_export_data(uploaded_file)
                st.success("✅ Export data loaded successfully!")
            except Exception as e:
                st.error(f"❌ Error processing export data: {str(e)}")
        
        # Analysis Parameters
        if st.session_state.fred_data is not None and st.session_state.export_data is not None:
            st.subheader("⚙️ Analysis Parameters")
            
            # Look-back window selection
            lookback_window = st.selectbox(
                "📅 Look-back Window",
                options=[3, 6, 12, 24],
                index=2,
                help="Select the number of months to analyze"
            )
            
            # Indicator selection
            available_indicators = list(st.session_state.fred_data.columns)
            selected_indicators = st.multiselect(
                "📈 Select Indicators",
                options=available_indicators,
                default=available_indicators[:5],
                help="Choose which economic indicators to include in analysis"
            )
            
            # Run Analysis Button
            if st.button("🔍 Run Analysis", type="primary"):
                if selected_indicators:
                    with st.spinner("Running correlation and lag analysis..."):
                        try:
                            results = analyzer.run_full_analysis(
                                st.session_state.fred_data,
                                st.session_state.export_data,
                                selected_indicators,
                                lookback_window
                            )
                            st.session_state.analysis_results = results
                            st.success("✅ Analysis completed!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Analysis error: {str(e)}")
                else:
                    st.warning("⚠️ Please select at least one indicator")
    
    # Main content area
    if st.session_state.fred_data is not None:
        st.subheader("📊 Economic Indicators Data")
        with st.expander("View FRED Data", expanded=False):
            st.dataframe(st.session_state.fred_data.tail(20))
            st.info(f"📈 Data range: {st.session_state.fred_data.index.min().strftime('%Y-%m')} to {st.session_state.fred_data.index.max().strftime('%Y-%m')}")
    
    if st.session_state.export_data is not None:
        st.subheader("💼 Export Sales Data")
        with st.expander("View Export Data", expanded=False):
            st.dataframe(st.session_state.export_data.tail(20))
            st.info(f"📈 Data range: {st.session_state.export_data.index.min().strftime('%Y-%m')} to {st.session_state.export_data.index.max().strftime('%Y-%m')}")
    
    # Analysis Results
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        # Time Series Plot
        st.subheader("📈 Time Series Analysis")
        time_series_fig = chart_generator.create_time_series_plot(results)
        st.plotly_chart(time_series_fig, use_container_width=True)
        
        # Correlation Analysis
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🔥 Correlation Heatmap")
            heatmap_fig = chart_generator.create_correlation_heatmap(results['correlation_matrix'])
            st.pyplot(heatmap_fig)
        
        with col2:
            st.subheader("🏆 Top 5 Correlations")
            top_corr_df = results['top_correlations']
            for idx, row in top_corr_df.iterrows():
                correlation = row['Correlation']
                indicator = row['Indicator']
                
                # Color coding based on correlation strength
                if abs(correlation) >= 0.7:
                    emoji = "🔴" if correlation > 0 else "🔵"
                elif abs(correlation) >= 0.5:
                    emoji = "🟠" if correlation > 0 else "🟣"
                else:
                    emoji = "🟡" if correlation > 0 else "🟤"
                
                st.metric(
                    label=f"{emoji} {indicator}",
                    value=f"{correlation:.3f}",
                    delta=f"Rank #{idx + 1}"
                )
        
        # Lag Analysis
        st.subheader("⏰ Time Lag Analysis")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            lag_fig = chart_generator.create_lag_analysis_plot(results['lag_analysis'])
            st.plotly_chart(lag_fig, use_container_width=True)
        
        with col2:
            st.subheader("🥇 Top 3 Lagged Correlations")
            top_lag_df = results['top_lagged_correlations']
            
            for idx, row in top_lag_df.iterrows():
                indicator = row['Indicator']
                lag = row['Lag (months)']
                correlation = row['Correlation']
                
                # Determine lag direction
                if lag > 0:
                    lag_text = f"Export leads by {lag}m"
                    lag_emoji = "⏭️"
                elif lag < 0:
                    lag_text = f"Indicator leads by {abs(lag)}m"
                    lag_emoji = "⏮️"
                else:
                    lag_text = "Simultaneous"
                    lag_emoji = "🎯"
                
                st.metric(
                    label=f"{lag_emoji} {indicator}",
                    value=f"{correlation:.3f}",
                    delta=lag_text
                )
        
        # Additional insights
        st.subheader("💡 Key Insights")
        insights_col1, insights_col2, insights_col3 = st.columns(3)
        
        with insights_col1:
            st.info(f"**Strongest Correlation**\n{results['top_correlations'].iloc[0]['Indicator']}: {results['top_correlations'].iloc[0]['Correlation']:.3f}")
        
        with insights_col2:
            best_lag = results['top_lagged_correlations'].iloc[0]
            lag_months = best_lag['Lag (months)']
            if lag_months > 0:
                lag_insight = f"Export sales lead {best_lag['Indicator']} by {lag_months} months"
            elif lag_months < 0:
                lag_insight = f"{best_lag['Indicator']} leads export sales by {abs(lag_months)} months"
            else:
                lag_insight = f"{best_lag['Indicator']} moves simultaneously with exports"
            
            st.info(f"**Best Predictive Relationship**\n{lag_insight}")
        
        with insights_col3:
            lookback_months = results.get('lookback_window', 'N/A')
            analysis_period = results.get('analysis_period', 'N/A')
            st.info(f"**Analysis Period**\n{lookback_months} months lookback\n{analysis_period}")

if __name__ == "__main__":
    main()
