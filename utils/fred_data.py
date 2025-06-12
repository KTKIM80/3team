import streamlit as st
import pandas as pd
import numpy as np
from fredapi import Fred
from datetime import datetime
import io

class FredDataManager:
    def __init__(self):
        # FRED API key
        self.fred_api_key = "b32ddacf51e52ec5af60de1cf34a183b"
        self.fred = Fred(api_key=self.fred_api_key)
        
        # FRED indicators mapping
        self.indicators = {
            'USD/KRW': 'DEXKOUS',
            'WTI': 'DCOILWTICO',
            'US10Y': 'DGS10',
            'CPI': 'CPIAUCSL',
            'DSPI': 'DSPI',
            'PPI': 'PPIACO',
            'UNRATE': 'UNRATE',
            'TOTALSA': 'TOTALSA',
            'IPG3361T3S': 'IPG3361T3S',
            'BDIY': 'STLFSI2'  # Baltic Dry Index proxy
        }
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def load_fred_data(_self):
        """Load all FRED economic indicators"""
        try:
            data_dict = {}
            
            for name, series_id in _self.indicators.items():
                try:
                    # Get monthly data for the last 5 years
                    series_data = _self.fred.get_series(
                        series_id, 
                        start='2019-01-01',
                        frequency='m'
                    )
                    
                    # Handle missing values
                    series_data = series_data.dropna()
                    
                    if len(series_data) > 0:
                        data_dict[name] = series_data
                        
                except Exception as e:
                    st.warning(f"Could not load {name} ({series_id}): {str(e)}")
                    continue
            
            if not data_dict:
                raise Exception("No FRED data could be loaded")
            
            # Combine all series into a DataFrame
            fred_df = pd.DataFrame(data_dict)
            
            # Ensure monthly frequency and forward fill missing values
            fred_df = fred_df.asfreq('M').fillna(method='ffill')
            
            # Calculate percentage changes for some indicators
            pct_change_indicators = ['USD/KRW', 'WTI', 'CPI', 'PPI']
            for indicator in pct_change_indicators:
                if indicator in fred_df.columns:
                    fred_df[f'{indicator}_pct'] = fred_df[indicator].pct_change() * 100
            
            return fred_df
            
        except Exception as e:
            raise Exception(f"Failed to load FRED data: {str(e)}")
    
    def process_export_data(self, uploaded_file):
        """Process uploaded Excel file containing export sales data"""
        try:
            # Read Excel file
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            else:
                df = pd.read_excel(uploaded_file)
            
            # Try to identify date and sales columns
            date_columns = []
            sales_columns = []
            
            for col in df.columns:
                col_lower = str(col).lower()
                
                # Look for date columns
                if any(word in col_lower for word in ['date', 'time', 'month', 'year', 'period']):
                    date_columns.append(col)
                
                # Look for sales/revenue columns
                if any(word in col_lower for word in ['sales', 'revenue', 'export', 'amount', 'value']):
                    sales_columns.append(col)
            
            # If no clear columns found, use first two columns
            if not date_columns and not sales_columns:
                if len(df.columns) >= 2:
                    date_columns = [df.columns[0]]
                    sales_columns = [df.columns[1]]
                else:
                    raise Exception("Unable to identify date and sales columns in the uploaded file")
            
            # Use the first identified columns
            date_col = date_columns[0] if date_columns else df.columns[0]
            sales_col = sales_columns[0] if sales_columns else df.columns[1]
            
            # Create clean DataFrame
            export_df = pd.DataFrame({
                'Date': pd.to_datetime(df[date_col]),
                'Export_Sales': pd.to_numeric(df[sales_col], errors='coerce')
            })
            
            # Remove rows with missing values
            export_df = export_df.dropna()
            
            # Set date as index and convert to monthly frequency
            export_df = export_df.set_index('Date')
            export_df = export_df.resample('M').sum()  # Sum if multiple entries per month
            
            # Remove zero or negative values
            export_df = export_df[export_df['Export_Sales'] > 0]
            
            if len(export_df) == 0:
                raise Exception("No valid export sales data found after processing")
            
            return export_df
            
        except Exception as e:
            raise Exception(f"Failed to process export data: {str(e)}")
    
    def align_datasets(self, fred_data, export_data):
        """Align FRED and export data by date"""
        try:
            # Find common date range
            start_date = max(fred_data.index.min(), export_data.index.min())
            end_date = min(fred_data.index.max(), export_data.index.max())
            
            # Filter both datasets to common range
            fred_aligned = fred_data.loc[start_date:end_date]
            export_aligned = export_data.loc[start_date:end_date]
            
            # Combine datasets
            combined_data = pd.concat([fred_aligned, export_aligned], axis=1)
            
            # Drop rows with any missing values
            combined_data = combined_data.dropna()
            
            if len(combined_data) == 0:
                raise Exception("No overlapping data found between FRED and export datasets")
            
            return combined_data
            
        except Exception as e:
            raise Exception(f"Failed to align datasets: {str(e)}")
