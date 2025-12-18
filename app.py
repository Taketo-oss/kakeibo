import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import plotly.express as px
import time

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

# --- 🎨 sizu.me風のカスタムCSS (余計な装飾を消してシンプルにする) ---
st.markdown("""
<style>
    /* 全体のフォントを少し柔らかく */
    html, body, [class*="css"] {
        font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
    }
    /* ヘッダーの装飾ラインを隠す */
    header {visibility: hidden;}
    /* フッターを隠す */
    footer {visibility: hidden;}
    /* タブのデザインをシンプルに */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 5px;
        padding: 0 20px;
        font-weight: bold;
    }
    /* 選択されたタブの下線を消して、文字色を変えるだけにしたいがStreamlitの制限で難しいので
       せめて余白を綺麗に調整 */
</style>
""", unsafe_allow_html=True)

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

# --- サイドバー ---
with st.sidebar:
    st.write(f"👤 **{user_id}**")
    if st.button("ログアウト", type="primary"):
        del st.session_state['user_id']
        st.rerun()

# データ取得
df_display = pd.DataFrame() 
show_deleted = False

if user_id == ADMIN_USER:
    st.sidebar.divider()
    st.sidebar.caption("👑 管理者メニュー")
    show_deleted = st.sidebar.checkbox("🗑️ 削除済を表示")
    
    if show_deleted:
        response = supabase.table('receipts').select("*").not_.is_('deleted_at', 'null').order('deleted_at', desc=True).execute()
    else:
        response = supabase.table('receipts').select("*").is_('deleted_at', 'null').order('date', desc=True).execute()
    
    raw_df = pd.DataFrame(response.data)
    
    if not raw_df.empty:
        user_list = raw_df['user_id'].unique().tolist()
        user_list.insert(0, "全員")
        selected_view_user = st.sidebar.selectbox("誰のデータを見る？", user_list)
        if selected_view_user == "全員":
            df_display = raw_df.copy()
        else:
            df_display = raw_df[raw_df['user_id'] == selected_view_user].copy()
    else:
        df_display = raw_df.copy()

else:
    response = supabase.table('receipts').select("*").eq('user_id', user_id).is_('deleted_at', 'null').order('date', desc=True).execute()
    raw_df = pd.DataFrame(response.data)
    df_display = raw_df.copy()


st.title("💰 家計簿アプリ")
tab_input, tab_dash, tab_history, tab_edit = st.tabs(["✏️ 入力", "📊 分析", "📝 ログ", "🔧 修正"])

# ==========================================
# 1. 入力タブ
# ==========================================
with tab_input:
    st.header("✏️ 新規記録")

    # 今月の出費表示（シンプルに）
    if not df_display.empty and not show_deleted:
        try:
            current_month_str = today.strftime("%Y-%m")
            df_display['date'] = pd.to_datetime(df_display['date'])
            
            # 今月と先月の計算
            this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month_str]['amount'].sum()
            last_month_str = (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
            last_month = df_display[df_display['date'].dt.strftime('%Y-%m') == last_month_str]['amount'].sum()
            diff = this_month - last_month

            st.metric(
                label=f"📅 {today.month}月の支出",
                value=f"¥{this_month:,}",
                delta=f"{diff:,}円 (先月比)",
                delta_color="inverse"
            )
            st.divider()
        except:
            pass

    # カテゴリリスト取得
    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
    except:
        category_list = ["食費", "その他"]

    # カテゴリ選択
    cat_mode = st.radio("カテゴリモード", ["既存リスト", "カテゴリ追加"], horizontal=True, label_visibility="collapsed")
    final_category = ""
    
    if cat_mode == "既存リスト":
        final_category = st.selectbox("カテゴリを選択", category_list)
    else:
        final_category = st.text_input("新しいカテゴリ名", placeholder="例：推し活")
        if final_category:
            st.caption(f"✨ 「{final_category}」を新しく登録します")

    # 入力フォーム
    with st.form("input_form"):
        col1, col2 = st.columns(2)
        date = col1.date_input("日付", today)
        amount = col2.number_input("金額", min_value=0, step=100)
        memo = st.text_input("メモ・店名", placeholder="例: コンビニ")
        
        submitted = st.form_submit_button("記録する", type="primary", use_container_width=True)
        
        if submitted:
            if show_deleted:
                st.error("削除済みデータ表示中は記録できません。")
                st.stop()
            if not final_category:
                st.error("カテゴリを入力してください")
                st.stop()
            if amount == 0:
                st.warning("金額が0円です")
                st.stop()

            # 新規カテゴリ追加
            if cat_mode == "カテゴリ追加":
                try:
                    supabase.table('categories').insert({"name": final_category}).execute()
                except:
                    pass

            data = {"user_id": user_id, "date": str(date), "category": final_category, "memo": memo, "amount": amount}
            supabase.table("receipts").insert(data).execute()
            
            st.toast("✅ 記録しました！", icon="🎉")
            st.balloons()
            time.sleep(1)
            st.rerun()

# ==========================================
# 2. 分析タブ (catnose風 シンプルカード)
# ==========================================
with tab_dash:
    st.header("📊 ダッシュボード")
    if not df_display.empty:
        df_display['date'] = pd.to_datetime(df_display['date'])
        
        # グラフエリア
        c1, c2 = st.columns(2)
        with c1:
            st.caption("📈 日々の推移")
            chart_data = df_display.copy().set_index('date').resample('D')['amount'].sum().reset_index()
            fig_bar = px.bar(chart_data, x='date', y='amount')
            fig_bar.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with c2:
            st.caption("🍰 カテゴリ割合")
            current_month = today.strftime("%Y-%m")
            df_this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month]
            if not df_this_month.empty:
                fig_pie = px.pie(df_this_month, values='amount', names='category', hole=0.4)
                fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("今月のデータなし")

        st.divider()

        # --- nani.now風 タイムライン表示 ---
        st.subheader("🕒 最近の記録")
        
        recent_data = df_display.sort_values('date', ascending=False).head(5)
        for index, row in recent_data.iterrows():
            with st.container(border=True):
                c_left, c_right = st.columns([3, 1])
                with c_left:
                    # カテゴリの頭文字をアイコン化
                    icon = row['category'][0] if row['category'] else "💰"
                    st.markdown(f"**{icon} {row['memo']}**")
                    st.caption(f"{row['date'].strftime('%Y/%m/%d')} | {row['category']}")
                with c_right:
                    st.markdown(f"<div style='text-align: right; font-weight: bold;'>¥{row['amount']:,}</div>", unsafe_allow_html=True)
    else:
        st.info("データがありません")

