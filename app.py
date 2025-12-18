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

st.set_page_config(page_title="家計簿", page_icon="💰", layout="wide", initial_sidebar_state="collapsed")

# --- 📱 marumie風 & スマホ最適化CSS ---
st.markdown("""
<style>
    /* 全体のフォント調整 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #333;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
    }
    header, footer, [data-testid="collapsedControl"] {display: none;}
    
    /* タブのデザイン */
    .stTabs [data-baseweb="tab"] {
        flex-grow: 1;
        justify-content: center;
        padding: 10px 0;
        font-size: 0.9rem;
        font-weight: 600;
        color: #555;
    }
    
    /* カテゴリタグ（marumie風） */
    .cat-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        background-color: #f0f2f6; /* 薄いグレー */
        color: #555;
        border: 1px solid #e0e0e0;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 ログイン機能
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
                        st.error("違います")
                except:
                    st.error("エラー")
    with tab2:
        with st.form("reg_form"):
            r_user = st.text_input("希望のユーザー名")
            r_pass = st.text_input("パスワード", type="password")
            if st.form_submit_button("登録する", type="primary", use_container_width=True):
                try:
                    supabase.table('users').insert({"username": r_user, "password": r_pass}).execute()
                    st.success("登録しました！")
                except:
                    st.error("その名前は使われています")

if 'user_id' not in st.session_state:
    login()
    st.stop()

user_id = st.session_state['user_id']

# ==========================================
# 📱 データ取得 & 管理者メニュー
# ==========================================
df_display = pd.DataFrame() 
show_deleted = False

if user_id == ADMIN_USER:
    with st.expander(f"👑 管理者メニュー ({user_id})", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        show_deleted = c1.checkbox("🗑️ 削除済を表示")
        
        if show_deleted:
            response = supabase.table('receipts').select("*").not_.is_('deleted_at', 'null').order('deleted_at', desc=True).execute()
        else:
            response = supabase.table('receipts').select("*").is_('deleted_at', 'null').order('date', desc=True).execute()
        
        raw_df = pd.DataFrame(response.data)
        
        if not raw_df.empty:
            user_list = raw_df['user_id'].unique().tolist()
            user_list.insert(0, "全員")
            selected_view_user = c2.selectbox("表示ユーザー", user_list)
            if selected_view_user == "全員":
                df_display = raw_df.copy()
            else:
                df_display = raw_df[raw_df['user_id'] == selected_view_user].copy()
        else:
            df_display = raw_df.copy()
            
        if c3.button("ログアウト"):
            del st.session_state['user_id']
            st.rerun()
else:
    # 一般ユーザー
    c_head1, c_head2 = st.columns([3, 1])
    c_head1.subheader(f"👋 {user_id}")
    if c_head2.button("ログアウト"):
        del st.session_state['user_id']
        st.rerun()
        
    response = supabase.table('receipts').select("*").eq('user_id', user_id).is_('deleted_at', 'null').order('date', desc=True).execute()
    raw_df = pd.DataFrame(response.data)
    df_display = raw_df.copy()

# ==========================================
# 📱 メインコンテンツ
# ==========================================
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
        st.markdown("<hr style='margin: 0.5em 0; opacity:0.2;'>", unsafe_allow_html=True)

    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
    except:
        category_list = ["食費", "その他"]

    cat_mode = "既存リスト"
    final_category = st.selectbox("カテゴリ", category_list)
    
    with st.expander("➕ カテゴリを新しく作る"):
        new_cat_input = st.text_input("新しいカテゴリ名", placeholder="例：推し活")
        if new_cat_input:
            cat_mode = "カテゴリ追加"
            final_category = new_cat_input
            st.success(f"「{final_category}」で記録します")

    with st.form("input_form"):
        c1, c2 = st.columns([1, 1.2]) 
        date = c1.date_input("日付", today)
        amount = c2.number_input("金額 (円)", min_value=0, step=100)
        memo = st.text_input("メモ", placeholder="内容を入力")
        
        if st.form_submit_button("記録する", type="primary", use_container_width=True):
            if show_deleted:
                st.error("管理モード中は記録不可")
                st.stop()
            if not final_category or amount == 0:
                st.warning("カテゴリと金額を入力してください")
                st.stop()

            if cat_mode == "カテゴリ追加":
                try:
                    supabase.table('categories').insert({"name": final_category}).execute()
                except:
                    pass

            data = {"user_id": user_id, "date": str(date), "category": final_category, "memo": memo, "amount": amount}
            supabase.table("receipts").insert(data).execute()
            st.toast("✅ 記録しました！", icon="🎉")
            time.sleep(0.5)
            st.rerun()

# ------------------------------------------
# 2. 分析タブ
# ------------------------------------------
with tab_dash:
    if not df_display.empty:
        df_display['date'] = pd.to_datetime(df_display['date'])
        
        st.caption("📈 日々の推移")
        chart_data = df_display.copy().set_index('date').resample('D')['amount'].sum().reset_index()
        fig_bar = px.bar(chart_data, x='date', y='amount')
        fig_bar.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=200)
        st.plotly_chart(fig_bar, use_container_width=True)
            
        st.caption("🍰 カテゴリ割合")
        current_month = today.strftime("%Y-%m")
        df_this_month = df_display[df_display['date'].dt.strftime('%Y-%m') == current_month]
        if not df_this_month.empty:
            fig_pie = px.pie(df_this_month, values='amount', names='category', hole=0.5)
            fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=10), height=250)
            total = df_this_month['amount'].sum()
            fig_pie.add_annotation(text=f"¥{total:,}", showarrow=False, font_size=16)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("今月のデータなし")
    else:
        st.info("データなし")

# ------------------------------------------
# 3. ログ（履歴）タブ - marumie風デザイン
# ------------------------------------------
with tab_history:
    if not df_display.empty:
        
        # --- 🔍 marumie風 検索＆フィルターエリア ---
        with st.container():
            f_col1, f_col2 = st.columns([2, 1])
            search_query = f_col1.text_input("🔍 キーワード検索", placeholder="店名やメモを検索...")
            
            # 月の選択肢を作る
            df_display['month_str'] = df_display['date'].dt.strftime('%Y-%m')
            month_list = df_display['month_str'].unique().tolist()
            month_list.insert(0, "全期間")
            selected_month = f_col2.selectbox("期間", month_list)

        st.markdown("<hr style='margin: 0.5em 0 1em 0; opacity:0.2;'>", unsafe_allow_html=True)
        
        # --- フィルタリング処理 ---
        filtered_df = df_display.copy()
        
        # 1. 月で絞り込み
        if selected_month != "全期間":
            filtered_df = filtered_df[filtered_df['month_str'] == selected_month]
            
        # 2. 検索ワードで絞り込み
        if search_query:
            # メモかカテゴリに文字が含まれていればヒット
            filtered_df = filtered_df[
                filtered_df['memo'].str.contains(search_query, na=False) | 
                filtered_df['category'].str.contains(search_query, na=False)
            ]

        # --- リスト表示 ---
        if not filtered_df.empty:
            # 日付で並び替え
            filtered_df = filtered_df.sort_values('date', ascending=False)
            
            for index, row in filtered_df.iterrows():
                icon = row['category'][0] if row['category'] else "💰"
                date_str = row['date'].strftime('%Y.%m.%d')
                
                # marumie風のきれいなリストデザイン
                st.markdown(
                    f"""
                    <div style="
                        background-color: white;
                        padding: 12px 0;
                        border-bottom: 1px solid #f0f0f0;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                    ">
                        <div style="display: flex; align-items: flex-start; gap: 10px;">
                            <div style="
                                background-color: #f8f9fa;
                                width: 40px; height: 40px;
                                border-radius: 50%;
                                display: flex; align-items: center; justify-content: center;
                                font-size: 1.2rem;
                            ">{icon}</div>
                            
                            <div>
                                <div style="font-weight: bold; font-size: 0.95rem; color: #333;">{row['memo']}</div>
                                <div style="font-size: 0.75rem; color: #888; margin-top:2px;">{date_str}</div>
                                <span class="cat-tag">{row['category']}</span>
                            </div>
                        </div>
                        
                        <div style="text-align: right;">
                            <div style="font-weight: bold; font-size: 1rem; color: #333;">¥{row['amount']:,}</div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.caption("条件に一致するデータが見つかりません 💦")
            
    else:
        st.info("データなし")

# ------------------------------------------
# 4. 修正・削除タブ
# ------------------------------------------
with tab_edit:
    if show_deleted:
        st.warning("閲覧モード中")
    elif not df_display.empty:
        edit_options = df_display.copy()
        edit_options['label'] = edit_options.apply(lambda x: f"{x['date'].strftime('%m/%d')} {x['memo']} ¥{x['amount']}", axis=1)
        
        selected_record_id = st.selectbox(
            "修正するデータ",
            edit_options['id'],
            format_func=lambda x: edit_options[edit_options['id'] == x]['label'].values[0]
        )
        target_row = df_display[df_display['id'] == selected_record_id].iloc[0]

        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            new_date = c1.date_input("日付", target_row['date'])
            new_amount = c2.number_input("金額", value=target_row['amount'], step=100)
            
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
                st.success("更新！")
                time.sleep(0.5)
                st.rerun()

            if b2.form_submit_button("削除", use_container_width=True):
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                supabase.table('receipts').update({"deleted_at": now_iso}).eq('id', int(selected_record_id)).execute()
                st.success("削除！")
                time.sleep(0.5)
                st.rerun()
    else:
        st.info("データなし")
