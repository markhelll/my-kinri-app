import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime, timedelta
import numpy as np

# --- 1. データベース設定 ---
DB_NAME = 'lending_rates.db' # 借入用(Lending)にDB名を変更

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rates
                 (date TEXT, bank_name TEXT, rate REAL, UNIQUE(date, bank_name))''')
    conn.commit()
    conn.close()

# --- 2. 過去5年分の借入金利データを生成（初回のみ） ---
def seed_initial_data():
    conn = sqlite3.connect(DB_NAME)
    df_check = pd.read_sql_query("SELECT count(*) as count FROM rates", conn)
    
    # データがない場合のみ生成
    if df_check['count'][0] == 0:
        st.info("初回起動：過去5年分の借入金利データ（ダミー）を生成中...")
        start_date = datetime.now() - timedelta(days=1825)
        
        # 借入金利の想定値（単位：％）
        # ※変動金利や短期プライムレートをイメージ
        banks = {
            "日銀(基準)": 1.475,       # 短期プライムレート基準などを想定
            "三菱UFJ(変動)": 0.345,    # ネット優遇などを想定した低い金利
            "横浜銀行(変動)": 0.425,   # 地銀の標準的な変動金利
            "城北信用金庫(変動)": 0.625 # 信金の標準的な金利
        }
        
        initial_records = []
        for i in range(1826):
            current_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            for bank, base_rate in banks.items():
                # 借入金利らしい「あまり動かないが、たまに動く」動きとノイズ
                noise = np.random.normal(0, 0.002)
                # 5年間で少しずつ上昇傾向にあるシナリオ
                trend = (i * 0.00005) 
                rate = max(0.1, base_rate + trend + noise)
                initial_records.append((current_date, bank, round(rate, 3)))
        
        c = conn.cursor()
        c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", initial_records)
        conn.commit()
    conn.close()

# --- 3. 最新金利取得（ダミー） ---
def fetch_latest_lending_rates():
    today = datetime.now().strftime('%Y-%m-%d')
    # 実際のサイトから取る場合はここをスクレイピング処理にする
    # 今回は借入金利としてのサンプル値を返却
    results = [
        (today, "日銀(基準)", 1.475),
        (today, "三菱UFJ(変動)", 0.345),
        (today, "横浜銀行(変動)", 0.425),
        (today, "城北信用金庫(変動)", 0.625)
    ]
    return results

# --- 4. メインアプリ ---
def main():
    st.set_page_config(page_title="借入金利チェッカー", layout="wide")
    st.title("💸 銀行借入金利 比較・推移トラッカー")
    
    init_db()
    seed_initial_data()

    # --- サイドバー設定 ---
    with st.sidebar:
        st.header("表示設定")
        st.write("住宅ローン変動金利・事業融資などの推移")
        
        # 更新ボタン
        if st.button("最新レートを取得"):
            new_data = fetch_latest_lending_rates()
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.executemany("INSERT OR IGNORE INTO rates VALUES (?,?,?)", new_data)
            conn.commit()
            conn.close()
            st.success("最新の金利情報を取得しました")
            
        st.divider()
        time_unit = st.radio("期間の粒度", ["日足", "週足", "月足", "年足"])
        st.info("👆 ダブルクリックでチャートのズームをリセットできます。")

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
        # A. 比較しやすいラインチャート（借入は「低さ」を比べたいため、こちらをメインに推奨しますが、ご希望のエリアも下に配置します）
        st.subheader(f"金利推移比較（{time_unit}）")
        
        # エリアチャート（累積的な視覚効果）
        # ※注: 借入金利の場合、積み上げ(stack)だと合計値になってしまうため、
        # 重なり(overlay)で見えるように調整するか、そのままデザインとしてStackさせるか選べます。
        # ここではご要望通り「累積型（積み上げエリア）」で表示します。
        fig = px.area(df, x="date", y="rate", color="bank_name",
                      labels={"rate": "金利 (%)", "date": "期間"},
                      title="借入金利のボリューム推移",
                      template="plotly_dark")

        # インタラクティブ設定
        fig.update_layout(
            dragmode='zoom', 
            hovermode='x unified',
            yaxis_title="金利 (%)",
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1ヶ月", step="month", stepmode="backward"),
                        dict(count=6, label="6ヶ月", step="month", stepmode="backward"),
                        dict(count=1, label="1年", step="year", stepmode="backward"),
                        dict(step="all", label="全期間")
                    ])
                ),
                rangeslider=dict(visible=True),
                type="date"
            )
        )
        st.plotly_chart(fig, use_container_width=True)

        # B. 最新レートの確認
        st.subheader("現在のお借入目安金利")
        latest = df.sort_values('date').groupby('bank_name').tail(1)
        
        # カード形式で表示
        cols = st.columns(4)
        for i, row in enumerate(latest.itertuples()):
            cols[i].metric(
                label=row.bank_name,
                value=f"{row.rate:.3f}%",
                delta="前日比なし" # 本来はここで前日差分を計算して表示できます
            )
            
    else:
        st.error("データがありません。")

if __name__ == "__main__":
    main()