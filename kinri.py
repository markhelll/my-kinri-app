import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime, timedelta
import numpy as np

# --- 1. データベース設定 ---
DB_NAME = 'financial_rates.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rates
                 (date TEXT, bank_name TEXT, rate REAL, UNIQUE(date, bank_name))''')
    conn.commit()
    conn.close()

# --- 2. 過去5年分のダミーデータ生成（初回のみ） ---
def seed_initial_data():
    conn = sqlite3.connect(DB_NAME)
    df_check = pd.read_sql_query("SELECT count(*) as count FROM rates", conn)
    if df_check['count'][0] == 0:
        start_date = datetime.now() - timedelta(days=1825)
        banks = {"日銀": 0.1, "三菱UFJ": 0.001, "横浜銀行": 0.002, "城北信用金庫": 0.01}
        initial_records = []
        for i in range(1826):
            current_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            for bank, base_rate in banks.items():
                noise = np.random.normal(0, 0.001)
                rate = max(0, base_rate + (i * 0.00008) + noise)
                initial_records.append((current_date, bank, round(rate, 4)))
        c = conn.cursor()
        c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", initial_records)
        conn.commit()
    conn.close()

# --- 3. メインアプリ ---
def main():
    st.set_page_config(page_title="金利プロ・トラッカー", layout="wide")
    st.title("🏦 金利推移マルチチャート（日・週・月・年）")
    
    init_db()
    seed_initial_data()

    # --- サイドバー設定 ---
    with st.sidebar:
        st.header("表示オプション")
        time_unit = st.radio("時間軸を切り替え", ["日足", "週足", "月足", "年足"])
        st.info("💡 チャート上を左クリックでドラッグすると拡大、ダブルクリックで元のサイズに戻ります。")

    # データの読み込み
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM rates ORDER BY date ASC", conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'])

    # --- 時間軸のリサンプリング処理 ---
    if time_unit == "週足":
        df = df.groupby('bank_name').resample('W', on='date').mean().reset_index()
    elif time_unit == "月足":
        df = df.groupby('bank_name').resample('M', on='date').mean().reset_index()
    elif time_unit == "年足":
        df = df.groupby('bank_name').resample('Y', on='date').mean().reset_index()

    # --- チャート作成 ---
    if not df.empty:
        st.subheader(f"金利推移（{time_unit}・累積型）")
        
        # 累積型エリアチャート
        fig = px.area(df, x="date", y="rate", color="bank_name",
                      labels={"rate": "金利 (%)", "date": "期間"},
                      color_discrete_sequence=px.colors.qualitative.Vivid,
                      template="plotly_dark") # 視認性の高いダークテーマ

        # インタラクティブ設定（拡大・戻す操作の最適化）
        fig.update_layout(
            dragmode='zoom', # デフォルトで拡大モード
            hovermode='x unified',
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1ヶ月", step="month", stepmode="backward"),
                        dict(count=6, label="6ヶ月", step="month", stepmode="backward"),
                        dict(count=1, label="1年", step="year", stepmode="backward"),
                        dict(step="all", label="全期間")
                    ])
                ),
                rangeslider=dict(visible=True), # 下部にスライダーを表示
                type="date"
            )
        )
        
        # グラフを表示
        st.plotly_chart(fig, use_container_width=True)

        # 最新データのサマリー
        st.divider()
        latest = df.sort_values('date').groupby('bank_name').tail(1)
        cols = st.columns(4)
        for i, row in enumerate(latest.itertuples()):
            cols[i].metric(row.bank_name, f"{row.rate:.4f}%")

if __name__ == "__main__":
    main()