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
    page_title="EPT Group 금융 분석 대시보드",
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
    st.title("📈 EPT Group 금융 분석 대시보드")
    st.markdown("**FRED 경제 지표와 수출 매출 데이터 상관관계 분석**")
    
    # 경제 지표 설명
    with st.expander("📊 분석 대상 경제 지표 설명", expanded=False):
        st.markdown("""
        **분석에 사용되는 주요 경제 지표들:**
        
        - **USD/KRW**: 달러-원 환율 (한국 수출에 직접적 영향)
        - **WTI**: 서부텍사스유 가격 (국제 유가)
        - **US10Y**: 미국 10년 국채 금리 (글로벌 금리 기준)
        - **CPI**: 미국 소비자물가지수 (인플레이션 지표)
        - **PDI**: 미국 개인가처분소득 (소비력 지표)
        - **PDI/CPI**: 실질 구매력 지표
        - **PPI**: 미국 생산자물가지수 (생산비용 지표)
        - **UNRATE**: 미국 실업률 (경기 상황 지표)
        - **AUTO_SALES**: 미국 자동차 판매량 (소비 심리)
        - **AUTO_PROD**: 미국 자동차 생산량 (제조업 활동)
        - **BDI**: 국제 운임지수 (글로벌 무역량 지표)
        """)
    
    # Initialize managers
    fred_manager = FredDataManager()
    analyzer = CorrelationAnalyzer()
    chart_generator = ChartGenerator()
    
    # Sidebar for controls
    with st.sidebar:
        st.header("📊 분석 제어판")
        
        # FRED Data Section
        st.subheader("🏦 경제 지표 데이터")
        
        # Date range selection
        st.markdown("**📅 데이터 수집 기간 설정**")
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "시작 날짜",
                value=datetime.now() - timedelta(days=10*365),  # 기본값: 10년 전
                min_value=datetime(1990, 1, 1),
                max_value=datetime.now(),
                help="FRED 데이터 수집 시작 날짜를 선택하세요"
            )
        
        with col2:
            end_date = st.date_input(
                "종료 날짜",
                value=datetime.now(),
                min_value=datetime(1990, 1, 1),
                max_value=datetime.now(),
                help="FRED 데이터 수집 종료 날짜를 선택하세요"
            )
        
        # 날짜 유효성 검사
        if start_date >= end_date:
            st.error("⚠️ 시작 날짜는 종료 날짜보다 이전이어야 합니다")
        else:
            # 선택된 기간 표시
            period_days = (end_date - start_date).days
            period_years = period_days / 365.25
            st.info(f"📊 선택된 기간: {period_years:.1f}년 ({period_days}일)")
        
        if st.button("📥 FRED 데이터 로드", type="primary", disabled=(start_date >= end_date)):
            with st.spinner("FRED에서 경제 지표를 불러오는 중..."):
                try:
                    st.session_state.fred_data = fred_manager.load_fred_data(
                        start_date=datetime.combine(start_date, datetime.min.time()),
                        end_date=datetime.combine(end_date, datetime.min.time())
                    )
                    st.success("✅ FRED 데이터 로드 성공!")
                except Exception as e:
                    st.error(f"❌ FRED 데이터 로드 오류: {str(e)}")
        
        # File Upload Section
        st.subheader("📁 수출 매출 데이터")
        uploaded_file = st.file_uploader(
            "EPT Group 엑셀 파일 업로드",
            type=['xlsx', 'xls'],
            help="날짜와 매출 컬럼이 포함된 엑셀 파일을 업로드하세요"
        )
        
        if uploaded_file is not None:
            try:
                with st.spinner("수출 데이터를 처리하는 중..."):
                    st.session_state.export_data = fred_manager.process_export_data(uploaded_file)
                st.success("✅ 수출 데이터 로드 성공!")
            except Exception as e:
                st.error(f"❌ 수출 데이터 처리 오류: {str(e)}")
        
        # Analysis Parameters
        if st.session_state.fred_data is not None and st.session_state.export_data is not None:
            st.subheader("⚙️ 분석 설정")
            
            # Look-back window selection
            lookback_window = st.selectbox(
                "📅 분석 기간 (개월)",
                options=[3, 6, 12, 24, 36],
                index=2,
                help="분석할 과거 데이터의 개월 수를 선택하세요"
            )
            
            # Indicator selection
            available_indicators = list(st.session_state.fred_data.columns)
            # PDI/CPI가 있다면 기본 선택에 포함
            default_indicators = []
            priority_indicators = ['USD/KRW', 'WTI', 'US10Y', 'CPI', 'PDI/CPI', 'UNRATE']
            for indicator in priority_indicators:
                if indicator in available_indicators:
                    default_indicators.append(indicator)
            
            selected_indicators = st.multiselect(
                "📈 분석할 지표 선택",
                options=available_indicators,
                default=default_indicators[:6],
                help="상관관계 분석에 포함할 경제 지표를 선택하세요"
            )
            
            # Run Analysis Button
            if st.button("🔍 분석 실행", type="primary"):
                if selected_indicators:
                    with st.spinner("상관관계 및 시차 분석을 실행하는 중..."):
                        try:
                            results = analyzer.run_full_analysis(
                                st.session_state.fred_data,
                                st.session_state.export_data,
                                selected_indicators,
                                lookback_window
                            )
                            st.session_state.analysis_results = results
                            st.success("✅ 분석 완료!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 분석 오류: {str(e)}")
                else:
                    st.warning("⚠️ 최소 하나의 지표를 선택해주세요")
    
    # Main content area
    if st.session_state.fred_data is not None:
        # 실제 데이터 기간 정보
        actual_start = st.session_state.fred_data.index.min()
        actual_end = st.session_state.fred_data.index.max()
        
        st.subheader(f"📊 경제 지표 데이터 ({actual_start.strftime('%Y-%m-%d')} ~ {actual_end.strftime('%Y-%m-%d')})")
        
        # 데이터 요약 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📈 지표 수", len(st.session_state.fred_data.columns))
        with col2:
            st.metric("📅 데이터 시작", actual_start.strftime('%Y-%m-%d'))
        with col3:
            st.metric("📅 데이터 종료", actual_end.strftime('%Y-%m-%d'))
        with col4:
            st.metric("📊 데이터 포인트", len(st.session_state.fred_data))
        
        with st.expander("FRED 데이터 보기", expanded=False):
            # 최신 데이터 표시
            st.subheader("📈 최신 20개 데이터")
            latest_data = st.session_state.fred_data.tail(20)
            st.dataframe(latest_data, use_container_width=True)
            
            # 기본 통계 정보
            st.subheader("📊 기본 통계")
            st.dataframe(st.session_state.fred_data.describe(), use_container_width=True)
    
    if st.session_state.export_data is not None:
        st.subheader("💼 수출 매출 데이터")
        
        # 수출 데이터 요약
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📅 데이터 시작", st.session_state.export_data.index.min().strftime('%Y-%m'))
        with col2:
            st.metric("📅 데이터 종료", st.session_state.export_data.index.max().strftime('%Y-%m'))
        with col3:
            st.metric("📊 데이터 포인트", len(st.session_state.export_data))
        with col4:
            avg_sales = st.session_state.export_data['Export_Sales'].mean()
            st.metric("💰 평균 매출", f"{avg_sales:,.0f}")
        
        with st.expander("수출 데이터 보기", expanded=False):
            st.dataframe(st.session_state.export_data.tail(20), use_container_width=True)
            
            # 수출 데이터 기본 통계
            st.subheader("📊 수출 매출 통계")
            export_stats = st.session_state.export_data['Export_Sales'].describe()
            st.dataframe(export_stats.to_frame().T, use_container_width=True)
    
    # Analysis Results
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        st.header("📈 분석 결과")
        
        # Time Series Plot
        st.subheader("📈 시계열 분석")
        time_series_fig = chart_generator.create_time_series_plot(results)
        st.plotly_chart(time_series_fig, use_container_width=True)
        
        # Correlation Analysis
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🔥 상관관계 히트맵")
            heatmap_fig = chart_generator.create_correlation_heatmap(results['correlation_matrix'])
            st.pyplot(heatmap_fig)
        
        with col2:
            st.subheader("🏆 상위 5개 상관관계")
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
                    delta=f"순위 #{idx + 1}"
                )
        
        # Lag Analysis
        st.subheader("⏰ 시차 분석")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            lag_fig = chart_generator.create_lag_analysis_plot(results['lag_analysis'])
            st.plotly_chart(lag_fig, use_container_width=True)
        
        with col2:
            st.subheader("🥇 상위 3개 시차 상관관계")
            top_lag_df = results['top_lagged_correlations']
            
            for idx, row in top_lag_df.iterrows():
                indicator = row['Indicator']
                lag = row['Lag (months)']
                correlation = row['Correlation']
                
                # Determine lag direction
                if lag > 0:
                    lag_text = f"수출이 {lag}개월 선행"
                    lag_emoji = "⏭️"
                elif lag < 0:
                    lag_text = f"지표가 {abs(lag)}개월 선행"
                    lag_emoji = "⏮️"
                else:
                    lag_text = "동시 움직임"
                    lag_emoji = "🎯"
                
                st.metric(
                    label=f"{lag_emoji} {indicator}",
                    value=f"{correlation:.3f}",
                    delta=lag_text
                )
        
        # Additional insights
        st.subheader("💡 주요 인사이트")
        insights_col1, insights_col2, insights_col3 = st.columns(3)
        
        with insights_col1:
            st.info(f"**가장 강한 상관관계**\n{results['top_correlations'].iloc[0]['Indicator']}: {results['top_correlations'].iloc[0]['Correlation']:.3f}")
        
        with insights_col2:
            best_lag = results['top_lagged_correlations'].iloc[0]
            lag_months = best_lag['Lag (months)']
            if lag_months > 0:
                lag_insight = f"수출 매출이 {best_lag['Indicator']}보다 {lag_months}개월 선행"
            elif lag_months < 0:
                lag_insight = f"{best_lag['Indicator']}가 수출 매출보다 {abs(lag_months)}개월 선행"
            else:
                lag_insight = f"{best_lag['Indicator']}와 수출 매출이 동시에 움직임"
            
            st.info(f"**최적 예측 관계**\n{lag_insight}")
        
        with insights_col3:
            lookback_months = results.get('lookback_window', 'N/A')
            analysis_period = results.get('analysis_period', 'N/A')
            st.info(f"**분석 기간**\n{lookback_months}개월 분석\n{analysis_period}")

if __name__ == "__main__":
    main()
