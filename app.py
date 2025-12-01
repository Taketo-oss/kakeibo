import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import plotly.express as px
import google.generativeai as genai
from PIL import Image
import io
import json

# ==========================================
# ⚙️ 設定エリア
# ==========================================
ADMIN_USER = "taketo" 

# 使用するAIモデルの定義（IDと表示名のペア）
AI_MODELS = {
    "models/gemini-2.5-flash-image": "⚡️ Flash (高速・通常用) - 基本はこれ！",
    "models/gemini-3-pro-image-preview": "🧠 Pro (高精度) - 文字が読み取れない時に"
}

# ==========================================
# 🕒 日本時間の定義
# ==========================================
JST = datetime.timezone(datetime.timedelta(hours=9))
today = datetime.datetime.now(JST).date()

# ==========================================
# 🔌 データベース & AI接続
# ==========================================
try:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(supabase_url, supabase_key)
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(f"接続設定エラー: {e}")
    st.stop()

@st.cache_resource
def init_connection():
    return create_client(supabase_url, supabase_key)
supabase = init_connection()

st.set_page_config(page_title="AI家計簿", page_icon="💰", layout="wide")

# ==========================================
# 🧠 画像解析関数
# ==========================================
def analyze_receipt(image_data, model_name):
    try:
        img = Image.open(image_data)
    except:
        st.error("画像の読み込みに失敗しました。")
        return None
    
    # 選ばれたモデルで初期化
    model = genai.GenerativeModel(model_name)

    prompt = """
    あなたはレシート読み取りの専門家です。この画像を解析し、以下の情報を抽出してJSON形式で出力してください。
    - date: 日付 (YYYY-MM-DD形式。年が不明なら今年と仮定。見つからなければ今日の日付)
    - store: 店名 (見つからなければ「不明」)
    - amount: 合計金額 (数値のみ。見つからなければ 0)
    - memo: 品目やメモ (主要な商品をいくつか、または店名を入れる)
    
    出力例:
    {"date": "2023-11-24", "store": "セブンイレブン", "amount": 850, "memo": "おにぎり, お茶"}
    """
    
    try:
        response = model.generate_content([prompt, img])
        response_text = response.text
        cleaned_text = response_text.strip().replace("```json", "").replace("```", "")
        result_json = json.loads(cleaned_text)
        return result_json
    except Exception as e:
        st.error(f"AI解析エラー: {e}")
        return None

# ==========================================
# 🔐 ログイン・新規登録機能
# ==========================================
def login():
    st.title("🔐 AI家計簿アプリ")
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

# データの取得
df_display = pd.DataFrame() 

if user_id == ADMIN_USER:
    response = supabase.table('receipts').select("*").order('date', desc=True).execute()
else:
    response = supabase.table('receipts').select("*").eq('user_id', user_id).order('date', desc=True).execute()

raw_df = pd.DataFrame(response.data)

