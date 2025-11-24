import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import plotly.express as px

# ==========================================
# ⚙️ 設定エリア
# ==========================================

# ★ここにあなたのユーザー名を入れると、そのアカウントだけ全員のデータが見えるようになります
ADMIN_USER = "hyoto" 

# ==========================================
# 🔌 データベース接続
# ==========================================
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

# ==========================================
# 🔐 ログイン・新規登録機能
# ==========================================
def login():
    st.title("🔐 家計簿アプリ")
    
    # タブで切り替え
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])

    # --- 既存ユーザーログイン ---
    with tab1:
        st.subheader("ログイン")
        l_user = st.text_input("ユーザー名", key="login_user")
        l_pass = st.text_input("パスワード", type="password", key="login_pass")
        
        if st.button("ログインする", key="login_btn"):
            if not l_user or not l_pass:
                st.error("ユーザー名とパスワードを入力してください")
            else:
                try:
                    # ユーザーテーブルから検索
                    res = supabase.table('users').select("*").eq('username', l_user).eq('password', l_pass).execute()
                    if len(res.data) > 0:
                        st.session_state['user_id'] = l_user
                        st.toast(f"おかえりなさい、{l_user}さん！")
                        st.rerun()
                    else:
                        st.error("ユーザー名またはパスワードが違います")
                except Exception as e:
                    st.error(f"ログインエラー: {e}")

    # --- 新規ユーザー登録 ---
    with tab2:
        st.subheader("新しくアカウントを作る")
        r_user = st.text_input("希望のユーザー名", key="reg_user")
        r_pass = st.text_input("パスワードを設定", type="password", key="reg_pass")
        
        if st.button("登録する", key="reg_btn"):
            if not r_user or not r_pass:
                st.error("入力してください")
            else:
                try:
                    supabase.table('users').insert({"username": r_user, "password": r_pass}).execute()
                    st.success("登録しました！「ログイン」タブからログインしてください。")
                except:
                    st.error("そのユーザー名は既に使用されています。別の名前にしてください。")

# ログインしていない場合はここでストップ
if 'user_id' not in st.session_state:
    login()
    st.stop()

# ログイン中のユーザーID
user_id = st.session_state['user_id']

# ==========================================
# 📱 メインアプリ画面
# ==========================================

# --- サイドバー：ユーザー情報 & 入力フォーム ---
with st.sidebar:
    st.write(f"👤 User: **{user_id}**")
    if user_id == ADMIN_USER:
        st.caption("👑 管理者権限あり")
    
    if st.button("ログアウト"):
        del st.session_state['user_id']
        st.rerun()
        
    st.divider()
    st.header("✏️ 入力")

    # カテゴリリスト取得
    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
        category_list.append("➕ 新しいカテゴリを追加...")
    except:
        category_list = ["食費", "その他"]

    # 入力フォーム
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
            # カテゴリ追加ロジック
            if selected_cat == "➕ 新しいカテゴリを追加...":
                if memo:
                    final_category = memo
                    try:
                        supabase.table('categories').insert({"name": final_category}).execute()
                        st.toast(f"カテゴリ「{final_category}」を追加！")
                    except:
                        pass # 重複など
                else:
                    st.error("新カテゴリ名を入力してください")
                    st.stop()

            # データ保存
            data = {
                "user_id": user_id,
                "date": str(date),
                "category": final_category,
                "memo": memo,
                "amount": amount
            }
            supabase.table("receipts").insert(data).execute()
            st.success("保存しました！")

# --- メインコンテンツ：ダッシュボード ---
st.title("💰 家計簿ダッシュボード")

# データの取得（管理者かどうかで分岐）
if user_id == ADMIN_USER:
    st.warning("👑 管理者モードで全ユーザーのデータを表示中")
    # 全員分を取得
    response = supabase.table('receipts').select("*").order('date', desc=True).execute()
else:
    # 自分の分だけ取得
    response = supabase.table('receipts').select("*").eq('user_id', user_id).order('date', desc=True).execute()

df = pd.DataFrame(response.data)

if not df.empty:
    df['date'] = pd.to_datetime(df['date'])
    
    # KPIエリア
    col1, col2, col3 = st.columns(3)
    current_month = datetime.date.today().strftime("%Y-%m")
    df_this_month = df[df['date'].dt.strftime('%Y-%m') == current_month]
    
    col1.metric("今月の出費", f"¥{df_this_month['amount'].sum():,}")
    col2.metric("全期間の出費", f"¥{df['amount'].sum():,}")
    col3.metric("データ件数", f"{len(df)} 件")
    
    st.divider()
    
    # グラフと履歴のタブ
    tab1, tab2, tab3 = st.tabs(["📊 カテゴリ分析", "📈 日別推移", "📝 履歴データ"])
    
    with tab1:
        if not df_this_month.empty:
            st.subheader("今月のカテゴリ割合")
            fig = px.pie(df_this_month, values='amount', names='category')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("今月のデータがまだありません")
            
    with tab2:
        st.subheader("日別支出")
        daily_data = df.groupby('date')['amount'].sum().reset_index()
        fig_bar = px.bar(daily_data, x='date', y='amount')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with tab3:
        # 管理者の場合、誰のデータかもわかるようにする
        cols = ['date', 'category', 'memo', 'amount']
        if user_id == ADMIN_USER:
            cols.insert(0, 'user_id') # 先頭にユーザーID列を追加
            
        st.dataframe(df[cols], use_container_width=True)

else:
    st.info("データがありません。サイドバーから入力してください。")
