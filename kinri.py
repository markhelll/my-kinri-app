import streamlit as st
import pandas as pd
import altair as alt

# ==========================================
# 👇 スプレッドシートのURL（そのままでOK）
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8hJRst-sZ2V_rzHW77OK5NBbDGRwJ8O7bYNoofq2l7gtqE8ZzPSUq39xPI4IDp4-q1NXdapzo-hZE/pub?output=csv"
# ==========================================

st.set_page_config(page_title="My金利ウォッチ", page_icon="🏦", layout="wide")

# --- データの読み込みと日本語化 ---
@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(CSV_URL)
        if df.empty: return None
        df['Date'] = pd.to_datetime(df['Date'])
        
        # ★ここで列名を日本語に変換します！
        # (グラフの凡例もこれに合わせて自動で変わります)
        df = df.rename(columns={
            'BOJ': '日銀',
            'MUFG': 'UFJ',
            'Yokohama': '横浜',
            'Johoku': '城北'
        })
        return df
    except Exception:
        return None

df = load_data()

# --- サイドバー設定 ---
st.sidebar.header("⚙️ 設定")

if st.sidebar.button("🔄 データを強制更新"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()

if df is not None and not df.empty:
    st.sidebar.subheader("💰 My金利シミュレーション")
    
    # ★デフォルトを「横浜」に変更
    # リストの順番を変えて、横浜を一番上にしました
    bank_options = ["横浜", "UFJ", "城北"]
    
    my_bank = st.sidebar.selectbox(
        "借りている銀行",
        bank_options,
        index=0  # 0番目（つまり横浜）をデフォルトにする
    )

    # 優遇幅
    discount_rate = st.sidebar.number_input(
        "優遇幅 (マイナス分 %)",
        min_value=0.0, max_value=3.0, value=1.85, step=0.01, format="%.2f"
    )
    
    st.sidebar.caption(f"適用金利 = {my_bank}店頭 - {discount_rate}%")

# --- メイン画面 ---
st.title("🏦 My金利ウォッチ (Pro)")

if df is None or df.empty:
    st.error("⚠️ データが読み込めませんでした。URLを確認してください。")
else:
    df_sorted = df.sort_values('Date')
    latest = df_sorted.iloc[-1]
    
    # My金利計算
    current_store_rate = latest[my_bank]
    my_real_rate = max(0, current_store_rate - discount_rate)

    # --- 1. 最新ステータス (日本語表記) ---
    st.markdown(f"### 📊 現在の金利状況 ({latest['Date'].strftime('%Y/%m/%d')} 時点)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # My金利
    col1.metric("🏠 あなたの金利", f"{my_real_rate:.3f}%", delta_color="inverse")
    
    # 各銀行のレート（日本語列名でアクセス）
    col2.metric("日銀 (政策)", f"{latest['日銀']}%")
    col3.metric(f"{my_bank} (店頭)", f"{current_store_rate}%")
    
    # 他行平均の計算も日本語列名で
    avg_rate = (latest['UFJ'] + latest['横浜']) / 2
    col4.metric("大手平均", f"{avg_rate:.2f}%")

    st.divider()

    # --- 2. チャート ---
    st.sidebar.divider()
    st.sidebar.header("📈 チャート設定")
    timeframe = st.sidebar.radio("期間（足）", ["分足", "日足", "週足", "年足"], index=1)

    # データ加工
    df_indexed = df_sorted.set_index('Date')
    df_chart_source = df_indexed.copy()
    
    if "週足" in timeframe:
        df_display = df_chart_source.resample('W').last().reset_index()
    elif "年足" in timeframe:
        df_display = df_chart_source.resample('A').last().reset_index()
    elif "分足" in timeframe:
        df_display = df_sorted.copy()
    else:
        df_display = df_chart_source.resample('D').last().dropna().reset_index()

    # My金利データの作成
    chart_data = df_display.melt('Date', var_name='Bank', value_name='Rate')
    
    my_rate_data = df_display[['Date', my_bank]].copy()
    my_rate_data['Rate'] = my_rate_data[my_bank] - discount_rate
    my_rate_data['Rate'] = my_rate_data['Rate'].apply(lambda x: max(0, x))
    my_rate_data['Bank'] = "★My金利"
    
    final_chart_data = pd.concat([chart_data, my_rate_data[['Date', 'Bank', 'Rate']]])

    st.subheader(f"📈 金利推移チャート")
    
    # チャート描画（凡例も自動的に日本語になります）
    base = alt.Chart(final_chart_data).encode(
        x=alt.X('Date:T', title='日付'),
        y=alt.Y('Rate:Q', title='金利 (%)'),
        tooltip=['Date', 'Bank', 'Rate']
    )

    lines = base.mark_line(interpolate='step-after', point=True).encode(
        color=alt.Color('Bank:N', title='銀行名'), # 凡例タイトル
        strokeDash=alt.condition(
            alt.datum.Bank == '★My金利',
            alt.value([0]),
            alt.value([4, 2])
        ),
        strokeWidth=alt.condition(
            alt.datum.Bank == '★My金利',
            alt.value(4),
            alt.value(1.5)
        )
    ).interactive()

    st.altair_chart(lines, use_container_width=True)
    
    # --- 3. 履歴リスト ---
    with st.expander("詳細データを見る"):
        st.dataframe(df_sorted.set_index('Date').sort_index(ascending=False))
