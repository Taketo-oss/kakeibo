import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import plotly.express as px

# ==========================================
# ⚙️ 設定エリア
# ==========================================
# ★あなたのユーザー名（管理者）
ADMIN_USER = "taketo" 

# ==========================================
# 🔌 データベース接続
# ==========================================
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    st.error("Supabaseのキー設定が見つかりません。")
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
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])

    with tab1:
        st.subheader("ログイン")
        l_user = st.text_input("ユーザー名", key="login_user")
        l_pass = st.text_input("パスワード", type="password", key="login_pass")
        
        if st.button("ログインする", key="login_btn"):
            if not l_user or not l_pass:
                st.error("入力してください")
            else:
                try:
                    res = supabase.table('users').select("*").eq('username', l_user).eq('password', l_pass).execute()
                    if len(res.data) > 0:
                        st.session_state['user_id'] = l_user
                        st.toast(f"おかえりなさい、{l_user}さん！")
                        st.rerun()
                    else:
                        st.error("ユーザー名またはパスワードが違います")
                except Exception as e:
                    st.error(f"ログインエラー: {e}")

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
                    st.error("そのユーザー名は既に使用されています。")

if 'user_id' not in st.session_state:
    login()
    st.stop()

user_id = st.session_state['user_id']

# ==========================================
# 📱 メインアプリ画面
# ==========================================

with st.sidebar:
    st.write(f"👤 User: **{user_id}**")
    if user_id == ADMIN_USER:
        st.caption("👑 管理者権限あり")
    
    if st.button("ログアウト"):
        del st.session_state['user_id']
        st.rerun()
        
    st.divider()
    st.header("✏️ 新規入力")

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
            
        memo = st.text_input("メモ・店名", placeholder="例: コンビニ")
        amount = st.number_input("金額", min_value=0, step=100)
        submitted = st.form_submit_button("記録する")
        
        if submitted:
            final_category = selected_cat
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

            data = {
                "user_id": user_id,
                "date": str(date),
                "category": final_category,
                "memo": memo,
                "amount": amount
            }
            supabase.table("receipts").insert(data).execute()
            st.success("保存しました！")

# --- メインコンテンツ ---
st.title("💰 家計簿ダッシュボード")

# データ取得
if user_id == ADMIN_USER:
    response = supabase.table('receipts').select("*").order('date', desc=True).execute()
else:
    response = supabase.table('receipts').select("*").eq('user_id', user_id).order('date', desc=True).execute()

df = pd.DataFrame(response.data)

if not df.empty:
    df['date'] = pd.to_datetime(df['date'])
    
    # ---------------------------------------------------
    # ★ここが新機能！タブに「修正・削除」を追加しました
    # ---------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs(["📊 カテゴリ分析", "📈 日別推移", "📝 履歴一覧", "🔧 修正・削除"])
    
    current_month = datetime.date.today().strftime("%Y-%m")
    df_this_month = df[df['date'].dt.strftime('%Y-%m') == current_month]

    with tab1:
        if not df_this_month.empty:
            st.subheader("今月のカテゴリ割合")
            fig = px.pie(df_this_month, values='amount', names='category')
            st.plotly_chart(fig, use_container_width=True)
            st.metric("今月の合計", f"¥{df_this_month['amount'].sum():,}")
        else:
            st.info("今月のデータがまだありません")
            
    with tab2:
        st.subheader("日別支出")
        daily_data = df.groupby('date')['amount'].sum().reset_index()
        fig_bar = px.bar(daily_data, x='date', y='amount')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with tab3:
        cols = ['date', 'category', 'memo', 'amount']
        if user_id == ADMIN_USER:
            cols.insert(0, 'user_id')
        st.dataframe(df[cols], use_container_width=True)

    # --- 新機能：修正・削除タブ ---
    with tab4:
        st.subheader("データの修正・削除")
        st.caption("直近のデータから選択して修正できます")

        # 編集対象を選ぶプルダウンを作る
        # 見やすいように「日付 | メモ | 金額」の形式にする
        edit_options = df.copy()
        edit_options['label'] = edit_options.apply(lambda x: f"{x['date'].strftime('%Y-%m-%d')} | {x['memo']} | ¥{x['amount']}", axis=1)
        
        # 選択ボックス
        selected_record_id = st.selectbox(
            "編集するデータを選んでください",
            edit_options['id'],
            format_func=lambda x: edit_options[edit_options['id'] == x]['label'].values[0]
        )

        # 選んだデータの今の値を取得
        target_row = df[df['id'] == selected_record_id].iloc[0]

        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            new_date = col1.date_input("日付", target_row['date'])
            new_cat = col2.selectbox("カテゴリ", category_list, index=category_list.index(target_row['category']) if target_row['category'] in category_list else 0)
            new_memo = st.text_input("メモ・店名", target_row['memo'])
            new_amount = st.number_input("金額", value=target_row['amount'], step=100)

            c1, c2 = st.columns([1, 1])
            update_btn = c1.form_submit_button("更新する (Update)")
            delete_btn = c2.form_submit_button("削除する (Delete)", type="primary")

            if update_btn:
                supabase.table('receipts').update({
                    "date": str(new_date),
                    "category": new_cat,
                    "memo": new_memo,
                    "amount": new_amount
                }).eq('id', int(selected_record_id)).execute()
                st.success("データを更新しました！")
                st.rerun()

            if delete_btn:
                # 削除処理
                supabase.table('receipts').delete().eq('id', int(selected_record_id)).execute()
                st.success("データを削除しました！")
                st.rerun()

else:
    st.info("データがありません。サイドバーから入力してください。")
