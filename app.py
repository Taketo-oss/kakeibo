import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import plotly.express as px

# ==========================================
# ⚙️ 設定エリア
# ==========================================
ADMIN_USER = "taketo" 

# ==========================================
# 🕒 日本時間の定義
# ==========================================
JST = datetime.timezone(datetime.timedelta(hours=9))
today = datetime.datetime.now(JST).date()

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

st.set_page_config(page_title="家計簿アプリ", page_icon="💰", layout="wide")

# ==========================================
# 🔐 ログイン機能
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
                            st.rerun()
                        else:
                            st.error("違います")
                    except:
                        st.error("エラー")

    with tab2:
        st.subheader("新規登録")
        with st.form("reg_form"):
            r_user = st.text_input("希望のユーザー名", key="reg_user")
            r_pass = st.text_input("パスワード", type="password", key="reg_pass")
            reg_submitted = st.form_submit_button("登録する")
            if reg_submitted:
                if not r_user or not r_pass:
                    st.error("入力してください")
                else:
                    try:
                        supabase.table('users').insert({"username": r_user, "password": r_pass}).execute()
                        st.success("登録しました！ログインしてください。")
                    except:
                        st.error("その名前は使われています")

if 'user_id' not in st.session_state:
    login()
    st.stop()

user_id = st.session_state['user_id']

# ==========================================
# 📱 メインアプリ画面
# ==========================================

# --- サイドバーは「ログアウト」と「管理者設定」だけにする ---
with st.sidebar:
    st.write(f"👤 **{user_id}**")
    if st.button("ログアウト", type="primary"):
        del st.session_state['user_id']
        st.rerun()

# データ取得
df_display = pd.DataFrame() 
if user_id == ADMIN_USER:
    response = supabase.table('receipts').select("*").order('date', desc=True).execute()
else:
    response = supabase.table('receipts').select("*").eq('user_id', user_id).order('date', desc=True).execute()
raw_df = pd.DataFrame(response.data)

# 管理者フィルター
if user_id == ADMIN_USER and not raw_df.empty:
    with st.sidebar:
        st.divider()
        st.caption("👑 管理者メニュー")
        user_list = raw_df['user_id'].unique().tolist()
        user_list.insert(0, "全員")
        selected_view_user = st.selectbox("誰のデータを見る？", user_list)
        if selected_view_user == "全員":
            df_display = raw_df.copy()
        else:
            df_display = raw_df[raw_df['user_id'] == selected_view_user].copy()
else:
    df_display = raw_df.copy()


# --- メイン画面：タブで機能を切り替える ---
st.title("💰 家計簿アプリ")

# ★ここが変更点！入力画面をメインのタブに持ってきました
tab_input, tab_dash, tab_edit = st.tabs(["✏️ 入力", "📊 分析", "🔧 履歴・修正"])

# ==========================================
# 1. 入力タブ (これで日付選択しても閉じません！)
# ==========================================
with tab_input:
    st.header("新規記録")
    
    # カテゴリ取得
    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
        category_list.append("➕ 新しいカテゴリを追加...")
    except:
        category_list = ["食費", "その他"]

    with st.form("input_form"):
        col1, col2 = st.columns(2)
        date = col1.date_input("日付", today)
        selected_cat = col2.selectbox("カテゴリ", category_list)
        
        if selected_cat == "➕ 新しいカテゴリを追加...":
            st.info("下のメモ欄にカテゴリ名を入力")
            
        memo = st.text_input("メモ・店名", placeholder="例: コンビニ")
        amount = st.number_input("金額", min_value=0, step=100)
        
        submitted = st.form_submit_button("記録する", type="primary")
        
        if submitted:
            final_category = selected_cat
            if selected_cat == "➕ 新しいカテゴリを追加...":
                if memo:
                    final_category = memo
                    try:
                        supabase.table('categories').insert({"name": final_category}).execute()
                    except:
                        pass
                else:
                    st.error("カテゴリ名を入力してください")
                    st.stop()

            if amount == 0:
                st.warning("金額が0円です")
                st.stop()

            data = {"user_id": user_id, "date": str(date), "category": final_category, "memo": memo, "amount": amount}
            supabase.table("receipts").insert(data).execute()
            st.success("保存しました！")
            st.rerun()

# ==========================================
# 2. 分析タブ
# ==========================================
with tab_dash:
    st.header("ダッシュボード")
    if not df_display.empty:
        df_display['date'] = pd.to_datetime(df_display['date'])
        
        # 支出の推移
        st.subheader("支出の推移")
        view_mode = st.radio("表示単位", ["日別", "週別", "月別"], horizontal=True)
        df_chart = df_display.copy().set_index('date')
        
        if view_mode == "日別":
            chart_data = df_chart.resample('D')['amount'].sum().reset_index()
        elif view_mode == "週別":
            chart_data = df_chart.resample('W-MON')['amount'].sum().reset_index()
        else: 
            chart_data = df_chart.resample('MS')['amount'].sum().reset_index()
            chart_data['date'] = chart_data['date'].dt.strftime('%Y-%m')

        fig_bar = px.bar(chart_data, x='date', y='amount')
        st.plotly_chart(fig_bar, use_container_width=True)

        # カテゴリ分析
        st.divider()
        st.subheader("カテゴリ割合 (今月)")
        current_month = today.strftime("%Y-%m")
        df_this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month]
        
        if not df_this_month.empty:
            fig_pie = px.pie(df_this_month, values='amount', names='category')
            st.plotly_chart(fig_pie, use_container_width=True)
            st.metric("今月の合計", f"¥{df_this_month['amount'].sum():,}")
        else:
            st.info("今月のデータなし")
    else:
        st.info("データがありません")

# ==========================================
# 3. 履歴・修正タブ
# ==========================================
with tab_edit:
    st.header("履歴・修正")
    if not df_display.empty:
        # 一覧表示
        cols = ['date', 'category', 'memo', 'amount']
        if user_id == ADMIN_USER:
            cols.insert(0, 'user_id')
        st.dataframe(df_display[cols], use_container_width=True)

        st.divider()
        st.subheader("データの修正・削除")
        
        # 修正用UI
        edit_options = df_display.copy()
        edit_options['label'] = edit_options.apply(lambda x: f"{x['date'].strftime('%m/%d')} | {x['memo']} | ¥{x['amount']}", axis=1)
        
        selected_record_id = st.selectbox(
            "修正するデータを選択",
            edit_options['id'],
            format_func=lambda x: edit_options[edit_options['id'] == x]['label'].values[0]
        )

        target_row = df_display[df_display['id'] == selected_record_id].iloc[0]

        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            new_date = c1.date_input("日付", target_row['date'])
            
            cur_idx = 0
            if target_row['category'] in category_list:
                cur_idx = category_list.index(target_row['category'])
            new_cat = c2.selectbox("カテゴリ", category_list, index=cur_idx)
            
            new_memo = st.text_input("メモ", target_row['memo'])
            new_amount = st.number_input("金額", value=target_row['amount'], step=100)

            btn_col1, btn_col2 = st.columns(2)
            if btn_col1.form_submit_button("更新する"):
                supabase.table('receipts').update({
                    "date": str(new_date),
                    "category": new_cat,
                    "memo": new_memo,
                    "amount": new_amount
                }).eq('id', int(selected_record_id)).execute()
                st.success("更新しました")
                st.rerun()

            if btn_col2.form_submit_button("削除する", type="primary"):
                supabase.table('receipts').delete().eq('id', int(selected_record_id)).execute()
                st.success("削除しました")
                st.rerun()
