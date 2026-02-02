import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
from io import BytesIO

# ============ 頁面設定 ============

st.set_page_config(
    page_title="SERP 排名追蹤工具",
    page_icon="📊",
    layout="wide"
)

st.title("📊 SERP 排名追蹤工具")
st.markdown("追蹤你的網站和競爭對手在 Google 香港的排名")

# ============ 側邊欄設定 ============

st.sidebar.header("⚙️ 設定")

# API Key
api_key = st.sidebar.text_input(
    "Serper API Key",
    type="password",
    help="在 serper.dev 註冊取得"
)

# 爬取頁數
max_pages = st.sidebar.slider(
    "爬取頁數",
    min_value=1,
    max_value=10,
    value=5,
    help="每頁 10 個結果"
)

st.sidebar.markdown(f"📄 每個關鍵字將爬取 **{max_pages * 10}** 個結果")

# 我的網站
st.sidebar.header("🏠 我的網站")
my_sites_input = st.sidebar.text_area(
    "每行一個網域",
    value="cateringbear.com\ndaynightcatering.com\nbbqmoment.com\ncateringmoment.com",
    height=120
)
my_sites = [s.strip() for s in my_sites_input.split("\n") if s.strip()]

# 競爭對手
st.sidebar.header("🎯 競爭對手")
competitors_input = st.sidebar.text_area(
    "每行一個網域",
    value="kamadelivery.com\ncateringmama.com\ncateraway.com",
    height=100
)
competitors = [s.strip() for s in competitors_input.split("\n") if s.strip()]

# ============ 主要區域 ============

# 關鍵字輸入
st.header("🔍 關鍵字")
keywords_input = st.text_area(
    "輸入要追蹤的關鍵字（每行一個）",
    value="到會\n到會推介\n派對到會\n公司到會",
    height=150
)
keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

st.info(f"共 {len(keywords)} 個關鍵字，預計使用 {len(keywords) * max_pages} 次 API 調用")


# ============ 函數區 ============

def search_serp(keyword, page, api_key):
    url = "https://google.serper.dev/search"

    payload = {
        "q": keyword,
        "gl": "hk",
        "hl": "zh-tw",
        "num": 10,
        "page": page
    }

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        return data.get("organic", [])
    except Exception as e:
        st.error(f"API 錯誤: {e}")
        return []


def get_all_results(keyword, max_pages, api_key, progress_bar, status_text):
    all_results = []

    for page in range(1, max_pages + 1):
        status_text.text(f"查詢「{keyword}」第 {page}/{max_pages} 頁...")
        results = search_serp(keyword, page, api_key)

        if not results:
            break

        for result in results:
            original_position = result.get("position", 0)
            actual_rank = (page - 1) * 10 + original_position
            result["actual_rank"] = actual_rank
            result["page"] = page

        all_results.extend(results)
        progress_bar.progress(page / max_pages)
        time.sleep(0.3)

    return all_results


def find_ranking(results, domain):
    for result in results:
        link = result.get("link", "")
        if domain in link:
            return result.get("actual_rank", "N/A")
    return "N/A"


