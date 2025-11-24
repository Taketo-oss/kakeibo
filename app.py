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
# 🔐 ログイン・新規登録機能 (フォーム対応版)
# ==========================================
def login():
    st.title("🔐 家計簿アプリ")
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])

    with tab1:
        st.subheader("ログイン")
        with st.form("login_form"):
            l_user = st.text_input("ユーザー名", key="login_user")
            l_pass = st.text_input("パスワード", type="password", key="login_pass")
            submitted = st.form_submit_button("ログインする")
            
            if submitted:
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
        with st.form("reg_form"):
            r_user = st.text_input("希望のユーザー名", key="reg_user")
            r_pass = st.text_input("パスワードを設定", type="password", key="reg_pass")
            reg_submitted = st.form_submit_button("登録する")
            
            if reg_submitted:
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

# データの取得（ここでフィルタリングの準備をします）
df_display = pd.DataFrame() # 表示用の空の箱

# まずは全データを取得するか、自分だけか
if user_id == ADMIN_USER:
    # 管理者は一旦全員分を取ってくる
    response = supabase.table('receipts').select("*").order('date', desc=True).execute()
else:
    # 一般ユーザーは自分だけ
    response = supabase.table('receipts').select("*").eq('user_id', user_id).order('date', desc=True).execute()

raw_df = pd.DataFrame(response.data)

# --- サイドバー ---
with st.sidebar:
    st.write(f"👤 User: **{user_id}**")
    
    # ★★★ ここが新機能！管理者用フィルター ★★★
    if user_id == ADMIN_USER:
        st.caption("👑 管理者メニュー")
        if not raw_df.empty:
            # データの中にいるユーザー一覧を取得
            user_list = raw_df['user_id'].unique().tolist()
            user_list.insert(0, "全員 (All Users)") # 先頭に「全員」を追加
            
            # 誰のデータを見るか選択
            selected_view_user = st.selectbox("📊 誰のデータを見る？", user_list)
            
            # データフレームを絞り込む
            if selected_view_user == "全員 (All Users)":
                df_display = raw_df.copy() # 全員そのまま
            else:
                df_display = raw_df[raw_df['user_id'] == selected_view_user].copy() # 選んだ人だけ
        else:
            df_display = raw_df.copy()
    else:
        # 一般ユーザーは選択権なし（自分のデータのみ）
        df_display = raw_df.copy()

    if st.button("ログアウト"):
        del st.session_state['user_id']
        st.rerun()
        
    st.divider()
    st.header("✏️ 新規入力")

    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
        category_list.append("➕ 新しいカテゴリを追加...")
    except:
        category_list = ["食費", "その他"]

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
            st.rerun() # 保存したら即反映

# --- メインコンテンツ ---
st.title("💰 家計簿ダッシュボード")

# フィルタリングされた df_display を使って表示
if not df_display.empty:
    df_display['date'] = pd.to_datetime(df_display['date'])
    
    # 誰のデータを表示中かタイトル出す
    if user_id == ADMIN_USER:
        # 選択ボックスの値を取得（サイドバーのキーがないので変数から判断しにくいが、ロジックで対応）
        # selectboxの返り値は変数に入っているので、再取得は難しいが、
        # df_displayの中身を見て判断
        unique_users = df_display['user_id'].unique()
        if len(unique_users) > 1:
            st.warning(f"👑 全員（{len(unique_users)}名）のデータを合算表示中")
        else:
            st.success(f"🔍 {unique_users[0]} さんのデータを表示中")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 カテゴリ分析", "📈 日別推移", "📝 履歴一覧", "🔧 修正・削除"])
    
    current_month = datetime.date.today().strftime("%Y-%m")
    df_this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month]

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
        daily_data = df_display.groupby('date')['amount'].sum().reset_index()
        fig_bar = px.bar(daily_data, x='date', y='amount')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with tab3:
        cols = ['date', 'category', 'memo', 'amount']
        if user_id == ADMIN_USER:
            cols.insert(0, 'user_id')
        st.dataframe(df_display[cols], use_container_width=True)

    with tab4:
        st.subheader("データの修正・削除")
        st.caption("表示中のデータから選択して修正できます")

        edit_options = df_display.copy()
        edit_options['label'] = edit_options.apply(lambda x: f"{x['date'].strftime('%Y-%m-%d')} | {x['memo']} | ¥{x['amount']}", axis=1)
        
        selected_record_id = st.selectbox(
            "編集するデータを選んでください",
            edit_options['id'],
            format_func=lambda x: edit_options[edit_options['id'] == x]['label'].values[0]
        )

        target_row = df_display[df_display['id'] == selected_record_id].iloc[0]

        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            new_date = col1.date_input("日付", target_row['date'])
            # カテゴリリストにない古いカテゴリの場合の対策
            current_cat_index = 0
            if target_row['category'] in category_list:
                current_cat_index = category_list.index(target_row['category'])
            
            new_cat = col2.selectbox("カテゴリ", category_list, index=current_cat_index)
            new_memo = st.text_input("メモ・店名", target_row['memo'])
            new_amount = st.number_input("金額", value=target_row['amount'], step=100)

            c1, c2 = st.columns([1, 1])
            update_btn = c1.form_submit_button("更新する")
            delete_btn = c2.form_submit_button("削除する", type="primary")

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
                supabase.table('receipts').delete().eq('id', int(selected_record_id)).execute()
                st.success("データを削除しました！")
                st.rerun()

else:
    st.info("データがありません。サイドバーから入力してください。")
