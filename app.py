import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import plotly.express as px

# --- 1. 設定・接続 (Secretsから読み込む安全な方法) ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    st.error("Supabaseのキー設定が見つかりません。StreamlitのSecretsを設定してください。")
    st.stop()

@st.cache_resource
def init_connection():
    return create_client(url, key)

supabase = init_connection()

st.set_page_config(page_title="みんなの家計簿", page_icon="💰", layout="wide")

# --- 2. ログイン機能 ---
def login():
    st.title("🔐 ログイン")
    username = st.text_input("ユーザー名を入力してください（例: yamada）")
    if st.button("利用開始"):
        if username:
            st.session_state['user_id'] = username
            st.rerun()

if 'user_id' not in st.session_state:
    login()
    st.stop()

user_id = st.session_state['user_id']

# --- 3. サイドバー（入力） ---
with st.sidebar:
    st.write(f"👤 User: **{user_id}**")
    if st.button("ログアウト"):
        del st.session_state['user_id']
        st.rerun()
    st.divider()
    st.header("✏️ 入力")

    # カテゴリ取得
    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
        category_list.append("➕ 新しいカテゴリを追加...")
    except:
        category_list = ["食費", "その他"] # エラー時の予備

    with st.form("input_form"):
        date = st.date_input("日付", datetime.date.today())
        selected_cat = st.selectbox("カテゴリ", category_list)
        
        if selected_cat == "➕ 新しいカテゴリを追加...":
            st.info("下のメモ欄に新カテゴリ名を入力して保存してください")
            
        memo = st.text_input("メモ・店名", placeholder="例: コンビニ, 新カテゴリ名")
        amount = st.number_input("金額", min_value=0, step=100)
        submitted = st.form_submit_button("記録する")
        
        if submitted:
            final_category = selected_cat
            # カテゴリ追加処理
            if selected_cat == "➕ 新しいカテゴリを追加...":
                if memo:
                    final_category = memo
                    try:
                        supabase.table('categories').insert({"name": final_category}).execute()
                        st.toast(f"カテゴリ「{final_category}」を追加！")
                    except:
                        pass
                else:
                    st.error("新カテゴリ名を入力してください")
                    st.stop()

            # 保存処理
            data = {"user_id": user_id, "date": str(date), "category": final_category, "memo": memo, "amount": amount}
            supabase.table("receipts").insert(data).execute()
            st.success("保存しました！")

# --- 4. メイン画面（分析） ---
st.title("💰 家計簿ダッシュボード")

# データ取得
response = supabase.table('receipts').select("*").eq('user_id', user_id).order('date', desc=True).execute()
df = pd.DataFrame(response.data)

if not df.empty:
    df['date'] = pd.to_datetime(df['date'])
    
    # KPI
    col1, col2, col3 = st.columns(3)
    current_month = datetime.date.today().strftime("%Y-%m")
    df_this_month = df[df['date'].dt.strftime('%Y-%m') == current_month]
    
    col1.metric("今月の出費", f"¥{df_this_month['amount'].sum():,}")
    col2.metric("全期間の出費", f"¥{df['amount'].sum():,}")
    col3.metric("記録数", f"{len(df)} 件")
    
    st.divider()
    
    # グラフ
    tab1, tab2 = st.tabs(["📊 カテゴリ分析", "📝 履歴一覧"])
    
    with tab1:
        if not df_this_month.empty:
            st.subheader("今月のカテゴリ割合")
            fig = px.pie(df_this_month, values='amount', names='category')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("今月のデータがまだありません")
            
    with tab2:
        st.dataframe(df[['date', 'category', 'memo', 'amount']], use_container_width=True)
else:
    st.info("データがありません。左のサイドバーから入力してください。")