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

# サイドバーを最初から展開した状態にする
st.set_page_config(page_title="家計簿", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

# --- 📱 ダークモード・UIカスタムCSS ---
st.markdown("""
<style>
    /* 全体のフォント調整 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    .block-container {
        /* ★上部の余白をしっかり取る（切れるのを防ぐ） */
        padding-top: 3.5rem; 
        padding-bottom: 5rem;
    }
    /* ヘッダーは隠さず、フッターのみ隠す（サイドバーボタンを確実に表示するため） */
    footer {visibility: hidden;}
    
    /* タブのデザイン調整 */
    .stTabs [data-baseweb="tab"] {
        flex-grow: 1;
        justify-content: center;
        padding: 10px 0;
        font-size: 0.9rem;
        font-weight: 600;
    }
    
    /* カテゴリタグのデザイン */
    .cat-tag {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: bold;
        background-color: rgba(77, 166, 255, 0.2); 
        color: #8ECAFF;
        border: 1px solid rgba(77, 166, 255, 0.3);
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================
def login():
    st.title("🔐 家計簿アプリ")
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("ユーザー名")
            l_pass = st.text_input("パスワード", type="password")
            if st.form_submit_button("ログイン", type="primary", use_container_width=True):
                try:
                    res = supabase.table('users').select("*").eq('username', l_user).eq('password', l_pass).execute()
                    if len(res.data) > 0:
                        st.session_state['user_id'] = l_user
                        st.rerun()
                    else:
                        st.error("ログイン情報が正しくありません")
                except:
                    st.error("エラーが発生しました")
    with tab2:
        with st.form("reg_form"):
            r_user = st.text_input("希望のユーザー名")
            r_pass = st.text_input("パスワード", type="password")
            if st.form_submit_button("登録する", type="primary", use_container_width=True):
                try:
                    supabase.table('users').insert({"username": r_user, "password": r_pass}).execute()
                    st.success("登録完了！ログインしてください。")
                except:
                    st.error("その名前は既に使用されています")

if 'user_id' not in st.session_state:
    login()
    st.stop()

user_id = st.session_state['user_id']

# ==========================================
# 📱 データ取得 & サイドバー
# ==========================================
df_display = pd.DataFrame() 
show_deleted = False

with st.sidebar:
    st.write(f"👤 **{user_id}**")
    
    if user_id == ADMIN_USER:
        st.divider()
        st.caption("👑 管理者メニュー")
        show_deleted = st.checkbox("🗑️ 削除済を表示")
        
        if show_deleted:
            response = supabase.table('receipts').select("*").not_.is_('deleted_at', 'null').order('deleted_at', desc=True).execute()
        else:
            response = supabase.table('receipts').select("*").is_('deleted_at', 'null').order('date', desc=True).execute()
        
        raw_df = pd.DataFrame(response.data)
        
        if not raw_df.empty:
            user_list = raw_df['user_id'].unique().tolist()
            user_list.insert(0, "全員")
            selected_view_user = st.selectbox("表示ユーザー", user_list)
            
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

    st.divider()
    if st.button("ログアウト", type="primary"):
        del st.session_state['user_id']
        st.rerun()

# ==========================================
# 📱 メインコンテンツ
# ==========================================
st.subheader("💰 家計簿")

tab_input, tab_dash, tab_history, tab_edit = st.tabs(["✏️ 入力", "📊 分析", "📝 ログ", "🔧 修正"])

# ------------------------------------------
# 1. 入力タブ
# ------------------------------------------
with tab_input:
    if not df_display.empty and not show_deleted:
        current_month_str = today.strftime("%Y-%m")
        df_display['date'] = pd.to_datetime(df_display['date'])
        this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month_str]['amount'].sum()
        st.metric(f"📅 {today.month}月の出費", f"¥{this_month:,}")
        st.markdown("<hr style='margin: 0.5em 0; opacity:0.1;'>", unsafe_allow_html=True)

    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
    except:
        category_list = ["🍔 食費", "🚋 交通費", "💊 日用品", "🕹️ 趣味", "🏠 固定費", "❓ その他"]

    cat_mode = "既存リスト"
    final_category = st.selectbox("カテゴリ", category_list)
    
    with st.expander("➕ カテゴリを新規作成"):
        new_cat_input = st.text_input("新しいカテゴリ名", placeholder="例：🎮 推し活")
        if new_cat_input:
            cat_mode = "カテゴリ追加"
            final_category = new_cat_input

    with st.form("input_form"):
        c1, c2 = st.columns([1, 1.2]) 
        date = c1.date_input("日付", today)
        amount = c2.number_input("金額 (円)", min_value=0, step=100)
        memo = st.text_input("メモ", placeholder="内容を入力")
        
        if st.form_submit_button("記録する", type="primary", use_container_width=True):
            if show_deleted:
                st.error("管理モード中は記録できません")
                st.stop()
            if not final_category or amount == 0:
                st.warning("内容を確認してください")
                st.stop()

            if cat_mode == "カテゴリ追加":
                try:
                    supabase.table('categories').insert({"name": final_category}).execute()
                except:
                    pass

            data = {"user_id": user_id, "date": str(date), "category": final_category, "memo": memo, "amount": amount}
            supabase.table("receipts").insert(data).execute()
            st.toast("✅ 記録完了！", icon="🎉")
            time.sleep(0.5)
            st.rerun()

# ------------------------------------------
# 2. 分析タブ
# ------------------------------------------
with tab_dash:
    if not df_display.empty:
        df_display['date'] = pd.to_datetime(df_display['date'])
        
        st.caption("📈 日別の推移")
        chart_data = df_display.copy().set_index('date').resample('D')['amount'].sum().reset_index()
        fig_bar = px.bar(chart_data, x='date', y='amount', color_discrete_sequence=['#4DA6FF'])
        fig_bar.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, 
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                              margin=dict(l=0, r=0, t=0, b=0), height=200)
        st.plotly_chart(fig_bar, use_container_width=True)
            
        st.caption("🍰 カテゴリ割合")
        current_month = today.strftime("%Y-%m")
        df_this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month]
        if not df_this_month.empty:
            fig_pie = px.pie(df_this_month, values='amount', names='category', hole=0.5)
            fig_pie.update_layout(showlegend=False, paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=0, b=10), height=250)
            total = df_this_month['amount'].sum()
            fig_pie.add_annotation(text=f"¥{total:,}", showarrow=False, font_size=16, font_color="#E0E1DD")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("今月のデータはありません")
    else:
        st.info("データがありません")

# ------------------------------------------
# 3. ログ（履歴）タブ
# ------------------------------------------
with tab_history:
    if not df_display.empty:
        with st.container():
            f_col1, f_col2 = st.columns([2, 1])
            search_query = f_col1.text_input("🔍 検索", placeholder="キーワード...")
            
            df_display['month_str'] = df_display['date'].dt.strftime('%Y-%m')
            month_list = sorted(df_display['month_str'].unique().tolist(), reverse=True)
            month_list.insert(0, "全期間")
            selected_month = f_col2.selectbox("月別", month_list)

        st.markdown("<hr style='margin: 0.5em 0 1em 0; opacity:0.1;'>", unsafe_allow_html=True)
        
        filtered_df = df_display.copy()
        if selected_month != "全期間":
            filtered_df = filtered_df[filtered_df['month_str'] == selected_month]
        if search_query:
            filtered_df = filtered_df[
                filtered_df['memo'].str.contains(search_query, na=False) | 
                filtered_df['category'].str.contains(search_query, na=False)
            ]

        if not filtered_df.empty:
            filtered_df = filtered_df.sort_values('date', ascending=False)
            for index, row in filtered_df.iterrows():
                icon = row['category'][0] if row['category'] else "💰"
                date_str = row['date'].strftime('%Y.%m.%d')
                
                # HTMLコードの先頭にスペースを入れないことで、コードブロック化を防止
                html_code = f"""
<div style="background-color: #1B263B; padding: 12px 10px; border-bottom: 1px solid #2B3A55; display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; border-radius: 8px; color: #E0E1DD;">
<div style="display: flex; align-items: flex-start; gap: 12px;">
<div style="background-color: #2B3A55; width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; border: 1px solid #3E4C63;">
{icon}
</div>
<div>
<div style="font-weight: bold; font-size: 0.95rem; color: #FFFFFF;">{row['memo']}</div>
<div style="font-size: 0.75rem; color: #8E9AAF; margin-top:2px;">{date_str}</div>
<span class="cat-tag">{row['category']}</span>
</div>
</div>
<div style="text-align: right;">
<div style="font-weight: bold; font-size: 1.1rem; color: #4DA6FF;">¥{row['amount']:,}</div>
</div>
</div>
"""
                st.markdown(html_code, unsafe_allow_html=True)
        else:
            st.caption("見つかりませんでした")
    else:
        st.info("データがありません")

# ------------------------------------------
# 4. 修正・削除タブ
# ------------------------------------------
with tab_edit:
    if show_deleted:
        st.warning("閲覧モード（削除済みデータ表示中）は操作できません")
    elif not df_display.empty:
        st.caption("対象データを選択してください")
        edit_df = df_display.copy().sort_values('date', ascending=False)
        edit_df['label'] = edit_df.apply(lambda x: f"{x['date'].strftime('%m/%d')} {x['memo']} ¥{x['amount']}", axis=1)
        
        selected_record_id = st.selectbox(
            "修正・削除する記録",
            edit_df['id'],
            format_func=lambda x: edit_df[edit_df['id'] == x]['label'].values[0]
        )
        target_row = df_display[df_display['id'] == selected_record_id].iloc[0]

        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            new_date = c1.date_input("日付", target_row['date'])
            new_amount = c2.number_input("金額", value=target_row['amount'], step=100)
            
            # カテゴリのインデックス取得
            cur_idx = 0
            if target_row['category'] in category_list:
                cur_idx = category_list.index(target_row['category'])
            else:
                category_list.append(target_row['category'])
                cur_idx = len(category_list) - 1
            
            new_cat = st.selectbox("カテゴリ", category_list, index=cur_idx)
            new_memo = st.text_input("メモ", target_row['memo'])

            b1, b2 = st.columns(2)
            if b1.form_submit_button("更新", type="primary", use_container_width=True):
                supabase.table('receipts').update({
                    "date": str(new_date),
                    "category": new_cat,
                    "memo": new_memo,
                    "amount": new_amount
                }).eq('id', int(selected_record_id)).execute()
                st.success("更新しました！")
                time.sleep(0.5)
                st.rerun()

            if b2.form_submit_button("削除", use_container_width=True):
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                supabase.table('receipts').update({"deleted_at": now_iso}).eq('id', int(selected_record_id)).execute()
                st.success("削除しました！")
                time.sleep(0.5)
                st.rerun()
    else:
        st.info("データがありません")

