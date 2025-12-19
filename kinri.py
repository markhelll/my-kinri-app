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

# --- 2. 過去1年分（今日から365日前まで）のデータを生成 ---
def seed_initial_data():
    conn = sqlite3.connect(DB_NAME)
    # 一旦データをリセットして、確実に1年分にする場合は以下のコメントアウトを外してね
    # c.execute("DELETE FROM rates") 
    
    df_check = pd.read_sql_query("SELECT count(*) as count FROM rates", conn)
    
    if df_check['count'][0] == 0:
        st.info("初期データを生成中（過去365日分）...")
        # 【重要】今日から365日引いた日を開始日に設定
        start_date = datetime.now() - timedelta(days=365)
        banks = {"日銀": 0.1, "三菱UFJ": 0.001, "横浜銀行": 0.002, "城北信用金庫": 0.01}
        
        initial_records = []
        for i in range(366): # 365日 + 今日
            current_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            for bank, base_rate in banks.items():
                noise = np.random.normal(0, 0.0003)
                # ゆるやかに右肩上がりにしつつノイズを入れる
                rate = max(0, base_rate + (i * 0.000015) + noise)
                initial_records.append((current_date, bank, round(rate, 4)))
        
        c = conn.cursor()
        c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", initial_records)
        conn.commit()
    conn.close()

# --- 3. メインアプリ ---
def main():
    st.set_page_config(page_title="金利チャート・1年ログ", layout="wide")
    st.title("📈 金利推移：日足・週足チャート（直近1年）")
    
    init_db()
    seed_initial_data()

    # --- サイドバー：メニューを日足と週足だけに絞る ---
    with st.sidebar:
        st.header("表示設定")
        time_unit = st.radio("表示スパンを切り替え", ["日足", "週足"])
        st.divider()
        st.write("【操作ガイド】")
        st.write("・左クリックドラッグ：拡大")
        st.write("・ダブルクリック：リセット")

    # データの読み込み
    conn = sqlite3.connect(DB_NAME)
    # SQLでも1年間に絞って取得
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    df = pd.read_sql_query(f"SELECT * FROM rates WHERE date >= '{one_year_ago}' ORDER BY date ASC", conn)
    conn.close()
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])

        # 時間軸のリサンプリング（日足 or 週足）
        if time_unit == "週足":
            # 週の平均値を計算
            df = df.groupby('bank_name').resample('W', on='date').mean().reset_index()

        # --- 4. 折れ線チャート作成 ---
        st.subheader(f"各行の金利比較（{time_unit}）")
        
        fig = px.line(df, x="date", y="rate", color="bank_name",
                      labels={"rate": "金利 (%)", "date": "日付", "bank_name": "銀行名"},
                      markers=(True if time_unit == "週足" else False), # 週足の時は点を目立たせる
                      color_discrete_sequence=px.colors.qualitative.Dark2,
                      template="plotly_white")

        fig.update_layout(
            hovermode='x unified',
            xaxis=dict(
                rangeslider=dict(visible=True), # 下のスライダーで1年分を自由に移動
                type="date"
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # 最新値サマリー
        st.divider()
        latest = df.sort_values('date').groupby('bank_name').tail(1)
        cols = st.columns(4)
        for i, row in enumerate(latest.itertuples()):
            cols[i].metric(row.bank_name, f"{row.rate:.4f}%")
    else:
        st.warning("表示期間内（過去1年）にデータが見つかりませんでした。")

if __name__ == "__main__":
    main()