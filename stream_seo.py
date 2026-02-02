import streamlit as st
import requests
import pandas as pd
import time
import json
import os
from datetime import datetime, timedelta
from io import BytesIO

# ============ 頁面設定 ============

st.set_page_config(
    page_title="SEO 排名追蹤工具 Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ 自訂 CSS ============

st.markdown("""
<style>
    /* 主要容器 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }

    /* 統計卡片 */
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 4px solid #667eea;
    }

    .stat-number {
        font-size: 2.5rem;
        font-weight: bold;
        color: #667eea;
    }

    .stat-label {
        color: #666;
        font-size: 0.9rem;
    }

    /* 排名變化 */
    .rank-up {
        color: #10B981;
        font-weight: bold;
    }

    .rank-down {
        color: #EF4444;
        font-weight: bold;
    }

    .rank-same {
        color: #6B7280;
    }

    /* 排名徽章 */
    .rank-badge-top3 {
        background: linear-gradient(135deg, #10B981, #059669);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
    }

    .rank-badge-top10 {
        background: linear-gradient(135deg, #F59E0B, #D97706);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
    }

    .rank-badge-top20 {
        background: linear-gradient(135deg, #6B7280, #4B5563);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
    }

    .rank-badge-na {
        background: #FEE2E2;
        color: #DC2626;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
    }

    /* 側邊欄美化 */
    .sidebar .sidebar-content {
        background: #f8f9fa;
    }

    /* 按鈕美化 */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-weight: bold;
    }

    /* 標籤頁 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# ============ 數據儲存功能 ============

DATA_FILE = "serp_history.json"


def load_history():
    """載入歷史記錄"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"records": [], "settings": {}}
    return {"records": [], "settings": {}}


def save_history(data):
    """儲存歷史記錄"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(history, record):
    """新增記錄"""
    record["timestamp"] = datetime.now().isoformat()
    record["date"] = datetime.now().strftime("%Y-%m-%d")
    history["records"].append(record)
    save_history(history)
    return history


# ============ 初始化 Session State ============

if "history" not in st.session_state:
    st.session_state.history = load_history()

if "current_results" not in st.session_state:
    st.session_state.current_results = None

# ============ 標題 ============

st.markdown("""
<div class="main-header">
    <h1>🚀 SEO 排名追蹤工具 Pro</h1>
    <p>追蹤排名變化 · 分析競爭對手 · 優化 SEO 策略</p>
</div>
""", unsafe_allow_html=True)

# ============ 側邊欄設定 ============

with st.sidebar:
    st.markdown("## ⚙️ 設定")

    # API Key
    api_key = st.text_input(
        "🔑 Serper API Key",
        type="password",
        help="在 serper.dev 註冊取得免費 API Key"
    )

    if api_key:
        st.success("✅ API Key 已設定")
    else:
        st.warning("⚠️ 請輸入 API Key")

    st.markdown("---")

    # 搜尋設定
    st.markdown("### 🔍 搜尋設定")

    col1, col2 = st.columns(2)
    with col1:
        search_region = st.selectbox(
            "地區",
            options=["hk", "tw", "sg", "my", "us", "uk"],
            format_func=lambda x: {
                "hk": "🇭🇰 香港",
                "tw": "🇹🇼 台灣",
                "sg": "🇸🇬 新加坡",
                "my": "🇲🇾 馬來西亞",
                "us": "🇺🇸 美國",
                "uk": "🇬🇧 英國"
            }[x]
        )

    with col2:
        search_lang = st.selectbox(
            "語言",
            options=["zh-tw", "zh-cn", "en"],
            format_func=lambda x: {
                "zh-tw": "繁體中文",
                "zh-cn": "简体中文",
                "en": "English"
            }[x]
        )

    max_pages = st.slider(
        "📄 爬取頁數",
        min_value=1,
        max_value=10,
        value=5,
        help="每頁 10 個結果"
    )

    st.info(f"每個關鍵字將爬取 **{max_pages * 10}** 個結果")

    st.markdown("---")

    # 我的網站
    st.markdown("### 🏠 我的網站")
    my_sites_input = st.text_area(
        "每行一個網域",
        value="example.com",
        height=100,
        key="my_sites"
    )
    my_sites = [s.strip() for s in my_sites_input.split("\n") if s.strip()]

    # 競爭對手
    st.markdown("### 🎯 競爭對手")
    competitors_input = st.text_area(
        "每行一個網域",
        value="competitor1.com\ncompetitor2.com",
        height=100,
        key="competitors"
    )
    competitors = [s.strip() for s in competitors_input.split("\n") if s.strip()]

    st.markdown("---")

    # 歷史記錄統計
    st.markdown("### 📊 數據統計")
    total_records = len(st.session_state.history.get("records", []))
    st.metric("總記錄數", total_records)

# ============ 主要區域 - 標籤頁 ============

tab1, tab2, tab3, tab4 = st.tabs(["🔍 排名查詢", "📈 歷史趨勢", "📊 數據分析", "⚙️ 管理"])

# ============ Tab 1: 排名查詢 ============

with tab1:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("### 📝 輸入關鍵字")
        keywords_input = st.text_area(
            "每行一個關鍵字",
            value="到會\n到會推介\n派對到會",
            height=200,
            key="keywords_input"
        )
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

    with col_right:
        st.markdown("### 📋 快速匯入")

        # 關鍵字分組
        keyword_groups = {
            "到會相關": ["到會", "到會推介", "到會服務", "派對到會", "公司到會", "到會外賣"],
            "餐飲相關": ["catering", "外賣", "訂餐", "宴會"],
            "自訂": []
        }

        selected_group = st.selectbox("選擇關鍵字組", list(keyword_groups.keys()))

        if selected_group != "自訂" and keyword_groups[selected_group]:
            if st.button("📥 匯入此組關鍵字"):
                st.session_state.keywords_input = "\n".join(keyword_groups[selected_group])
                st.rerun()

        st.markdown("---")
        st.markdown(f"**共 {len(keywords)} 個關鍵字**")
        st.markdown(f"**預計 API 調用：{len(keywords) * max_pages} 次**")

    st.markdown("---")

    # 執行按鈕
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        start_tracking = st.button("🚀 開始追蹤排名", type="primary", use_container_width=True)

    # ============ 執行搜尋 ============

    if start_tracking:
        if not api_key:
            st.error("❌ 請先在側邊欄輸入 API Key")
            st.stop()

        if not keywords:
            st.error("❌ 請輸入至少一個關鍵字")
            st.stop()

        all_sites = my_sites + competitors
        if not all_sites:
            st.error("❌ 請輸入至少一個要追蹤的網站")
            st.stop()

        # 進度顯示
        progress_container = st.container()
        with progress_container:
            overall_progress = st.progress(0)
            status_text = st.empty()

        all_rankings = []
        all_serp_data = {}


        def search_serp(keyword, page, api_key):
            url = "https://google.serper.dev/search"
            payload = {
                "q": keyword,
                "gl": search_region,
                "hl": search_lang,
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


        def get_all_results(keyword, max_pages, api_key):
            all_results = []
            for page in range(1, max_pages + 1):
                status_text.text(f"🔍 查詢「{keyword}」第 {page}/{max_pages} 頁...")
                results = search_serp(keyword, page, api_key)
                if not results:
                    break
                for result in results:
                    original_position = result.get("position", 0)
                    actual_rank = (page - 1) * 10 + original_position
                    result["actual_rank"] = actual_rank
                    result["page"] = page
                all_results.extend(results)
                time.sleep(0.3)
            return all_results


        def find_ranking(results, domain):
            for result in results:
                link = result.get("link", "")
                if domain in link:
                    return result.get("actual_rank", None)
            return None


        # 執行搜尋
        for i, keyword in enumerate(keywords):
            results = get_all_results(keyword, max_pages, api_key)

            if results:
                rankings = {"keyword": keyword}
                for site in all_sites:
                    rank = find_ranking(results, site)
                    rankings[site] = rank
                all_rankings.append(rankings)
                all_serp_data[keyword] = results

            overall_progress.progress((i + 1) / len(keywords))

        status_text.text("✅ 完成！")

        # 儲存結果
        st.session_state.current_results = {
            "rankings": all_rankings,
            "serp_data": all_serp_data,
            "timestamp": datetime.now().isoformat()
        }

        # 加入歷史記錄
        record = {
            "rankings": all_rankings,
            "my_sites": my_sites,
            "competitors": competitors,
            "region": search_region
        }
        st.session_state.history = add_record(st.session_state.history, record)

        st.success("✅ 數據已儲存到歷史記錄")

    # ============ 顯示結果 ============

    if st.session_state.current_results:
        st.markdown("---")
        st.markdown("## 📊 排名結果")

        results = st.session_state.current_results
        rankings = results["rankings"]
        all_sites = my_sites + competitors

        # 獲取上次記錄用於比較
        history_records = st.session_state.history.get("records", [])
        previous_rankings = {}
        if len(history_records) >= 2:
            prev_record = history_records[-2]
            for item in prev_record.get("rankings", []):
                kw = item.get("keyword")
                previous_rankings[kw] = item

        # 統計卡片
        st.markdown("### 📈 總覽")

        col1, col2, col3, col4 = st.columns(4)

        # 計算統計
        top3_count = 0
        top10_count = 0
        improved_count = 0
        declined_count = 0

        for rank_data in rankings:
            for site in my_sites:
                rank = rank_data.get(site)
                if rank is not None:
                    if rank <= 3:
                        top3_count += 1
                    if rank <= 10:
                        top10_count += 1

                    # 比較變化
                    kw = rank_data.get("keyword")
                    if kw in previous_rankings:
                        prev_rank = previous_rankings[kw].get(site)
                        if prev_rank is not None:
                            if rank < prev_rank:
                                improved_count += 1
                            elif rank > prev_rank:
                                declined_count += 1

        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{top3_count}</div>
                <div class="stat-label">🏆 前 3 名</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{top10_count}</div>
                <div class="stat-label">📄 首頁排名</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number" style="color: #10B981;">{improved_count}</div>
                <div class="stat-label">📈 排名上升</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number" style="color: #EF4444;">{declined_count}</div>
                <div class="stat-label">📉 排名下降</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # 詳細排名表格
        st.markdown("### 📋 詳細排名")

        # 建立顯示用的 DataFrame
        display_data = []
        for rank_data in rankings:
            row = {"關鍵字": rank_data.get("keyword")}

            for site in all_sites:
                rank = rank_data.get(site)
                kw = rank_data.get("keyword")

                # 計算變化
                change = ""
                if kw in previous_rankings:
                    prev_rank = previous_rankings[kw].get(site)
                    if prev_rank is not None and rank is not None:
                        diff = prev_rank - rank  # 正數表示上升
                        if diff > 0:
                            change = f" ↑{diff}"
                        elif diff < 0:
                            change = f" ↓{abs(diff)}"
                        else:
                            change = " ─"

                if rank is not None:
                    row[site] = f"{rank}{change}"
                else:
                    row[site] = "N/A"

            display_data.append(row)

        df_display = pd.DataFrame(display_data)


        # 顯示表格
        def highlight_ranking(val):
            if "N/A" in str(val):
                return "background-color: #FEE2E2; color: #DC2626;"
            try:
                rank = int(str(val).split()[0].replace("↑", "").replace("↓", "").replace("─", ""))
                if rank <= 3:
                    return "background-color: #D1FAE5; color: #065F46; font-weight: bold;"
                elif rank <= 10:
                    return "background-color: #FEF3C7; color: #92400E;"
                elif rank <= 20:
                    return "background-color: #F3F4F6; color: #374151;"
            except:
                pass
            return ""


        st.dataframe(
            df_display.style.applymap(highlight_ranking, subset=all_sites),
            use_container_width=True,
            height=400
        )

        # 圖例說明
        st.markdown("""
        **圖例：** 
        🟢 前 3 名 | 🟡 首頁 (4-10) | ⚪ 第二頁 (11-20) | 🔴 未上榜
        | ↑ 上升 | ↓ 下降 | ─ 持平
        """)

        # 下載按鈕
        st.markdown("---")


        def create_excel(rankings, serp_data, my_sites, competitors):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # 排名總覽
                df_rankings = pd.DataFrame(rankings)
                df_rankings.to_excel(writer, sheet_name="排名總覽", index=False)

                # 完整 SERP
                serp_records = []
                for keyword, results in serp_data.items():
                    for result in results:
                        serp_records.append({
                            "關鍵字": keyword,
                            "排名": result.get("actual_rank"),
                            "標題": result.get("title"),
                            "網址": result.get("link"),
                            "描述": result.get("snippet", "")[:200]
                        })
                df_serp = pd.DataFrame(serp_records)
                df_serp.to_excel(writer, sheet_name="完整SERP", index=False)

            output.seek(0)
            return output


        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            excel_file = create_excel(
                rankings,
                results.get("serp_data", {}),
                my_sites,
                competitors
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 下載 Excel 報告",
                data=excel_file,
                file_name=f"serp_ranking_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col_dl2:
            csv_data = df_display.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 下載 CSV",
                data=csv_data,
                file_name=f"serp_ranking_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True
            )

# ============ Tab 2: 歷史趨勢 ============

with tab2:
    st.markdown("### 📈 排名趨勢圖")

    history_records = st.session_state.history.get("records", [])

    if len(history_records) < 2:
        st.info("📊 需要至少 2 次記錄才能顯示趨勢圖。請先執行排名查詢。")
    else:
        # 收集所有關鍵字
        all_keywords = set()
        all_tracked_sites = set()
        for record in history_records:
            for item in record.get("rankings", []):
                all_keywords.add(item.get("keyword"))
            all_tracked_sites.update(record.get("my_sites", []))
            all_tracked_sites.update(record.get("competitors", []))

        # 選擇要查看的關鍵字和網站
        col1, col2 = st.columns(2)
        with col1:
            selected_keyword = st.selectbox("選擇關鍵字", sorted(list(all_keywords)))
        with col2:
            selected_site = st.selectbox("選擇網站", sorted(list(all_tracked_sites)))

        # 建立趨勢數據
        trend_data = []
        for record in history_records:
            date = record.get("date", "未知")
            for item in record.get("rankings", []):
                if item.get("keyword") == selected_keyword:
                    rank = item.get(selected_site)
                    trend_data.append({
                        "日期": date,
                        "排名": rank if rank is not None else None
                    })
                    break

        if trend_data:
            df_trend = pd.DataFrame(trend_data)
            df_trend = df_trend.dropna()

            if not df_trend.empty:
                # 使用 Streamlit 內建圖表
                st.markdown(f"**「{selected_keyword}」在 {selected_site} 的排名變化**")

                # 反轉排名顯示（排名越低越好）
                df_trend["排名（越低越好）"] = df_trend["排名"]
                st.line_chart(df_trend.set_index("日期")["排名（越低越好）"])

                # 顯示數據表
                st.markdown("#### 📋 歷史數據")
                st.dataframe(df_trend, use_container_width=True)

                # 計算統計
                st.markdown("#### 📊 統計摘要")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("最佳排名", int(df_trend["排名"].min()))
                with col2:
                    st.metric("最差排名", int(df_trend["排名"].max()))
                with col3:
                    st.metric("平均排名", f"{df_trend['排名'].mean():.1f}")
                with col4:
                    if len(df_trend) >= 2:
                        change = df_trend["排名"].iloc[0] - df_trend["排名"].iloc[-1]
                        st.metric("總變化", f"{change:+.0f}", delta=f"{change:+.0f}")
            else:
                st.warning("此關鍵字/網站組合沒有排名數據")
        else:
            st.warning("沒有找到相關數據")

# ============ Tab 3: 數據分析 ============

with tab3:
    st.markdown("### 📊 SEO 數據分析")

    history_records = st.session_state.history.get("records", [])

    if not history_records:
        st.info("📊 還沒有數據。請先執行排名查詢。")
    else:
        latest_record = history_records[-1]
        rankings = latest_record.get("rankings", [])
        tracked_my_sites = latest_record.get("my_sites", [])
        tracked_competitors = latest_record.get("competitors", [])

        if rankings:
            st.markdown("#### 🏆 排名分佈（我的網站）")

            # 計算各排名區間數量
            rank_distribution = {"前3名": 0, "首頁(4-10)": 0, "第2頁(11-20)": 0, "20名外": 0, "未上榜": 0}

            for item in rankings:
                for site in tracked_my_sites:
                    rank = item.get(site)
                    if rank is None:
                        rank_distribution["未上榜"] += 1
                    elif rank <= 3:
                        rank_distribution["前3名"] += 1
                    elif rank <= 10:
                        rank_distribution["首頁(4-10)"] += 1
                    elif rank <= 20:
                        rank_distribution["第2頁(11-20)"] += 1
                    else:
                        rank_distribution["20名外"] += 1

            df_dist = pd.DataFrame([rank_distribution])
            st.bar_chart(df_dist.T)

            # 競爭對手比較
            st.markdown("#### ⚔️ 與競爭對手比較")

            comparison_data = []
            all_sites = tracked_my_sites + tracked_competitors

            for site in all_sites:
                site_stats = {"網站": site, "平均排名": 0, "首頁數": 0, "總關鍵字": 0}
                ranks = []
                for item in rankings:
                    rank = item.get(site)
                    if rank is not None:
                        ranks.append(rank)
                        if rank <= 10:
                            site_stats["首頁數"] += 1

                if ranks:
                    site_stats["平均排名"] = round(sum(ranks) / len(ranks), 1)
                    site_stats["總關鍵字"] = len(ranks)

                site_stats["類型"] = "我的網站" if site in tracked_my_sites else "競爭對手"
                comparison_data.append(site_stats)

            df_comparison = pd.DataFrame(comparison_data)
            st.dataframe(df_comparison, use_container_width=True)

            # SEO 建議
            st.markdown("#### 💡 SEO 建議")

            suggestions = []
            for item in rankings:
                kw = item.get("keyword")
                for site in tracked_my_sites:
                    rank = item.get(site)
                    if rank is None:
                        suggestions.append(f"❌ **{kw}**：未上榜，建議建立相關內容頁面")
                    elif rank > 10 and rank <= 20:
                        suggestions.append(f"🔶 **{kw}**：排名 {rank}，距離首頁只差一點，建議優化內容和建立反向連結")
                    elif rank > 20:
                        suggestions.append(f"⚠️ **{kw}**：排名 {rank}，需要較大幅度的 SEO 優化")

            if suggestions:
                for s in suggestions[:10]:  # 只顯示前 10 個
                    st.markdown(s)
                if len(suggestions) > 10:
                    st.markdown(f"... 還有 {len(suggestions) - 10} 個建議")
            else:
                st.success("🎉 表現很好！大部分關鍵字都在首頁")

# ============ Tab 4: 管理 ============

with tab4:
    st.markdown("### ⚙️ 數據管理")

    history_records = st.session_state.history.get("records", [])

    st.markdown(f"**總記錄數：** {len(history_records)}")

    if history_records:
        # 顯示歷史記錄列表
        st.markdown("#### 📜 歷史記錄")

        for i, record in enumerate(reversed(history_records)):
            date = record.get("date", "未知")
            timestamp = record.get("timestamp", "")
            keyword_count = len(record.get("rankings", []))

            with st.expander(f"📅 {date} ({keyword_count} 個關鍵字)"):
                st.json(record.get("rankings", []))

        st.markdown("---")

        # 匯出所有數據
        st.markdown("#### 💾 匯出數據")

        col1, col2 = st.columns(2)

        with col1:
            json_data = json.dumps(st.session_state.history, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 匯出 JSON 備份",
                data=json_data,
                file_name=f"serp_history_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )

        with col2:
            # 匯出為 Excel
            all_records = []
            for record in history_records:
                date = record.get("date", "")
                for item in record.get("rankings", []):
                    row = {"日期": date, **item}
                    all_records.append(row)

            if all_records:
                df_all = pd.DataFrame(all_records)
                output = BytesIO()
                df_all.to_excel(output, index=False, engine="openpyxl")
                output.seek(0)

                st.download_button(
                    label="📥 匯出所有歷史 Excel",
                    data=output,
                    file_name=f"serp_all_history_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        st.markdown("---")

        # 清除數據
        st.markdown("#### 🗑️ 清除數據")
        st.warning("⚠️ 此操作無法復原")

        if st.button("🗑️ 清除所有歷史記錄", type="secondary"):
            st.session_state.history = {"records": [], "settings": {}}
            save_history(st.session_state.history)
            st.success("✅ 已清除所有記錄")
            st.rerun()
    else:
        st.info("還沒有歷史記錄")

    # 匯入數據
    st.markdown("---")
    st.markdown("#### 📤 匯入數據")

    uploaded_file = st.file_uploader("上傳 JSON 備份檔案", type=["json"])
    if uploaded_file:
        try:
            imported_data = json.load(uploaded_file)
            if st.button("確認匯入"):
                st.session_state.history = imported_data
                save_history(imported_data)
                st.success("✅ 匯入成功！")
                st.rerun()
        except Exception as e:
            st.error(f"匯入失敗：{e}")

# ============ 頁尾 ============

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>🚀 SEO 排名追蹤工具 Pro</p>
    <p style="font-size: 0.8rem;">Powered by Serper API | Made with Streamlit</p>
</div>
""", unsafe_allow_html=True)
