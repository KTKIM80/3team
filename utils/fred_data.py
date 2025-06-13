import streamlit as st
import pandas as pd
import numpy as np
from fredapi import Fred
from datetime import datetime, timedelta
import io
import time

class FredDataManager:
    def __init__(self):
        # FRED API key
        self.fred_api_key = "b32ddacf51e52ec5af60de1cf34a183b"
        self.fred = None
        self.connection_tested = False
        
        # FRED indicators mapping - 요청된 경제 지표들
        self.indicators = {
            'USD/KRW': 'DEXKOUS',           # USD-KRW 환율
            'WTI': 'DCOILWTICO',            # 국제유가 (WTI)
            'US10Y': 'DGS10',               # 미국 10년 국채금리
            'CPI': 'CPIAUCSL',              # 미국 CPI
            'PDI': 'DSPI',                  # 미국 Personal Disposal Income
            'PPI': 'PPIACO',                # 미국 PPI
            'UNRATE': 'UNRATE',             # 미국 실업률
            'AUTO_SALES': 'TOTALSA',        # 미국 자동차 판매량
            'AUTO_PROD': 'DAUPSA',      # 미국 자동차 생산량
            'BDI': 'STLFSI2'                # 국제 운임지수 (Baltic Dry Index proxy)
        }
    
    def test_fred_connection(self):
        """FRED API 연결 테스트"""
        try:
            st.info("🔗 FRED API 연결을 테스트하는 중...")
            self.fred = Fred(api_key=self.fred_api_key)
            
            # 간단한 테스트 쿼리 (GDP 데이터 최신 1개)
            test_data = self.fred.get_series('GDP', limit=1)
            
            if test_data is not None and len(test_data) > 0:
                st.success("✅ FRED API 연결 성공!")
                self.connection_tested = True
                return True
            else:
                st.error("❌ FRED API 연결 실패: 데이터를 받을 수 없습니다")
                return False
                
        except Exception as e:
            st.error(f"❌ FRED API 연결 오류: {str(e)}")
            st.error("API 키를 확인하거나 인터넷 연결을 확인해주세요")
            return False
    
    def _fetch_series_data(self, series_id, series_name, start_date, end_date):
        """개별 시리즈 데이터 가져오기"""
        try:
            # 날짜를 문자열로 변환
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            st.write(f"🔍 {series_name} 데이터 요청: {start_str} ~ {end_str}")
            
            series_data = self.fred.get_series(
                series_id,
                start=start_str,
                end=end_str
            )
            
            if series_data is not None and len(series_data) > 0:
                # 요청한 기간으로 필터링
                series_data = series_data.loc[start_date:end_date]
                
                # 월별 데이터로 리샘플링
                series_data = series_data.resample('M').last().dropna()
                
                if len(series_data) > 0:
                    actual_start = series_data.index.min().strftime('%Y-%m-%d')
                    actual_end = series_data.index.max().strftime('%Y-%m-%d')
                    st.write(f"✅ {series_name} 실제 데이터: {actual_start} ~ {actual_end} ({len(series_data)}개)")
                    return series_data
                else:
                    st.warning(f"⚠️ {series_name}: 요청 기간에 데이터가 없습니다")
                    return None
            else:
                st.warning(f"⚠️ {series_name}: FRED에서 데이터를 가져올 수 없습니다")
                return None
                
        except Exception as e:
            st.error(f"❌ {series_name} 데이터 로드 실패: {str(e)}")
            return None
    
    def load_fred_data(self, start_date=None, end_date=None):
        """Load all FRED economic indicators with user-specified date range"""
        # 기본값 설정 (최근 10년)
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=10*365)
        
        # API 연결 테스트
        if not self.connection_tested:
            if not self.test_fred_connection():
                raise Exception("FRED API 연결에 실패했습니다")
        
        try:
            st.info(f"📅 **요청 데이터 수집 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}**")
            
            data_dict = {}
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_indicators = len(self.indicators)
            
            for idx, (name, series_id) in enumerate(self.indicators.items()):
                progress = (idx + 1) / total_indicators
                progress_bar.progress(progress)
                status_text.text(f"📊 {name} 데이터 로딩 중... ({idx + 1}/{total_indicators})")
                
                # 개별 시리즈 데이터 가져오기
                series_data = self._fetch_series_data(series_id, name, start_date, end_date)
                
                if series_data is not None and len(series_data) > 0:
                    data_dict[name] = series_data
                
                # API 호출 간격 조정
                time.sleep(0.3)
            
            progress_bar.progress(1.0)
            status_text.text("✅ 모든 데이터 로딩 완료!")
            
            if not data_dict:
                raise Exception("요청한 기간에 사용 가능한 FRED 데이터가 없습니다")
            
            st.success(f"📊 성공적으로 로드된 지표: {len(data_dict)}개")
            
            # Combine all series into a DataFrame
            fred_df = pd.DataFrame(data_dict)
            
            # 인덱스를 월말로 통일
            fred_df.index = fred_df.index.to_period('M').to_timestamp('M')
            
            # 사용자가 선택한 기간으로 다시 한번 필터링 (확실히 하기 위해)
            mask = (fred_df.index >= start_date) & (fred_df.index <= end_date)
            fred_df = fred_df.loc[mask]
            
            # Forward fill missing values
            fred_df = fred_df.fillna(method='ffill')
            
            # Calculate PDI/CPI ratio if both are available
            if 'PDI' in fred_df.columns and 'CPI' in fred_df.columns:
                # CPI를 100으로 나누어 정규화 (CPI는 보통 100 기준)
                fred_df['PDI/CPI'] = (fred_df['PDI'] / (fred_df['CPI'] / 100))
                st.success("✅ PDI/CPI 비율 계산 완료")
            
            # Calculate percentage changes for some indicators
            pct_change_indicators = ['USD/KRW', 'WTI', 'CPI', 'PPI']
            for indicator in pct_change_indicators:
                if indicator in fred_df.columns:
                    fred_df[f'{indicator}_pct'] = fred_df[indicator].pct_change() * 100
            
            # 최종 데이터 기간 확인
            if len(fred_df) > 0:
                final_start = fred_df.index.min()
                final_end = fred_df.index.max()
                
                # 데이터 품질 체크
                st.subheader("📊 데이터 로딩 결과")
                
                # 요청 vs 실제 데이터 기간 비교
                col1, col2 = st.columns(2)
                
                with col1:
                    st.info(f"""
                    **📅 요청한 기간:**
                    - 시작: {start_date.strftime('%Y-%m-%d')}
                    - 종료: {end_date.strftime('%Y-%m-%d')}
                    - 기간: {(end_date - start_date).days}일
                    """)
                
                with col2:
                    st.success(f"""
                    **📈 실제 데이터 기간:**
                    - 시작: {final_start.strftime('%Y-%m-%d')}
                    - 종료: {final_end.strftime('%Y-%m-%d')}
                    - 포인트: {len(fred_df)}개월
                    """)
                
                # 데이터 요약 통계
                summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                
                with summary_col1:
                    st.metric("총 지표 수", len(fred_df.columns))
                with summary_col2:
                    st.metric("데이터 포인트", len(fred_df))
                with summary_col3:
                    coverage_pct = (len(fred_df) / ((end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1)) * 100
                    st.metric("기간 커버리지", f"{coverage_pct:.1f}%")
                with summary_col4:
                    complete_rows = len(fred_df.dropna())
                    completeness = (complete_rows / len(fred_df)) * 100 if len(fred_df) > 0 else 0
                    st.metric("데이터 완성도", f"{completeness:.1f}%")
                
                # 최신 데이터 표시
                st.subheader("📈 최신 데이터 (최근 5개월)")
                latest_data = fred_df.tail(5)
                st.dataframe(latest_data, use_container_width=True)
                
                # 누락 데이터 체크
                missing_data = fred_df.isnull().sum()
                if missing_data.sum() > 0:
                    st.warning("⚠️ 일부 지표에 누락 데이터가 있습니다:")
                    missing_df = pd.DataFrame({
                        '지표': missing_data.index,
                        '누락 개수': missing_data.values,
                        '누락 비율(%)': (missing_data.values / len(fred_df) * 100).round(1)
                    })
                    missing_df = missing_df[missing_df['누락 개수'] > 0]
                    st.dataframe(missing_df, use_container_width=True)
                else:
                    st.success("✅ 모든 데이터가 완전합니다!")
                
                # 각 지표별 최신 값 표시
                st.subheader("📊 각 지표별 최신 값")
                latest_values = fred_df.iloc[-1]
                
                cols = st.columns(3)
                for idx, (indicator, value) in enumerate(latest_values.items()):
                    col_idx = idx % 3
                    with cols[col_idx]:
                        if pd.notna(value):
                            # 퍼센트 지표는 다르게 표시
                            if '_pct' in indicator:
                                st.metric(indicator, f"{value:.2f}%")
                            elif indicator == 'UNRATE':
                                st.metric(indicator, f"{value:.1f}%")
                            elif indicator in ['USD/KRW', 'WTI', 'US10Y']:
                                st.metric(indicator, f"{value:.2f}")
                            else:
                                st.metric(indicator, f"{value:,.1f}")
                        else:
                            st.metric(indicator, "N/A")
                
                st.success(f"🎉 총 {len(fred_df.columns)}개 지표 로드 완료!")
                
            else:
                st.error("❌ 요청한 기간에 사용 가능한 데이터가 없습니다")
                st.info("다른 기간을 선택해보세요")
            
            # 진행률 바와 상태 텍스트 제거
            progress_bar.empty()
            status_text.empty()
            
            return fred_df
            
        except Exception as e:
            raise Exception(f"FRED 데이터 로드 실패: {str(e)}")
    
    def get_indicator_info(self):
        """경제 지표 정보 반환"""
        indicator_info = {
            'USD/KRW': {'name': '달러-원 환율', 'description': '한국 수출에 직접적 영향을 미치는 환율'},
            'WTI': {'name': '서부텍사스유 가격', 'description': '국제 유가 지표'},
            'US10Y': {'name': '미국 10년 국채금리', 'description': '글로벌 금리 기준'},
            'CPI': {'name': '미국 소비자물가지수', 'description': '인플레이션 지표'},
            'PDI': {'name': '미국 개인가처분소득', 'description': '소비력 지표'},
            'PPI': {'name': '미국 생산자물가지수', 'description': '생산비용 지표'},
            'UNRATE': {'name': '미국 실업률', 'description': '경기 상황 지표'},
            'AUTO_SALES': {'name': '미국 자동차 판매량', 'description': '소비 심리 지표'},
            'AUTO_PROD': {'name': '미국 자동차 생산량', 'description': '제조업 활동 지표'},
            'BDI': {'name': '국제 운임지수', 'description': '글로벌 무역량 지표'},
            'PDI/CPI': {'name': '실질 구매력 지표', 'description': 'PDI를 CPI로 나눈 실질 소득 지표'}
        }
        return indicator_info
    
    def process_export_data(self, uploaded_file, analysis_start_date=None, analysis_end_date=None):
        """Process uploaded Excel file containing export sales data with analysis period filtering"""
        try:
            # Read Excel file
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            else:
                df = pd.read_excel(uploaded_file)
            
            st.info(f"📁 파일 읽기 완료: {len(df)}행 x {len(df.columns)}열")
            
            # 컬럼 정보 표시
            st.subheader("📋 파일 컬럼 정보")
            for i, col in enumerate(df.columns):
                st.text(f"{i+1}. {col}")
            
            # Try to identify date and sales columns
            date_columns = []
            sales_columns = []
            
            for col in df.columns:
                col_lower = str(col).lower()
                
                # Look for date columns
                if any(word in col_lower for word in ['date', 'time', 'month', 'year', 'period', '날짜', '연월']):
                    date_columns.append(col)
                
                # Look for sales/revenue columns
                if any(word in col_lower for word in ['sales', 'revenue', 'export', 'amount', 'value', '매출', '수출', '판매']):
                    sales_columns.append(col)
            
            # If no clear columns found, use first two columns
            if not date_columns and not sales_columns:
                if len(df.columns) >= 2:
                    date_columns = [df.columns[0]]
                    sales_columns = [df.columns[1]]
                else:
                    raise Exception("업로드된 파일에서 날짜와 매출 컬럼을 식별할 수 없습니다")
            
            # Use the first identified columns
            date_col = date_columns[0] if date_columns else df.columns[0]
            sales_col = sales_columns[0] if sales_columns else df.columns[1]
            
            st.info(f"📅 날짜 컬럼: {date_col}")
            st.info(f"💰 매출 컬럼: {sales_col}")
            
            # 샘플 데이터 미리보기
            st.subheader("👀 데이터 미리보기")
            st.dataframe(df[[date_col, sales_col]].head(10))
            
            # Create clean DataFrame
            export_df = pd.DataFrame({
                'Date': pd.to_datetime(df[date_col], errors='coerce'),
                'Export_Sales': pd.to_numeric(df[sales_col], errors='coerce')
            })
            
            # Remove rows with missing values
            before_count = len(export_df)
            export_df = export_df.dropna()
            after_count = len(export_df)
            
            if before_count != after_count:
                st.warning(f"⚠️ {before_count - after_count}개 행이 누락 데이터로 인해 제거되었습니다")
            
            # Set date as index and convert to monthly frequency
            export_df = export_df.set_index('Date')
            export_df = export_df.resample('M').sum()  # Sum if multiple entries per month
            
            # Remove zero or negative values
            before_filter = len(export_df)
            export_df = export_df[export_df['Export_Sales'] > 0]
            after_filter = len(export_df)
            
            if before_filter != after_filter:
                st.warning(f"⚠️ {before_filter - after_filter}개 행이 0 이하 값으로 인해 제거되었습니다")
            
            # 분석 기간 필터링 적용
            if analysis_start_date is not None and analysis_end_date is not None:
                # 날짜를 월 시작일로 변환
                start_filter = pd.Timestamp(analysis_start_date.year, analysis_start_date.month, 1)
                end_filter = pd.Timestamp(analysis_end_date.year, analysis_end_date.month, 1)
                
                st.info(f"📅 **선택된 분석 기간으로 필터링: {start_filter.strftime('%Y-%m')} ~ {end_filter.strftime('%Y-%m')}**")
                
                # 원본 데이터 기간 표시
                original_start = export_df.index.min()
                original_end = export_df.index.max()
                st.info(f"📊 원본 데이터 기간: {original_start.strftime('%Y-%m')} ~ {original_end.strftime('%Y-%m')}")
                
                # 기간 필터링
                before_period_filter = len(export_df)
                export_df = export_df.loc[start_filter:end_filter]
                after_period_filter = len(export_df)
                
                if after_period_filter < before_period_filter:
                    filtered_count = before_period_filter - after_period_filter
                    st.success(f"✅ 분석 기간 필터링 완료: {filtered_count}개 데이터 포인트 제외")
                
                # 필터링 후 데이터 기간 확인
                if len(export_df) > 0:
                    filtered_start = export_df.index.min()
                    filtered_end = export_df.index.max()
                    st.success(f"📈 **필터링된 데이터 기간: {filtered_start.strftime('%Y-%m')} ~ {filtered_end.strftime('%Y-%m')}**")
                else:
                    st.error("❌ 선택된 분석 기간에 해당하는 데이터가 없습니다")
                    st.info("다른 분석 기간을 선택하거나 데이터를 확인해주세요")
                    return None
            
            if len(export_df) == 0:
                raise Exception("처리 후 유효한 수출 매출 데이터가 없습니다")
            
            # 최종 결과 표시
            st.success(f"✅ 수출 데이터 처리 완료: {len(export_df)}개 데이터 포인트")
            
            if analysis_start_date is not None and analysis_end_date is not None:
                st.info(f"📅 **최종 분석 데이터 기간: {export_df.index.min().strftime('%Y-%m')} ~ {export_df.index.max().strftime('%Y-%m')}**")
            else:
                st.info(f"📅 데이터 기간: {export_df.index.min().strftime('%Y-%m')} ~ {export_df.index.max().strftime('%Y-%m')}")
            
            # 데이터 요약 통계
            st.subheader("📊 처리된 데이터 요약")
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            
            with summary_col1:
                st.metric("총 데이터 포인트", len(export_df))
            with summary_col2:
                st.metric("평균 매출", f"{export_df['Export_Sales'].mean():,.0f}")
            with summary_col3:
                st.metric("최대 매출", f"{export_df['Export_Sales'].max():,.0f}")
            with summary_col4:
                st.metric("최소 매출", f"{export_df['Export_Sales'].min():,.0f}")
            
            return export_df
            
        except Exception as e:
            raise Exception(f"수출 데이터 처리 실패: {str(e)}")
    
    def align_datasets(self, fred_data, export_data):
        """Align FRED and export data by date"""
        try:
            # Find common date range
            start_date = max(fred_data.index.min(), export_data.index.min())
            end_date = min(fred_data.index.max(), export_data.index.max())
            
            st.info(f"📅 공통 데이터 기간: {start_date.strftime('%Y-%m')} ~ {end_date.strftime('%Y-%m')}")
            
            # Filter both datasets to common range
            fred_aligned = fred_data.loc[start_date:end_date]
            export_aligned = export_data.loc[start_date:end_date]
            
            # Combine datasets
            combined_data = pd.concat([fred_aligned, export_aligned], axis=1)
            
            # Drop rows with any missing values
            before_dropna = len(combined_data)
            combined_data = combined_data.dropna()
            after_dropna = len(combined_data)
            
            if before_dropna != after_dropna:
                st.warning(f"⚠️ {before_dropna - after_dropna}개 행이 누락 데이터로 인해 제거되었습니다")
            
            if len(combined_data) == 0:
                raise Exception("FRED 데이터와 수출 데이터 간 겹치는 기간이 없습니다")
            
            st.success(f"✅ 데이터 정렬 완료: {len(combined_data)}개 데이터 포인트")
            return combined_data
            
        except Exception as e:
            raise Exception(f"데이터 정렬 실패: {str(e)}")