def create_excel(all_rankings, all_serp_data, my_sites, competitors):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        # Sheet 1: 排名總覽
        df_rankings = pd.DataFrame(all_rankings)
        columns = ["keyword"] + my_sites + competitors
        available_columns = [c for c in columns if c in df_rankings.columns]
        df_rankings = df_rankings[available_columns]
        df_rankings.to_excel(writer, sheet_name="排名總覽", index=False)

        # Sheet 2: 完整 SERP 數據
        serp_records = []
        for keyword, results in all_serp_data.items():
            for result in results:
                serp_records.append({
                    "關鍵字": keyword,
                    "排名": result.get("actual_rank"),
                    "標題": result.get("title"),
                    "網址": result.get("link"),
                    "描述": result.get("snippet", "")[:100]
                })

        df_serp = pd.DataFrame(serp_records)
        df_serp.to_excel(writer, sheet_name="完整SERP數據", index=False)

        # Sheet 3: 我的網站詳情
        my_site_records = []
        for keyword, results in all_serp_data.items():
            for result in results:
                link = result.get("link", "")
                for site in my_sites:
                    if site in link:
                        my_site_records.append({
                            "關鍵字": keyword,
                            "網站": site,
                            "排名": result.get("actual_rank"),
                            "標題": result.get("title"),
                            "網址": link
                        })

        if my_site_records:
            df_my_sites = pd.DataFrame(my_site_records)
            df_my_sites.to_excel(writer, sheet_name="我的網站詳情", index=False)

        # Sheet 4: 競爭對手詳情
        competitor_records = []
        for keyword, results in all_serp_data.items():
            for result in results:
                link = result.get("link", "")
                for site in competitors:
                    if site in link:
                        competitor_records.append({
                            "關鍵字": keyword,
                            "網站": site,
                            "排名": result.get("actual_rank"),
                            "標題": result.get("title"),
                            "網址": link
                        })

        if competitor_records:
            df_competitors = pd.DataFrame(competitor_records)
            df_competitors.to_excel(writer, sheet_name="競爭對手詳情", index=False)

    output.seek(0)
    return output


# ============ 執行按鈕 ============

st.markdown("---")

if st.button("🚀 開始追蹤", type="primary", use_container_width=True):

    # 驗證
    if not api_key:
        st.error("請輸入 API Key")
        st.stop()

    if not keywords:
        st.error("請輸入至少一個關鍵字")
        st.stop()

    if not my_sites and not competitors:
        st.error("請輸入至少一個要追蹤的網站")
        st.stop()

    all_sites = my_sites + competitors
    all_rankings = []
    all_serp_data = {}

    # 進度顯示
    overall_progress = st.progress(0)
    status_text = st.empty()

    for i, keyword in enumerate(keywords):
        st.markdown(f"### 正在分析：{keyword}")

        keyword_progress = st.progress(0)
        keyword_status = st.empty()

        results = get_all_results(keyword, max_pages, api_key, keyword_progress, keyword_status)

        if results:
            rankings = {"keyword": keyword}
            for site in all_sites:
                rank = find_ranking(results, site)
                rankings[site] = rank

            all_rankings.append(rankings)
            all_serp_data[keyword] = results

            keyword_status.text(f"✅ 完成！取得 {len(results)} 個結果")
        else:
            keyword_status.text("❌ 沒有取得結果")

        overall_progress.progress((i + 1) / len(keywords))

    status_text.text("✅ 全部完成！")

    # 顯示結果
    st.markdown("---")
    st.header("📊 排名結果")

    if all_rankings:
        df_rankings = pd.DataFrame(all_rankings)


        # 用顏色標示排名
        def highlight_rank(val):
            if val == "N/A":
                return "background-color: #ffcccc"
            elif isinstance(val, int):
                if val <= 3:
                    return "background-color: #90EE90"  # 綠色 - 前3
                elif val <= 10:
                    return "background-color: #FFFFE0"  # 黃色 - 首頁
                elif val <= 20:
                    return "background-color: #FFE4B5"  # 橙色 - 第2頁
            return ""


        st.dataframe(
            df_rankings.style.applymap(highlight_rank, subset=my_sites + competitors),
            use_container_width=True
        )

        # 下載按鈕
        excel_file = create_excel(all_rankings, all_serp_data, my_sites, competitors)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        st.download_button(
            label="📥 下載 Excel 報告",
            data=excel_file,
            file_name=f"serp_ranking_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        # 顯示詳細數據
        with st.expander("📋 查看完整 SERP 數據"):
            for keyword, results in all_serp_data.items():
                st.subheader(f"關鍵字：{keyword}")
                df = pd.DataFrame([{
                    "排名": r.get("actual_rank"),
                    "標題": r.get("title"),
                    "網址": r.get("link")
                } for r in results])
                st.dataframe(df, use_container_width=True)

# ============ 頁尾 ============

st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: gray;">
        Made with ❤️ | Powered by Serper API
    </div>
    """,
    unsafe_allow_html=True

)