# --- サイドバー ---
with st.sidebar:
    st.write(f"👤 User: **{user_id}**")
    
    # ==========================================
    # 🤖 AIモデル選択 (ここを修正しました)
    # ==========================================
    st.caption("🤖 AI設定")
    # キー(ID)をリストにして渡し、表示には辞書の値(説明文)を使う
    selected_model_id = st.selectbox(
        "使用するAIモデル",
        options=list(AI_MODELS.keys()),
        format_func=lambda x: AI_MODELS[x]
    )
    # 選択したモデルの説明を表示してあげる
    if "Flash" in AI_MODELS[selected_model_id]:
        st.info("ℹ️ **Flash**: 処理が速いです。普段はこれを使ってください。")
    else:
        st.warning("ℹ️ **Pro**: 賢いですが処理制限があります。Flashで読めない時だけ使いましょう。")

    if user_id == ADMIN_USER:
        st.divider()
        st.caption("👑 管理者メニュー")
        if not raw_df.empty:
            user_list = raw_df['user_id'].unique().tolist()
            user_list.insert(0, "全員 (All Users)")
            selected_view_user = st.selectbox("📊 誰のデータを見る？", user_list)
            
            if selected_view_user == "全員 (All Users)":
                df_display = raw_df.copy()
            else:
                df_display = raw_df[raw_df['user_id'] == selected_view_user].copy()
        else:
            df_display = raw_df.copy()
    else:
        df_display = raw_df.copy()

    if st.button("ログアウト"):
        del st.session_state['user_id']
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
        
    st.divider()
    st.header("✏️ 新規入力")

    try:
        cat_response = supabase.table('categories').select("name").execute()
        category_list = [item['name'] for item in cat_response.data]
        category_list.append("➕ 新しいカテゴリを追加...")
    except:
        category_list = ["食費", "その他"]

    # ==========================================
    # 📁 画像アップロードエリア
    # ==========================================
    st.subheader("1. 画像を選択")
    upload_file = st.file_uploader("レシート画像をアップロード", type=['png', 'jpg', 'jpeg', 'heic'])

    ai_date = today
    ai_memo = ""
    ai_amount = 0

    if upload_file:
        with st.spinner('AIがレシートを解析中...'):
            ai_result = analyze_receipt(upload_file, selected_model_id)
            
            if ai_result:
                st.success("読み取り成功！")
                try:
                    ai_date = datetime.datetime.strptime(ai_result.get('date', str(today)), '%Y-%m-%d').date()
                    ai_store = ai_result.get('store', '')
                    ai_memo_raw = ai_result.get('memo', '')
                    ai_memo = f"{ai_store} {ai_memo_raw}".strip()
                    ai_amount = int(ai_result.get('amount', 0))
                except:
                    st.warning("一部のデータ修正が必要です")

    st.divider()

    # ==========================================
    # 📝 入力フォーム
    # ==========================================
    st.subheader("2. 内容を確認して記録")
    
    with st.form("input_form"):
        date = st.date_input("日付", value=ai_date)
        
        selected_cat = st.selectbox("カテゴリ", category_list)
        if selected_cat == "➕ 新しいカテゴリを追加...":
            st.info("下のメモ欄に新カテゴリ名を入力して保存してください")
            
        memo = st.text_input("メモ・店名", value=ai_memo, placeholder="例: コンビニ")
        amount = st.number_input("金額", value=ai_amount, min_value=0, step=100)
        
        submitted = st.form_submit_button("この内容で記録する", type="primary")
        
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

            if amount == 0:
                st.warning("金額が0円です。確認してください。")
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
            st.rerun()

# --- メインコンテンツ (前回と同じ) ---
st.title("💰 家計簿ダッシュボード")

if not df_display.empty:
    df_display['date'] = pd.to_datetime(df_display['date'])
    
    if user_id == ADMIN_USER:
        unique_users = df_display['user_id'].unique()
        if len(unique_users) > 1:
            st.warning(f"👑 全員（{len(unique_users)}名）のデータを合算表示中")
        else:
            st.success(f"🔍 {unique_users[0]} さんのデータを表示中")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 カテゴリ分析", "📈 推移 (日/週/月)", "📝 履歴一覧", "🔧 修正・削除"])
    
    current_month = today.strftime("%Y-%m")
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
        st.subheader("支出の推移")
        view_mode = st.radio("表示単位", ["日別", "週別", "月別"], horizontal=True)
        df_chart = df_display.copy().set_index('date')
        
        if view_mode == "日別":
            chart_data = df_chart.resample('D')['amount'].sum().reset_index()
            title_text = "日々の支出"
        elif view_mode == "週別":
            chart_data = df_chart.resample('W-MON')['amount'].sum().reset_index()
            title_text = "週ごとの支出 (月曜始まり)"
        else: 
            chart_data = df_chart.resample('MS')['amount'].sum().reset_index()
            chart_data['date'] = chart_data['date'].dt.strftime('%Y-%m')
            title_text = "月ごとの支出"

        fig_bar = px.bar(chart_data, x='date', y='amount', title=title_text)
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
