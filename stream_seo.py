import streamlit as st
import requests
import pandas as pd
import time
import json
import os
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import BytesIO
import threading

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
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }
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
    .speed-badge {
        background: linear-gradient(135deg, #10B981, #059669);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        margin-left: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ============ 數據儲存功能 ============

DATA_FILE = "serp_history.json"


def load_history():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"records": [], "settings": {}}
    return {"records": [], "settings": {}}


def save_history(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(history, record):
    record["timestamp"] = datetime.now().isoformat()
    record["date"] = datetime.now().strftime("%Y-%m-%d")
    history["records"].append(record)
    save_history(history)
    return history


# ============ 高速異步搜尋引擎 ============

class FastSerpSearcher:
    """高速 SERP 搜尋器 - 使用異步並行請求"""

    def __init__(self, api_key, region="hk", lang="zh-tw", max_concurrent=20):
        self.api_key = api_key
        self.region = region
        self.lang = lang
        self.max_concurrent = max_concurrent  # 最大並發數
        self.results_cache = {}

    async def _fetch_single(self, session, keyword, page, semaphore):
        """異步獲取單個搜尋結果"""
        async with semaphore:
            url = "https://google.serper.dev/search"
            payload = {
                "q": keyword,
                "gl": self.region,
                "hl": self.lang,
                "num": 10,
                "page": page
            }
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            try:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("organic", [])

                        # 計算實際排名
                        for result in results:
                            original_position = result.get("position", 0)
                            result["actual_rank"] = (page - 1) * 10 + original_position
                            result["page"] = page

                        return {
                            "keyword": keyword,
                            "page": page,
                            "results": results,
                            "success": True
                        }
                    else:
                        return {
                            "keyword": keyword,
                            "page": page,
                            "results": [],
                            "success": False,
                            "error": f"HTTP {response.status}"
                        }
            except Exception as e:
                return {
                    "keyword": keyword,
                    "page": page,
                    "results": [],
                    "success": False,
                    "error": str(e)
                }

    async def search_all_async(self, keywords, max_pages, progress_callback=None):
        """異步並行搜尋所有關鍵字"""

        # 建立所有任務
        tasks = []
        for keyword in keywords:
            for page in range(1, max_pages + 1):
                tasks.append((keyword, page))

        total_tasks = len(tasks)
        completed = 0

        # 限制並發數
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # 使用連接池
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, limit_per_host=self.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=30)

        all_results = {}

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 建立協程任務
            coroutines = [
                self._fetch_single(session, keyword, page, semaphore)
                for keyword, page in tasks
            ]

            # 並行執行所有任務
            for coro in asyncio.as_completed(coroutines):
                result = await coro
                completed += 1

                keyword = result["keyword"]
                if keyword not in all_results:
                    all_results[keyword] = []

                if result["success"]:
                    all_results[keyword].extend(result["results"])

                # 更新進度
                if progress_callback:
                    progress_callback(completed, total_tasks, keyword)

        # 排序結果
        for keyword in all_results:
            all_results[keyword].sort(key=lambda x: x.get("actual_rank", 999))

        return all_results

    def search_all(self, keywords, max_pages, progress_callback=None):
        """同步包裝器 - 在 Streamlit 中調用"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.search_all_async(keywords, max_pages, progress_callback)
            )
        finally:
            loop.close()


class ThreadedSerpSearcher:
    """多線程 SERP 搜尋器 - 備用方案"""

    def __init__(self, api_key, region="hk", lang="zh-tw", max_workers=20):
        self.api_key = api_key
        self.region = region
        self.lang = lang
        self.max_workers = max_workers
        self.session = requests.Session()

        # 設定連接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers,
            pool_maxsize=max_workers,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def _fetch_single(self, keyword, page):
        """獲取單個搜尋結果"""
        url = "https://google.serper.dev/search"
        payload = {
            "q": keyword,
            "gl": self.region,
            "hl": self.lang,
            "num": 10,
            "page": page
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get("organic", [])

                for result in results:
                    original_position = result.get("position", 0)
                    result["actual_rank"] = (page - 1) * 10 + original_position
                    result["page"] = page

                return {
                    "keyword": keyword,
                    "page": page,
                    "results": results,
                    "success": True
                }
        except Exception as e:
            pass

        return {
            "keyword": keyword,
            "page": page,
            "results": [],
            "success": False
        }

    def search_all(self, keywords, max_pages, progress_callback=None):
        """多線程並行搜尋"""

        # 建立所有任務
        tasks = [(kw, page) for kw in keywords for page in range(1, max_pages + 1)]
        total_tasks = len(tasks)
        completed = 0

        all_results = {kw: [] for kw in keywords}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任務
            future_to_task = {
                executor.submit(self._fetch_single, kw, page): (kw, page)
                for kw, page in tasks
            }

            # 收集結果
            for future in as_completed(future_to_task):
                result = future.result()
                completed += 1

                keyword = result["keyword"]
                if result["success"]:
                    all_results[keyword].extend(result["results"])

                if progress_callback:
                    progress_callback(completed, total_tasks, keyword)

        # 排序
        for keyword in all_results:
            all_results[keyword].sort(key=lambda x: x.get("actual_rank", 999))

        return all_results


# ============ 排名分析工具 ============

def find_rankings(serp_results, sites):
    """從 SERP 結果中找出指定網站的排名"""
    rankings = []

    for keyword, results in serp_results.items():
        row = {"keyword": keyword}

        for site in sites:
            rank = None
            for result in results:
                if site in result.get("link", ""):
                    rank = result.get("actual_rank")
                    break
            row[site] = rank

        rankings.append(row)

    return rankings


# ============ 初始化 Session State ============

if "history" not in st.session_state:
    st.session_state.history = load_history()

if "current_results" not in st.session_state:
    st.session_state.current_results = None

# ============ 標題 ============

st.markdown("""
<div class="main-header">
    <h1>🚀 SEO 排名追蹤工具 Pro <span class="speed-badge">⚡ 50x 高速版</span></h1>
    <p>異步並行搜尋 · 追蹤排名變化 · 分析競爭對手</p>
</div>
""", unsafe_allow_html=True)

# ============ 側邊欄設定 ============

with st.sidebar:
    st.markdown("## ⚙️ 設定")

    api_key = st.text_input(
        "🔑 Serper API Key",
        type="password",
        help="在 serper.dev 註冊取得免費 API Key"
    )

    if api_key:
        st.success("✅ API Key 已設定")
    else:
        st.warning("⚠️ 請輸入 API Key123")

    st.markdown("---")

    st.markdown("### 🔍 搜尋設定")

    col1, col2 = st.columns(2)
    with col1:
        search_region = st.selectbox(
            "地區",
            options=["hk", "tw", "sg", "my", "us", "uk"],
            format_func=lambda x: {
                "hk": "🇭🇰 香港", "tw": "🇹🇼 台灣", "sg": "🇸🇬 新加坡",
                "my": "🇲🇾 馬來西亞", "us": "🇺🇸 美國", "uk": "🇬🇧 英國"
            }[x]
        )

    with col2:
        search_lang = st.selectbox(
            "語言",
            options=["zh-tw", "zh-cn", "en"],
            format_func=lambda x: {"zh-tw": "繁體中文", "zh-cn": "简体中文", "en": "English"}[x]
        )

    max_pages = st.slider("📄 爬取頁數", 1, 10, 5)

    st.markdown("---")

    # 速度設定
    st.markdown("### ⚡ 速度設定")

    search_method = st.radio(
        "搜尋方式",
        options=["async", "thread"],
        format_func=lambda x: {
            "async": "⚡ 異步 (最快)",
            "thread": "🔄 多線程 (穩定)"
        }[x],
        index=0
    )

    max_concurrent = st.slider(
        "最大並發數",
        min_value=5,
        max_value=50,
        value=20,
        help="越高越快，但可能觸發 API 限制"
    )

    st.info(f"⚡ 預估速度提升: **{max_concurrent}x**")

    st.markdown("---")

    st.markdown("### 🏠 我的網站")
    my_sites_input = st.text_area(
        "每行一個網域",
        value="example.com",
        height=100,
        key="my_sites"
    )
    my_sites = [s.strip() for s in my_sites_input.split("\n") if s.strip()]

    st.markdown("### 🎯 競爭對手")
    competitors_input = st.text_area(
        "每行一個網域",
        value="competitor1.com\ncompetitor2.com",
        height=100,
        key="competitors"
    )
    competitors = [s.strip() for s in competitors_input.split("\n") if s.strip()]

    st.markdown("---")

    st.markdown("### 📊 數據統計")
    total_records = len(st.session_state.history.get("records", []))
    st.metric("總記錄數", total_records)

# ============ 主要區域 ============

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
        st.markdown("### 📋 查詢資訊")

        keyword_groups = {
            "到會相關": ["到會", "到會推介", "到會服務", "派對到會", "公司到會", "到會外賣"],
            "餐飲相關": ["catering", "外賣", "訂餐", "宴會"],
        }

        selected_group = st.selectbox("快速匯入關鍵字組", ["選擇..."] + list(keyword_groups.keys()))

        if selected_group != "選擇..." and st.button("📥 匯入"):
            st.session_state.keywords_input = "\n".join(keyword_groups[selected_group])
            st.rerun()

        st.markdown("---")

        total_requests = len(keywords) * max_pages
        st.markdown(f"**關鍵字數量：** {len(keywords)}")
        st.markdown(f"**API 請求數：** {total_requests}")
        st.markdown(f"**並發數：** {max_concurrent}")

        # 預估時間
        if search_method == "async":
            est_time = max(total_requests / max_concurrent * 0.5, 2)
        else:
            est_time = max(total_requests / max_concurrent * 0.8, 3)

        st.markdown(f"**預估時間：** ~{est_time:.0f} 秒")

        # 對比傳統時間
        traditional_time = total_requests * 0.5
        speedup = traditional_time / est_time
        st.markdown(f"**速度提升：** 🚀 **{speedup:.0f}x**")

    st.markdown("---")

    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        start_tracking = st.button("🚀 開始高速追蹤", type="primary", use_container_width=True)

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
            col1, col2 = st.columns([3, 1])
            with col1:
                progress_bar = st.progress(0)
                status_text = st.empty()
            with col2:
                time_display = st.empty()

        start_time = time.time()


        # 進度回調函數
        def update_progress(completed, total, current_keyword):
            progress = completed / total
            progress_bar.progress(progress)
            elapsed = time.time() - start_time
            status_text.text(f"⚡ 已完成 {completed}/{total} | 目前: {current_keyword}")
            time_display.markdown(f"**⏱️ {elapsed:.1f}s**")


        # 選擇搜尋方式
        if search_method == "async":
            searcher = FastSerpSearcher(
                api_key=api_key,
                region=search_region,
                lang=search_lang,
                max_concurrent=max_concurrent
            )
        else:
            searcher = ThreadedSerpSearcher(
                api_key=api_key,
                region=search_region,
                lang=search_lang,
                max_workers=max_concurrent
            )

        # 執行搜尋
        serp_results = searcher.search_all(keywords, max_pages, update_progress)

        # 計算耗時
        elapsed_time = time.time() - start_time

        # 提取排名
        all_rankings = find_rankings(serp_results, all_sites)

        # 完成
        progress_bar.progress(1.0)
        status_text.text(f"✅ 完成！共耗時 {elapsed_time:.1f} 秒")

        # 顯示速度統計
        total_requests = len(keywords) * max_pages
        traditional_time = total_requests * 0.5
        actual_speedup = traditional_time / elapsed_time

        st.success(f"""
        ✅ **搜尋完成！**
        - 總請求數：{total_requests}
        - 實際耗時：{elapsed_time:.1f} 秒
        - 傳統方式預估：{traditional_time:.0f} 秒
        - 🚀 **實際加速：{actual_speedup:.1f}x**
        """)

        # 儲存結果
        st.session_state.current_results = {
            "rankings": all_rankings,
            "serp_data": serp_results,
            "timestamp": datetime.now().isoformat(),
            "elapsed_time": elapsed_time
        }

        record = {
            "rankings": all_rankings,
            "my_sites": my_sites,
            "competitors": competitors,
            "region": search_region
        }
        st.session_state.history = add_record(st.session_state.history, record)

    # ============ 顯示結果 ============

    if st.session_state.current_results:
        st.markdown("---")
        st.markdown("## 📊 排名結果")

        results = st.session_state.current_results
        rankings = results["rankings"]
        all_sites = my_sites + competitors

        # 獲取上次記錄
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

        # 詳細表格
        st.markdown("### 📋 詳細排名")

        display_data = []
        for rank_data in rankings:
            row = {"關鍵字": rank_data.get("keyword")}

            for site in all_sites:
                rank = rank_data.get(site)
                kw = rank_data.get("keyword")

                change = ""
                if kw in previous_rankings:
                    prev_rank = previous_rankings[kw].get(site)
                    if prev_rank is not None and rank is not None:
                        diff = prev_rank - rank
                        if diff > 0:
                            change = f" ↑{diff}"
                        elif diff < 0:
                            change = f" ↓{abs(diff)}"
                        else:
                            change = " ─"

                row[site] = f"{rank}{change}" if rank is not None else "N/A"

            display_data.append(row)

        df_display = pd.DataFrame(display_data)


        def highlight_ranking(val):
            if "N/A" in str(val):
                return "background-color: #FEE2E2; color: #DC2626;"
            try:
                rank = int(str(val).split()[0])
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

        st.markdown("""
        **圖例：** 🟢 前 3 名 | 🟡 首頁 (4-10) | ⚪ 第二頁 (11-20) | 🔴 未上榜 | ↑ 上升 | ↓ 下降
        """)

        # 下載
        st.markdown("---")


        def create_excel(rankings, serp_data, my_sites, competitors):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_rankings = pd.DataFrame(rankings)
                df_rankings.to_excel(writer, sheet_name="排名總覽", index=False)

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
            excel_file = create_excel(rankings, results.get("serp_data", {}), my_sites, competitors)
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
        st.info("📊 需要至少 2 次記錄才能顯示趨勢圖")
    else:
        all_keywords = set()
        all_tracked_sites = set()
        for record in history_records:
            for item in record.get("rankings", []):
                all_keywords.add(item.get("keyword"))
            all_tracked_sites.update(record.get("my_sites", []))
            all_tracked_sites.update(record.get("competitors", []))

        col1, col2 = st.columns(2)
        with col1:
            selected_keyword = st.selectbox("選擇關鍵字", sorted(list(all_keywords)))
        with col2:
            selected_site = st.selectbox("選擇網站", sorted(list(all_tracked_sites)))

        trend_data = []
        for record in history_records:
            date = record.get("date", "未知")
            for item in record.get("rankings", []):
                if item.get("keyword") == selected_keyword:
                    rank = item.get(selected_site)
                    trend_data.append({"日期": date, "排名": rank if rank else None})
                    break

        if trend_data:
            df_trend = pd.DataFrame(trend_data).dropna()

            if not df_trend.empty:
                st.markdown(f"**「{selected_keyword}」在 {selected_site} 的排名變化**")
                st.line_chart(df_trend.set_index("日期")["排名"])
                st.dataframe(df_trend, use_container_width=True)

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
                        st.metric("總變化", f"{change:+.0f}")

# ============ Tab 3: 數據分析 ============

with tab3:
    st.markdown("### 📊 SEO 數據分析")

    history_records = st.session_state.history.get("records", [])

    if not history_records:
        st.info("📊 還沒有數據，請先執行排名查詢")
    else:
        latest_record = history_records[-1]
        rankings = latest_record.get("rankings", [])
        tracked_my_sites = latest_record.get("my_sites", [])
        tracked_competitors = latest_record.get("competitors", [])

        if rankings:
            st.markdown("#### 🏆 排名分佈（我的網站）")

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

            st.bar_chart(pd.DataFrame([rank_distribution]).T)

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

            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True)

# ============ Tab 4: 管理 ============

with tab4:
    st.markdown("### ⚙️ 數據管理")

    history_records = st.session_state.history.get("records", [])
    st.markdown(f"**總記錄數：** {len(history_records)}")

    if history_records:
        st.markdown("#### 📜 歷史記錄")

        for i, record in enumerate(reversed(history_records[-10:])):
            date = record.get("date", "未知")
            keyword_count = len(record.get("rankings", []))
            with st.expander(f"📅 {date} ({keyword_count} 個關鍵字)"):
                st.json(record.get("rankings", []))

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            json_data = json.dumps(st.session_state.history, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 匯出 JSON 備份",
                data=json_data,
                file_name=f"serp_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )

        with col2:
            all_records = []
            for record in history_records:
                date = record.get("date", "")
                for item in record.get("rankings", []):
                    all_records.append({"日期": date, **item})

            if all_records:
                output = BytesIO()
                pd.DataFrame(all_records).to_excel(output, index=False, engine="openpyxl")
                output.seek(0)
                st.download_button(
                    label="📥 匯出歷史 Excel",
                    data=output,
                    file_name=f"serp_history_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        st.markdown("---")
        st.markdown("#### 🗑️ 清除數據")

        if st.button("🗑️ 清除所有記錄", type="secondary"):
            st.session_state.history = {"records": [], "settings": {}}
            save_history(st.session_state.history)
            st.success("✅ 已清除")
            st.rerun()

    st.markdown("---")
    st.markdown("#### 📤 匯入數據")

    uploaded_file = st.file_uploader("上傳 JSON 備份", type=["json"])
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
    <p>🚀 SEO 排名追蹤工具 Pro123 <span class="speed-badge">⚡ 50x 高速版</span></p>
    <p style="font-size: 0.8rem;">Async + Multi-threading | Powered by Serper API</p>
</div>
""", unsafe_allow_html=True)

