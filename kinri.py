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

# --- 2. 過去1年分の初期データを生成（1年前までのログに変更） ---
def seed_initial_data():
    conn = sqlite3.connect(DB_NAME)
    df_check = pd.read_sql_query("SELECT count(*) as count FROM rates", conn)
    
    # データが空の場合のみ、過去365日分を作成
    if df_check['count'][0] == 0:
        st.info("初期データを生成中（過去1年分）...")
        start_date = datetime.now() - timedelta(days=365)
        banks = {"日銀": 0.1, "三菱UFJ": 0.001, "横浜銀行": 0.002, "城北信用金庫": 0.01}
        
        initial_records = []
        for i in range(366):
            current_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            for bank, base_rate in banks.items():
                # 1年分なので、少し動きをリアルにするためのノイズ
                noise = np.random.normal(0, 0.0005)
                rate = max(0, base_rate + (i * 0.00002) + noise)
                initial_records.append((current_date, bank, round(rate, 4)))
        
        c = conn.cursor()
        c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", initial_records)
        conn.commit()
    conn.close()

# --- 3. メインアプリ ---
def main():
    st.set_page_config(page_title="金利チャート・プロ", layout="wide")
    st.title("📈 金利推移折れ線チャート（過去1年ログ）")
    
    init_db()
    seed_initial_data()

    # --- サイドバー設定 ---
    with st.sidebar:
        st.header("表示オプション")
        time_unit = st.radio("時間軸を切り替え", ["日足", "週足", "月足"])
        st.divider()
        st.write("操作ヘルプ:")
        st.write("・左ドラッグ：拡大")
        st.write("・ダブルクリック：元に戻す")

    # データの読み込み
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM rates ORDER BY date ASC", conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'])

    # 時間軸のリサンプリング（切り替え機能）
    if time_unit == "週足":
        df = df.groupby('bank_name').resample('W', on='date').mean().reset_index()
    elif time_unit == "月足":
        df = df.groupby('bank_name').resample('M', on='date').mean().reset_index()

    # --- 4. チャート作成（折れ線に変更） ---
    if not df.empty:
        st.subheader(f"金融機関別 金利比較（{time_unit}・折れ線）")
        
        # px.line で折れ線チャートを作成
        fig = px.line(df, x="date", y="rate", color="bank_name",
                      labels={"rate": "金利 (%)", "date": "日付", "bank_name": "金融機関"},
                      markers=True, # 点を表示して見やすくする
                      color_discrete_sequence=px.colors.qualitative.Bold,
                      template="plotly_white")

        # インタラクティブ設定の強化
        fig.update_layout(
            hovermode='x unified',
            xaxis=dict(
                rangeslider=dict(visible=True), # 下部にスライダー
                type="date"
            ),
            yaxis=dict(fixedrange=False) # Y軸のズームも有効化
        )
        
        # グラフを表示
        st.plotly_chart(fig, use_container_width=True)

        # 最新値のサマリー
        st.divider()
        latest = df.sort_values('date').groupby('bank_name').tail(1)
        cols = st.columns(4)
        for i, row in enumerate(latest.itertuples()):
            cols[i].metric(row.bank_name, f"{row.rate:.4f}%")
    else:
        st.error("表示するデータがありません。")

if __name__ == "__main__":
    main()