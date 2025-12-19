import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime, timedelta
import numpy as np

# --- 1. データベース設定 ---
DB_NAME = 'lending_rates.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rates
                 (date TEXT, bank_name TEXT, rate REAL, UNIQUE(date, bank_name))''')
    conn.commit()
    conn.close()

# --- 2. 過去1年分のデータを生成（初回のみ） ---
def seed_initial_data():
    conn = sqlite3.connect(DB_NAME)
    df_check = pd.read_sql_query("SELECT count(*) as count FROM rates", conn)
    
    if df_check['count'][0] == 0:
        st.info("初回起動：過去1年分の借入金利データを生成中...")
        start_date = datetime.now() - timedelta(days=365)
        
        banks = {
            "日銀(基準)": 1.475,
            "三菱UFJ(変動)": 0.345,
            "横浜銀行(変動)": 0.425,
            "城北信用金庫(変動)": 0.625
        }
        
        initial_records = []
        for i in range(366):
            current_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            for bank, base_rate in banks.items():
                noise = np.random.normal(0, 0.002)
                trend = (i * 0.0001) if "日銀" not in bank else 0
                rate = max(0.1, base_rate + trend + noise)
                initial_records.append((current_date, bank, round(rate, 3)))
        
        c = conn.cursor()
        c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", initial_records)
        conn.commit()
    conn.close()

# --- 3. 最新金利取得（ダミー） ---
def fetch_latest_rates():
    today = datetime.now().strftime('%Y-%m-%d')
    results = [
        (today, "日銀(基準)", 1.475),
        (today, "三菱UFJ(変動)", 0.450),
        (today, "横浜銀行(変動)", 0.435),
        (today, "城北信用金庫(変動)", 0.630)
    ]
    return results

# --- 4. メインアプリ ---
def main():
    st.set_page_config(page_title="金利チャート（1年）", layout="wide")
    st.title("💸 銀行借入金利 推移チャート")
    
    init_db()
    seed_initial_data()

    # --- サイドバー ---
    with st.sidebar:
        st.header("設定")
        
        if st.button("最新レートを取得"):
            new_data = fetch_latest_rates()
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", new_data)
            conn.commit()
            conn.close()
            st.success("データを更新しました")
            
        st.divider()
        # 【変更点】最小値を7、デフォルト値を7に変更しました
        view_days = st.slider("表示期間（過去何日分）", 7, 365, 7)
        
        st.divider()
        time_unit = st.radio("表示単位", ["日足", "週足", "月足", "年足"])
        st.caption("※チャート上をダブルクリックでリセット、左クリックドラッグで拡大できます。")

    # データ読み込み
    conn = sqlite3.connect(DB_NAME)
    cutoff = (datetime.now() - timedelta(days=view_days)).strftime('%Y-%m-%d')
    query = f"SELECT * FROM rates WHERE date >= '{cutoff}' ORDER BY date ASC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'])

    # --- 時間軸の切り替え ---
    if time_unit == "週足":
        df = df.groupby('bank_name').resample('W', on='date').mean().reset_index()
    elif time_unit == "月足":
        df = df.groupby('bank_name').resample('M', on='date').mean().reset_index()
    elif time_unit == "年足":
        df = df.groupby('bank_name').resample('Y', on='date').mean().reset_index()

    # --- チャート描画 ---
    if not df.empty:
        fig = px.line(df, x="date", y="rate", color="bank_name",
                      title=f"借入金利の推移（過去{view_days}日・{time_unit}）",
                      labels={"rate": "金利 (%)", "date": "日付", "bank_name": "金融機関"},
                      template="plotly_dark")

        fig.update_layout(
            hovermode='x unified',
            yaxis=dict(title="金利 (%)"),
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=7, label="1週間", step="day", stepmode="backward"), # 7日ボタンを追加
                        dict(count=1, label="1ヶ月", step="month", stepmode="backward"),
                        dict(count=3, label="3ヶ月", step="month", stepmode="backward"),
                        dict(step="all", label="全期間")
                    ])
                ),
                rangeslider=dict(visible=True),
                type="date"
            )
        )
        
        fig.update_traces(line=dict(width=3))
        st.plotly_chart(fig, use_container_width=True)

        # 最新値テーブル
        st.subheader("現在の金利一覧")
        latest_df = df.sort_values('date').groupby('bank_name').tail(1)[['bank_name', 'rate']]
        latest_df = latest_df.set_index('bank_name')
        st.table(latest_df.style.format("{:.3f}%"))
            
    else:
        st.error("データがありません。")

if __name__ == "__main__":
    main()