# ==========================================
# 3. ログ（履歴）タブ (nani.now風 タイムライン)
# ==========================================
with tab_history:
    st.header("📝 支出ログ")
    st.caption("日々の記録")

    if not df_display.empty:
        # 日付でグループ化して表示する（これが nani.now のポイント！）
        df_display['date_str'] = df_display['date'].dt.strftime('%Y-%m-%d')
        
        # 日付ごとにデータをまとめる
        grouped = df_display.groupby('date_str')
        
        # 日付の降順（新しい順）でループ
        sorted_dates = sorted(df_display['date_str'].unique(), reverse=True)
        
        for date_key in sorted_dates:
            group_data = grouped.get_group(date_key)
            
            # --- 日付ヘッダー ---
            # "2023-12-18 (Mon)" のように表示
            day_obj = datetime.datetime.strptime(date_key, '%Y-%m-%d')
            weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day_obj.weekday()]
            
            st.markdown(f"##### {date_key} <span style='color:gray; font-weight:normal; font-size:0.8em;'>({weekday})</span>", unsafe_allow_html=True)
            
            # その日のデータをリスト表示
            for idx, row in group_data.iterrows():
                # シンプルな行表示
                # 左: カテゴリとメモ、 右: 金額
                
                # アイコン作成
                icon = row['category'][0] if row['category'] else "💰"
                
                col_main, col_amount = st.columns([4, 1])
                
                with col_main:
                    st.markdown(f"{icon} **{row['memo']}** <span style='color:gray; font-size:0.8em;'>({row['category']})</span>", unsafe_allow_html=True)
                
                with col_amount:
                    st.markdown(f"¥{row['amount']:,}")
            
            # 日付ごとの区切り線（薄く）
            st.markdown("<hr style='margin: 0.5em 0; opacity: 0.3;'>", unsafe_allow_html=True)

    else:
        st.info("データがありません")

# ==========================================
# 4. 修正・削除タブ
# ==========================================
with tab_edit:
    st.header("🔧 修正・削除")
    if show_deleted:
        st.warning("削除済みデータ表示中は操作できません")
    elif not df_display.empty:
        st.caption("修正したいデータを選んでください")
        edit_options = df_display.copy()
        edit_options['label'] = edit_options.apply(lambda x: f"{x['date'].strftime('%m/%d')} | {x['memo']} | ¥{x['amount']}", axis=1)
        
        selected_record_id = st.selectbox(
            "データ選択",
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
            else:
                category_list.append(target_row['category'])
                cur_idx = len(category_list) - 1

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
                st.success("更新しました！")
                time.sleep(1)
                st.rerun()

            if btn_col2.form_submit_button("削除する", type="primary"):
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                supabase.table('receipts').update({"deleted_at": now_iso}).eq('id', int(selected_record_id)).execute()
                st.success("ゴミ箱に移動しました！")
                time.sleep(1)
                st.rerun()
    else:
        st.info("データがありません")
