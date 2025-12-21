import streamlit as st
import pandas as pd
import altair as alt

# ==========================================
# 👇 スプレッドシートのURL（ここは変えないでOK！）
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8hJRst-sZ2V_rzHW77OK5NBbDGRwJ8O7bYNoofq2l7gtqE8ZzPSUq39xPI4IDp4-q1NXdapzo-hZE/pub?output=csv"
# ==========================================

st.set_page_config(page_title="My金利ウォッチ", page_icon="🏦", layout="wide")

# --- サイドバー：設定エリア ---
st.sidebar.header("⚙️ 設定")

if st.sidebar.button("🔄 データを強制更新"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()

# ★新機能：リアル金利シミュレーター
st.sidebar.subheader("💰 My金利シミュレーション")
st.sidebar.caption("あなたの契約内容を入力してください")

# 1. 銀行を選ぶ
my_bank = st.sidebar.selectbox(
    "借りている銀行",
    ["三菱UFJ", "横浜銀行", "城北信用金庫"],
    index=0
)

# 2. 優遇幅を入力する (例: 1.85%)
discount_rate = st.sidebar.number_input(
    "優遇幅 (マイナス分 %)",
    min_value=0.0,
    max_value=3.0,
    value=1.85,
    step=0.01,
    format="%.2f"
)

st.sidebar.info(f"あなたの適用金利 = 店頭金利 - {discount_rate}%")

# --- メイン画面 ---
st.title("🏦 My金利ウォッチ (Pro)")

@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(CSV_URL)
        if df.empty: return None
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception:
        return None

df = load_data()

if df is None or df.empty:
    st.error("⚠️ データが読み込めませんでした。")
else:
    df_sorted = df.sort_values('Date')
    latest = df_sorted.iloc[-1]
    
    # マッピング用辞書 (CSVの列名 -> 表示名)
    bank_map = {
        "三菱UFJ": "MUFG",
        "横浜銀行": "Yokohama",
        "城北信用金庫": "Johoku"
    }
    target_col = bank_map[my_bank]
    
    # ★My金利の計算
    current_store_rate = latest[target_col]
    my_real_rate = max(0, current_store_rate - discount_rate)

    # --- 1. 最新ステータス (My金利を強調！) ---
    st.markdown(f"### 📊 現在の金利状況 ({latest['Date'].strftime('%Y/%m/%d')} 時点)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # My金利を一番左にドーンと表示
    col1.metric("🏠 あなたの支払金利", f"{my_real_rate:.3f}%", help=f"{my_bank}店頭 {current_store_rate}% - 優遇 {discount_rate}%")
    
    col2.metric("日銀政策金利", f"{latest['BOJ']}%")
    col3.metric(f"{my_bank} (店頭)", f"{current_store_rate}%")
    col4.metric("他行平均 (参考)", f"{(latest['MUFG']+latest['Yokohama'])/2:.2f}%")

    st.divider()

    # --- 2. チャート ---
    st.sidebar.divider()
    st.sidebar.header("📈 チャート設定")
    timeframe = st.sidebar.radio("期間（足）", ["分足", "日足", "週足", "年足"], index=1)

    # データの加工
    df_indexed = df_sorted.set_index('Date')
    
    # My金利列を追加計算！
    # 全行に対して「その銀行の店頭金利 - 優遇幅」を計算
    df_chart_source = df_indexed.copy()
    if "週足" in timeframe:
        df_display = df_chart_source.resample('W').last().reset_index()
    elif "年足" in timeframe:
        df_display = df_chart_source.resample('A').last().reset_index()
    elif "分足" in timeframe:
        df_display = df_sorted.copy()
    else:
        df_display = df_chart_source.resample('D').last().dropna().reset_index()

    # チャート用のデータ作成
    # 1. まず既存の銀行データを縦持ちに変換
    chart_data = df_display.melt('Date', var_name='Bank', value_name='Rate')
    
    # 2. My金利のデータを計算して追加
    # 選ばれた銀行のデータだけ抜き出して計算
    my_rate_data = df_display[['Date', target_col]].copy()
    my_rate_data['Rate'] = my_rate_data[target_col] - discount_rate
    my_rate_data['Rate'] = my_rate_data['Rate'].apply(lambda x: max(0, x)) # 0%未満にはしない
    my_rate_data['Bank'] = "★My金利" # 特別な名前をつける
    
    # 結合 (通常の銀行データ + My金利データ)
    final_chart_data = pd.concat([chart_data, my_rate_data[['Date', 'Bank', 'Rate']]])

    st.subheader(f"📈 金利推移チャート (My金利付き)")
    
    # チャート描画
    # My金利だけ太く赤くする設定
    base = alt.Chart(final_chart_data).encode(
        x=alt.X('Date:T', title='日付'),
        y=alt.Y('Rate:Q', title='金利 (%)'),
        tooltip=['Date', 'Bank', 'Rate']
    )

    # 通常の線
    lines = base.mark_line(interpolate='step-after', point=True).encode(
        color=alt.Color('Bank:N', title='凡例'),
        strokeDash=alt.condition(
            alt.datum.Bank == '★My金利',
            alt.value([0]),  # 実線
            alt.value([4, 2]) # 他は点線っぽくして区別
        ),
        strokeWidth=alt.condition(
            alt.datum.Bank == '★My金利',
            alt.value(4),    # My金利は太く
            alt.value(1.5)   # 他は細く
        )
    ).interactive()

    st.altair_chart(lines, use_container_width=True)
    
    # --- 3. 履歴リスト ---
    with st.expander("詳細データを見る"):
        st.dataframe(df_sorted.set_index('Date').sort_index(ascending=False))
