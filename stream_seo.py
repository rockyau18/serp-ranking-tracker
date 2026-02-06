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
import random

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

    .debug-box {
        background: #1a1a2e;
        color: #00ff88;
        padding: 1rem;
        border-radius: 8px;
        font-family: monospace;
        font-size: 0.85rem;
        max-height: 300px;
        overflow-y: auto;
    }

    .stat-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .keyword-group-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .copy-box {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 0.75rem;
        font-family: monospace;
        font-size: 0.85rem;
        white-space: pre-wrap;
        max-height: 200px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ============ 數據儲存功能 ============

DATA_FILE = "serp_history.json"
KEYWORD_GROUPS_FILE = "keyword_groups.json"


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


def load_keyword_groups():
    """載入關鍵字組"""
    if os.path.exists(KEYWORD_GROUPS_FILE):
        try:
            with open(KEYWORD_GROUPS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_keyword_groups(groups):
    """儲存關鍵字組"""
    with open(KEYWORD_GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)


def add_record(history, record):
    record["timestamp"] = datetime.now().isoformat()
    record["date"] = datetime.now().strftime("%Y-%m-%d")
    record["time"] = datetime.now().strftime("%H:%M:%S")
    record["id"] = f"{record['date']}_{record['time'].replace(':', '')}"
    history["records"].append(record)
    save_history(history)
    return history


def export_single_record(record):
    """匯出單一記錄為 Excel"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_rankings = pd.DataFrame(record.get("rankings", []))
        df_rankings.to_excel(writer, sheet_name="排名", index=False)

        info_data = {
            "項目": ["日期", "時間", "地區", "我的網站", "競爭對手"],
            "內容": [
                record.get("date", ""),
                record.get("time", ""),
                record.get("region", ""),
                ", ".join(record.get("my_sites", [])),
                ", ".join(record.get("competitors", []))
            ]
        }
        pd.DataFrame(info_data).to_excel(writer, sheet_name="查詢資訊", index=False)

    output.seek(0)
    return output


def normalize_domain(domain):
    """標準化網域名稱，移除 http/https 和尾部斜線"""
    domain = domain.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.rstrip("/")
    # 移除 www. 前綴
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def get_unique_sites(sites_list):
    """獲取唯一的網站列表（標準化後）"""
    seen = {}
    unique = []
    for site in sites_list:
        normalized = normalize_domain(site)
        if normalized not in seen:
            seen[normalized] = site
            unique.append(site)
    return unique


def get_record_display_name(record):
    """獲取記錄的顯示名稱"""
    date = record.get("date", "未知")
    time_str = record.get("time", "")
    keyword_count = len(record.get("rankings", []))
    return f"{date} {time_str} ({keyword_count}個關鍵字)"


def get_all_sites_from_record(record):
    """從記錄中獲取所有網站（標準化後去重）"""
    all_sites = []
    seen = set()
    
    for site in record.get("my_sites", []):
        normalized = normalize_domain(site)
        if normalized not in seen:
            seen.add(normalized)
            all_sites.append(site)
    
    for site in record.get("competitors", []):
        normalized = normalize_domain(site)
        if normalized not in seen:
            seen.add(normalized)
            all_sites.append(site)
    
    return all_sites


def get_keyword_order_map(record):
    """獲取關鍵字的原始順序映射"""
    keywords = record.get("keywords", [])
    return {kw: idx for idx, kw in enumerate(keywords)}


def analyze_keyword_competition(rankings, site_a, site_b, keyword_order_map=None):
    """分析兩個網站之間的關鍵字競爭"""
    winning = []  # A 贏
    losing = []  # A 輸
    both_ranked = []  # 雙方都有排名
    only_a = []  # 只有 A 有排名
    only_b = []  # 只有 B 有排名
    neither = []  # 都沒排名

    site_a_normalized = normalize_domain(site_a)
    site_b_normalized = normalize_domain(site_b)

    for item in rankings:
        keyword = item.get("keyword")
        
        # 查找 site_a 的排名
        rank_a = None
        for key in item.keys():
            if key != "keyword" and normalize_domain(key) == site_a_normalized:
                rank_a = item.get(key)
                break
        
        # 查找 site_b 的排名
        rank_b = None
        for key in item.keys():
            if key != "keyword" and normalize_domain(key) == site_b_normalized:
                rank_b = item.get(key)
                break

        # 獲取原始順序（用於排序）
        order = keyword_order_map.get(keyword, 9999) if keyword_order_map else 0

        if rank_a is None and rank_b is None:
            neither.append({"keyword": keyword, "order": order})
        elif rank_a is None:
            only_b.append({"keyword": keyword, "rank_b": rank_b, "order": order})
        elif rank_b is None:
            only_a.append({"keyword": keyword, "rank_a": rank_a, "order": order})
        else:
            both_ranked.append({
                "keyword": keyword,
                "rank_a": rank_a,
                "rank_b": rank_b,
                "diff": rank_b - rank_a,
                "order": order
            })
            if rank_a < rank_b:
                winning.append({"keyword": keyword, "rank_a": rank_a, "rank_b": rank_b, "order": order})
            elif rank_a > rank_b:
                losing.append({"keyword": keyword, "rank_a": rank_a, "rank_b": rank_b, "order": order})

    # 按原始輸入順序排序
    winning.sort(key=lambda x: x["order"])
    losing.sort(key=lambda x: x["order"])
    only_a.sort(key=lambda x: x["order"])
    only_b.sort(key=lambda x: x["order"])
    neither.sort(key=lambda x: x["order"])
    both_ranked.sort(key=lambda x: x["order"])

    return {
        "winning": winning,
        "losing": losing,
        "both_ranked": both_ranked,
        "only_a": only_a,
        "only_b": only_b,
        "neither": neither
    }


def analyze_site_keywords_detail(rankings, site, warning_threshold=20, keyword_order_map=None):
    """分析單一網站的關鍵字詳情"""
    site_normalized = normalize_domain(site)
    
    details = {
        "top3": [],
        "top10": [],
        "top20": [],
        "top30": [],
        "warning": [],
        "na": []
    }

    for item in rankings:
        keyword = item.get("keyword")
        order = keyword_order_map.get(keyword, 9999) if keyword_order_map else 0
        
        # 查找該網站的排名
        rank = None
        for key in item.keys():
            if key != "keyword" and normalize_domain(key) == site_normalized:
                rank = item.get(key)
                break

        if rank is None:
            details["na"].append({"keyword": keyword, "order": order})
        else:
            if rank <= 3:
                details["top3"].append({"keyword": keyword, "rank": rank, "order": order})
            elif rank <= 10:
                details["top10"].append({"keyword": keyword, "rank": rank, "order": order})
            elif rank <= 20:
                details["top20"].append({"keyword": keyword, "rank": rank, "order": order})
            elif rank <= 30:
                details["top30"].append({"keyword": keyword, "rank": rank, "order": order})

            if rank > warning_threshold:
                details["warning"].append({"keyword": keyword, "rank": rank, "order": order})

    # 按原始輸入順序排序
    for key in details:
        details[key].sort(key=lambda x: x["order"])

    return details


# ============ 穩定版異步搜尋引擎 ============

class StableSerpSearcher:
    """穩定版 SERP 搜尋器"""

    def __init__(self, api_key, region="hk", lang="zh-tw", max_concurrent=10,
                 delay_between_requests=0.1, max_retries=3, autocorrect=False):
        self.api_key = api_key
        self.region = region
        self.lang = lang
        self.max_concurrent = max_concurrent
        self.delay = delay_between_requests
        self.max_retries = max_retries
        self.autocorrect = autocorrect
        self.debug_logs = []
        self.success_count = 0
        self.fail_count = 0

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.debug_logs.append(log_entry)

    async def _fetch_with_retry(self, session, keyword, page, semaphore):
        async with semaphore:
            await asyncio.sleep(random.uniform(0.05, self.delay))

            url = "https://google.serper.dev/search"
            payload = {
                "q": keyword,
                "gl": self.region,
                "hl": self.lang,
                "num": 10,
                "page": page,
                "autocorrect": self.autocorrect
            }
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            for attempt in range(self.max_retries):
                try:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            results = data.get("organic", [])

                            for result in results:
                                original_position = result.get("position", 0)
                                result["actual_rank"] = (page - 1) * 10 + original_position
                                result["page"] = page

                            self.success_count += 1
                            self.log(f"✅ {keyword} (頁{page}): 取得 {len(results)} 個結果")

                            return {
                                "keyword": keyword,
                                "page": page,
                                "results": results,
                                "success": True
                            }

                        elif response.status == 429:
                            wait_time = (attempt + 1) * 2
                            self.log(f"⚠️ {keyword} (頁{page}): 限流，等待 {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue

                        else:
                            self.log(f"❌ {keyword} (頁{page}): HTTP {response.status}")
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(1)
                                continue

                except asyncio.TimeoutError:
                    self.log(f"⏱️ {keyword} (頁{page}): 超時")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)
                        continue

                except Exception as e:
                    self.log(f"❌ {keyword} (頁{page}): {str(e)[:50]}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)
                        continue

            self.fail_count += 1
            return {"keyword": keyword, "page": page, "results": [], "success": False}

    async def search_all_async(self, keywords, max_pages, progress_callback=None):
        self.debug_logs = []
        self.success_count = 0
        self.fail_count = 0

        tasks_info = [(kw, page) for kw in keywords for page in range(1, max_pages + 1)]
        total_tasks = len(tasks_info)

        self.log(f"🚀 開始: {len(keywords)} 關鍵字 × {max_pages} 頁 = {total_tasks} 請求")
        self.log(f"📝 Autocorrect: {'開啟' if self.autocorrect else '關閉'}")

        semaphore = asyncio.Semaphore(self.max_concurrent)
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        all_results = {kw: [] for kw in keywords}
        completed = 0

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            coroutines = [
                self._fetch_with_retry(session, kw, page, semaphore)
                for kw, page in tasks_info
            ]

            for coro in asyncio.as_completed(coroutines):
                result = await coro
                completed += 1

                keyword = result["keyword"]
                if result["success"] and result["results"]:
                    all_results[keyword].extend(result["results"])

                if progress_callback:
                    progress_callback(completed, total_tasks, keyword)

        for keyword in all_results:
            all_results[keyword].sort(key=lambda x: x.get("actual_rank", 999))

        self.log(f"📊 完成: 成功={self.success_count}, 失敗={self.fail_count}")
        return all_results

    def search_all(self, keywords, max_pages, progress_callback=None):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.search_all_async(keywords, max_pages, progress_callback)
            )
        finally:
            loop.close()


class SequentialSerpSearcher:
    """順序搜尋器"""

    def __init__(self, api_key, region="hk", lang="zh-tw", delay=0.3, autocorrect=False):
        self.api_key = api_key
        self.region = region
        self.lang = lang
        self.delay = delay
        self.autocorrect = autocorrect
        self.debug_logs = []
        self.success_count = 0
        self.fail_count = 0

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=3)
        self.session.mount('https://', adapter)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.debug_logs.append(f"[{timestamp}] {message}")

    def _fetch_single(self, keyword, page):
        url = "https://google.serper.dev/search"
        payload = {
            "q": keyword,
            "gl": self.region,
            "hl": self.lang,
            "num": 10,
            "page": page,
            "autocorrect": self.autocorrect
        }
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                results = data.get("organic", [])

                for result in results:
                    result["actual_rank"] = (page - 1) * 10 + result.get("position", 0)
                    result["page"] = page

                self.success_count += 1
                self.log(f"✅ {keyword} (頁{page}): {len(results)} 結果")
                return results

            elif response.status_code == 429:
                self.log(f"⚠️ {keyword} (頁{page}): 限流")
                time.sleep(2)
                return self._fetch_single(keyword, page)
            else:
                self.log(f"❌ {keyword} (頁{page}): HTTP {response.status_code}")
                self.fail_count += 1

        except Exception as e:
            self.log(f"❌ {keyword} (頁{page}): {str(e)[:30]}")
            self.fail_count += 1

        return []

    def search_all(self, keywords, max_pages, progress_callback=None):
        self.debug_logs = []
        self.success_count = 0
        self.fail_count = 0

        total = len(keywords) * max_pages
        completed = 0
        all_results = {}

        for keyword in keywords:
            all_results[keyword] = []
            for page in range(1, max_pages + 1):
                results = self._fetch_single(keyword, page)
                all_results[keyword].extend(results)
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, keyword)
                time.sleep(self.delay)
            all_results[keyword].sort(key=lambda x: x.get("actual_rank", 999))

        return all_results


class BatchSerpSearcher:
    """批次搜尋器"""

    def __init__(self, api_key, region="hk", lang="zh-tw",
                 batch_size=5, delay_between_batches=1.0, max_workers=5, autocorrect=False):
        self.api_key = api_key
        self.region = region
        self.lang = lang
        self.batch_size = batch_size
        self.batch_delay = delay_between_batches
        self.max_workers = max_workers
        self.autocorrect = autocorrect
        self.debug_logs = []
        self.success_count = 0
        self.fail_count = 0

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=max_workers, pool_maxsize=max_workers, max_retries=3)
        self.session.mount('https://', adapter)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.debug_logs.append(f"[{timestamp}] {message}")

    def _fetch_single(self, keyword, page):
        url = "https://google.serper.dev/search"
        payload = {
            "q": keyword,
            "gl": self.region,
            "hl": self.lang,
            "num": 10,
            "page": page,
            "autocorrect": self.autocorrect
        }
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        for attempt in range(3):
            try:
                response = self.session.post(url, json=payload, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("organic", [])
                    for result in results:
                        result["actual_rank"] = (page - 1) * 10 + result.get("position", 0)
                        result["page"] = page
                    self.success_count += 1
                    return {"keyword": keyword, "page": page, "results": results, "success": True}
                elif response.status_code == 429:
                    time.sleep((attempt + 1) * 2)
                    continue
            except Exception:
                if attempt < 2:
                    time.sleep(1)
                    continue

        self.fail_count += 1
        return {"keyword": keyword, "page": page, "results": [], "success": False}

    def search_all(self, keywords, max_pages, progress_callback=None):
        self.debug_logs = []
        self.success_count = 0
        self.fail_count = 0

        all_tasks = [(kw, page) for kw in keywords for page in range(1, max_pages + 1)]
        total_tasks = len(all_tasks)
        batches = [all_tasks[i:i + self.batch_size] for i in range(0, len(all_tasks), self.batch_size)]

        all_results = {kw: [] for kw in keywords}
        completed = 0

        for batch_idx, batch in enumerate(batches):
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self._fetch_single, kw, page): (kw, page) for kw, page in batch}
                for future in as_completed(futures):
                    result = future.result()
                    completed += 1
                    if result["success"]:
                        all_results[result["keyword"]].extend(result["results"])
                    if progress_callback:
                        progress_callback(completed, total_tasks, result["keyword"])

            if batch_idx < len(batches) - 1:
                time.sleep(self.batch_delay)

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
            site_normalized = normalize_domain(site)
            for result in results:
                link = result.get("link", "")
                link_normalized = normalize_domain(link)
                if site_normalized in link_normalized:
                    rank = result.get("actual_rank")
                    break
            row[site] = rank

        rankings.append(row)

    return rankings


def analyze_site_rankings(rankings, site, warning_threshold=20):
    """分析單一網站的排名分佈"""
    analysis = {
        "top3": [],
        "top10": [],
        "top20": [],
        "top30": [],
        "warning": [],
        "na": []
    }

    for item in rankings:
        keyword = item.get("keyword")
        rank = item.get(site)

        if rank is None:
            analysis["na"].append(keyword)
        elif rank <= 3:
            analysis["top3"].append({"keyword": keyword, "rank": rank})
        elif rank <= 10:
            analysis["top10"].append({"keyword": keyword, "rank": rank})
        elif rank <= 20:
            analysis["top20"].append({"keyword": keyword, "rank": rank})
        elif rank <= 30:
            analysis["top30"].append({"keyword": keyword, "rank": rank})

        if rank is not None and rank > warning_threshold:
            analysis["warning"].append({"keyword": keyword, "rank": rank})

    return analysis


def create_styled_ranking_dataframe(rankings, my_sites, competitors, warning_threshold, previous_rankings=None):
    """創建帶樣式的排名 DataFrame"""
    all_sites = my_sites + competitors

    # 建立顯示數據
    display_data = []
    for rank_data in rankings:
        row = {"關鍵字": rank_data.get("keyword")}

        for site in all_sites:
            rank = rank_data.get(site)
            kw = rank_data.get("keyword")

            # 計算變化
            change = ""
            if previous_rankings and kw in previous_rankings:
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

    # 樣式函數
    def style_ranking_cell(val, col_name):
        is_my_site = col_name in my_sites

        if "N/A" in str(val):
            if is_my_site:
                return "background-color: #FEF2F2; color: #B91C1C;"
            else:
                return "background-color: #F9FAFB; color: #9CA3AF;"

        try:
            rank = int(str(val).split()[0])

            if is_my_site:
                if rank <= 3:
                    return "background-color: #DBEAFE; color: #1E40AF; font-weight: bold;"
                elif rank <= 10:
                    return "background-color: #E0F2FE; color: #0369A1;"
                elif rank <= 20:
                    return "background-color: #F0F9FF; color: #0C4A6E;"
                elif rank > warning_threshold:
                    return "background-color: #FEE2E2; color: #DC2626; font-weight: bold;"
                else:
                    return "background-color: #F8FAFC; color: #475569;"
            else:
                if rank <= 3:
                    return "background-color: #FEF3C7; color: #92400E; font-weight: bold;"
                elif rank <= 10:
                    return "background-color: #FFFBEB; color: #B45309;"
                elif rank <= 20:
                    return "background-color: #F9FAFB; color: #6B7280;"
                else:
                    return "background-color: #F3F4F6; color: #9CA3AF;"
        except:
            return ""

    def apply_styles(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for col in df.columns:
            if col != "關鍵字":
                styles[col] = df[col].apply(lambda x: style_ranking_cell(x, col))
        return styles

    styled_df = df_display.style.apply(lambda _: apply_styles(df_display), axis=None)

    return df_display, styled_df


# ============ 初始化 Session State ============

if "history" not in st.session_state:
    st.session_state.history = load_history()

if "keyword_groups" not in st.session_state:
    st.session_state.keyword_groups = load_keyword_groups()

if "current_results" not in st.session_state:
    st.session_state.current_results = None

if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

if "keywords_input" not in st.session_state:
    st.session_state.keywords_input = "到會\n到會推介\n派對到會"

if "current_tab" not in st.session_state:
    st.session_state.current_tab = 0

# ============ 標題 ============

st.markdown("""
<div class="main-header">
    <h1>🚀 SEO 排名追蹤工具 Pro</h1>
    <p>穩定高速版 · 智能分析 · 競爭對手追蹤</p>
</div>
""", unsafe_allow_html=True)

# ============ 側邊欄設定 ============

with st.sidebar:
    st.markdown("## ⚙️ 設定")

    api_key = st.text_input("🔑 Serper API Key", type="password")

    if api_key:
        st.success("✅ API Key 已設定")
    else:
        st.warning("⚠️ 請輸入 API Key")

    st.markdown("---")

    st.markdown("### 🔍 搜尋設定")

    col1, col2 = st.columns(2)
    with col1:
        search_region = st.selectbox(
            "地區",
            options=["hk", "tw", "sg", "my", "us", "uk"],
            format_func=lambda x: {"hk": "🇭🇰 香港", "tw": "🇹🇼 台灣", "sg": "🇸🇬 新加坡",
                                   "my": "🇲🇾 馬來西亞", "us": "🇺🇸 美國", "uk": "🇬🇧 英國"}[x]
        )

    with col2:
        search_lang = st.selectbox(
            "語言",
            options=["zh-tw", "zh-cn", "en"],
            format_func=lambda x: {"zh-tw": "繁體中文", "zh-cn": "简体中文", "en": "English"}[x]
        )

    max_pages = st.slider("📄 爬取頁數", 1, 10, 5)

    # 新增 Autocorrect 開關
    autocorrect_enabled = st.toggle(
        "🔤 自動校正 (Autocorrect)",
        value=False,
        help="關閉時會搜尋原始關鍵字，開啟時 Google 會自動校正拼寫錯誤"
    )

    if not autocorrect_enabled:
        st.caption("📝 已關閉自動校正，將搜尋原始關鍵字")
    else:
        st.caption("📝 已開啟自動校正，Google 可能修改搜尋詞")

    st.markdown("---")

    st.markdown("### ⚡ 速度模式")
    speed_mode = st.radio(
        "選擇模式",
        options=["stable", "balanced", "fast"],
        format_func=lambda x: {
            "stable": "🐢 穩定模式",
            "balanced": "⚖️ 平衡模式 (推薦)",
            "fast": "🚀 高速模式"
        }[x],
        index=1
    )

    if speed_mode == "stable":
        max_concurrent = 1
        delay = 0.5
    elif speed_mode == "balanced":
        max_concurrent = 5
        delay = 0.3
    else:
        max_concurrent = st.slider("最大並發數", 5, 30, 15)
        delay = 0.1

    st.markdown("---")

    # 預設網站
    st.markdown("### 🏠 我的網站")
    default_my_sites = """daynightcatering.com
cateringbear.com
ceocatering.com
cateringmoment.com"""

    my_sites_input = st.text_area(
        "每行一個網域",
        value=default_my_sites,
        height=100,
        key="my_sites"
    )
    my_sites = [s.strip() for s in my_sites_input.split("\n") if s.strip()]

    st.markdown("### 🎯 競爭對手")
    competitors_input = st.text_area(
        "每行一個網域",
        value="cateringmama.com\nkamadelivery.com",
        height=80,
        key="competitors"
    )
    competitors = [s.strip() for s in competitors_input.split("\n") if s.strip()]

    st.markdown("---")

    st.markdown("### 🎨 顯示設定")
    warning_threshold = st.number_input(
        "⚠️ 警告閾值（排名超過此數字標紅）",
        min_value=10,
        max_value=100,
        value=20,
        step=5,
        help="排名超過這個數字的會用紅色標示"
    )

    st.markdown("---")
    debug_mode = st.checkbox("🐛 顯示調試信息", value=False)

# ============ 固定導航按鈕 ============

st.markdown("---")

# 使用 columns 創建固定導航 - 調整順序：數據分析在歷史記錄前面
nav_cols = st.columns(5)

tab_names = ["🔍 排名查詢", "🏷️ 關鍵字管理", "📊 數據分析", "📈 歷史記錄", "⚙️ 管理"]

for i, (col, name) in enumerate(zip(nav_cols, tab_names)):
    with col:
        if st.button(name, key=f"nav_{i}", use_container_width=True,
                     type="primary" if st.session_state.current_tab == i else "secondary"):
            st.session_state.current_tab = i
            st.rerun()

st.markdown("---")

# ============ Tab 內容 ============

# ============ Tab 0: 排名查詢 ============

if st.session_state.current_tab == 0:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("### 📝 輸入關鍵字")
        keywords_input = st.text_area(
            "每行一個關鍵字",
            value=st.session_state.keywords_input,
            height=200,
            key="keywords_text_area"
        )
        # 同步到 session state
        st.session_state.keywords_input = keywords_input
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

    with col_right:
        st.markdown("### 📂 關鍵字組（點擊複製）")

        keyword_groups = st.session_state.keyword_groups

        if keyword_groups:
            selected_group = st.selectbox(
                "選擇關鍵字組查看",
                options=["選擇..."] + list(keyword_groups.keys()),
                key="view_group_select"
            )

            if selected_group != "選擇...":
                group_data = keyword_groups[selected_group]
                group_keywords = group_data.get("keywords", [])
                group_desc = group_data.get("description", "")

                st.markdown(f"**{selected_group}** ({len(group_keywords)}個關鍵字)")
                if group_desc:
                    st.caption(f"📝 {group_desc}")

                # 顯示關鍵字內容，可以複製
                keywords_text = "\n".join(group_keywords)
                st.code(keywords_text, language=None)

                st.caption("👆 點擊右上角複製按鈕，然後貼到左邊輸入框")
        else:
            st.info("💡 還沒有關鍵字組，請到「關鍵字管理」建立")

        st.markdown("---")
        st.markdown("### 📋 查詢資訊")
        st.markdown(f"**關鍵字數量：** {len(keywords)}")
        st.markdown(f"**API 請求數：** {len(keywords) * max_pages}")
        st.markdown(f"**警告閾值：** 排名 > {warning_threshold}")
        st.markdown(f"**自動校正：** {'開啟' if autocorrect_enabled else '關閉'}")

    st.markdown("---")

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

        progress_container = st.container()
        with progress_container:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                progress_bar = st.progress(0)
                status_text = st.empty()
            with col2:
                time_display = st.empty()
            with col3:
                stats_display = st.empty()

        start_time = time.time()


        def update_progress(completed, total, current_keyword):
            progress = completed / total
            progress_bar.progress(progress)
            elapsed = time.time() - start_time
            status_text.text(f"處理: {current_keyword}")
            time_display.markdown(f"**⏱️ {elapsed:.1f}s**")
            stats_display.markdown(f"**{completed}/{total}**")


        if speed_mode == "stable":
            searcher = SequentialSerpSearcher(api_key, search_region, search_lang, delay, autocorrect_enabled)
        elif speed_mode == "balanced":
            searcher = BatchSerpSearcher(api_key, search_region, search_lang, max_concurrent, 0.5, max_concurrent,
                                         autocorrect_enabled)
        else:
            searcher = StableSerpSearcher(api_key, search_region, search_lang, max_concurrent, delay, 3,
                                          autocorrect_enabled)

        serp_results = searcher.search_all(keywords, max_pages, update_progress)
        elapsed_time = time.time() - start_time

        st.session_state.debug_logs = searcher.debug_logs

        if debug_mode and searcher.debug_logs:
            with st.expander("🐛 調試日誌", expanded=True):
                log_text = "\n".join(searcher.debug_logs[-50:])
                st.markdown(f'<div class="debug-box">{log_text}</div>', unsafe_allow_html=True)

        all_rankings = find_rankings(serp_results, all_sites)
        progress_bar.progress(1.0)

        success_rate = searcher.success_count / (searcher.success_count + searcher.fail_count) * 100 if (
                                                                                                                searcher.success_count + searcher.fail_count) > 0 else 0

        if success_rate >= 90:
            st.success(f"✅ 完成！耗時 {elapsed_time:.1f}s，成功率 {success_rate:.0f}%")
        elif success_rate >= 70:
            st.warning(f"⚠️ 完成，部分失敗。耗時 {elapsed_time:.1f}s，成功率 {success_rate:.0f}%")
        else:
            st.error(f"❌ 大量失敗。成功率 {success_rate:.0f}%，建議切換到穩定模式")

        st.session_state.current_results = {
            "rankings": all_rankings,
            "serp_data": serp_results,
            "timestamp": datetime.now().isoformat(),
            "elapsed_time": elapsed_time,
            "success_rate": success_rate,
            "my_sites": my_sites,
            "competitors": competitors
        }

        record = {
            "rankings": all_rankings,
            "my_sites": my_sites,
            "competitors": competitors,
            "region": search_region,
            "keywords": keywords,
            "autocorrect": autocorrect_enabled
        }
        st.session_state.history = add_record(st.session_state.history, record)

    # ============ 顯示結果 ============

    if st.session_state.current_results:
        st.markdown("---")

        results = st.session_state.current_results
        rankings = results["rankings"]
        result_my_sites = results.get("my_sites", my_sites)
        result_competitors = results.get("competitors", competitors)

        # 獲取上次記錄用於比較
        history_records = st.session_state.history.get("records", [])
        previous_rankings = {}
        if len(history_records) >= 2:
            prev_record = history_records[-2]
            for item in prev_record.get("rankings", []):
                previous_rankings[item.get("keyword")] = item

        # ============ 詳細排名表格（移到最上方） ============

        st.markdown("## 📋 詳細排名")

        st.markdown("""
        **圖例：** 🔵 我的網站（藍色系）| 🟠 競爭對手（橙色系）| ⚠️ 紅色 = 排名 > {} | N/A = 未上榜
        """.format(warning_threshold))

        df_display, styled_df = create_styled_ranking_dataframe(
            rankings, result_my_sites, result_competitors, warning_threshold, previous_rankings
        )

        st.dataframe(styled_df, use_container_width=True, height=500)

        # 下載按鈕
        def create_excel(rankings, serp_data, my_sites_list, competitors_list):
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
                if serp_records:
                    pd.DataFrame(serp_records).to_excel(writer, sheet_name="完整SERP", index=False)

            output.seek(0)
            return output


        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            excel_file = create_excel(rankings, results.get("serp_data", {}), result_my_sites, result_competitors)
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

        # ============ 排名總覽（移到表格下方） ============

        st.markdown("---")
        st.markdown("## 📊 排名總覽")

        # 我的網站
        if result_my_sites:
            st.markdown("### 🏠 我的網站")

            for site in result_my_sites:
                analysis = analyze_site_rankings(rankings, site, warning_threshold)

                with st.expander(f"📊 **{site}**", expanded=True):
                    cols = st.columns(6)

                    categories = [
                        ("🏆 前3名", "top3", "#10B981"),
                        ("📄 首頁(4-10)", "top10", "#3B82F6"),
                        ("📑 第2頁(11-20)", "top20", "#F59E0B"),
                        ("📋 第3頁(21-30)", "top30", "#8B5CF6"),
                        (f"⚠️ >{warning_threshold}名", "warning", "#EF4444"),
                        ("❌ 未上榜", "na", "#6B7280")
                    ]

                    for i, (label, key, color) in enumerate(categories):
                        with cols[i]:
                            count = len(analysis[key])
                            st.markdown(f"""
                            <div style="text-align: center; padding: 0.5rem; background: white; border-radius: 8px; border-left: 3px solid {color};">
                                <div style="font-size: 1.5rem; font-weight: bold; color: {color};">{count}</div>
                                <div style="font-size: 0.75rem; color: #666;">{label}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown("---")

                    tab_top3, tab_top10, tab_top20, tab_top30, tab_warning, tab_na = st.tabs([
                        f"🏆 前3名 ({len(analysis['top3'])})",
                        f"📄 首頁 ({len(analysis['top10'])})",
                        f"📑 第2頁 ({len(analysis['top20'])})",
                        f"📋 第3頁 ({len(analysis['top30'])})",
                        f"⚠️ 警告 ({len(analysis['warning'])})",
                        f"❌ 未上榜 ({len(analysis['na'])})"
                    ])

                    with tab_top3:
                        if analysis["top3"]:
                            for item in sorted(analysis["top3"], key=lambda x: x["rank"]):
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在前3名")

                    with tab_top10:
                        if analysis["top10"]:
                            for item in sorted(analysis["top10"], key=lambda x: x["rank"]):
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在4-10名")

                    with tab_top20:
                        if analysis["top20"]:
                            for item in sorted(analysis["top20"], key=lambda x: x["rank"]):
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在11-20名")

                    with tab_top30:
                        if analysis["top30"]:
                            for item in sorted(analysis["top30"], key=lambda x: x["rank"]):
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在21-30名")

                    with tab_warning:
                        if analysis["warning"]:
                            st.warning(f"以下 {len(analysis['warning'])} 個關鍵字排名超過 {warning_threshold}：")
                            for item in sorted(analysis["warning"], key=lambda x: x["rank"]):
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.success(f"所有關鍵字都在 {warning_threshold} 名內！")

                    with tab_na:
                        if analysis["na"]:
                            st.error(f"以下 {len(analysis['na'])} 個關鍵字未上榜：")
                            for kw in analysis["na"]:
                                st.markdown(f"• {kw}")
                        else:
                            st.success("所有關鍵字都有排名！")

        # 競爭對手
        if result_competitors:
            st.markdown("---")
            st.markdown("### 🎯 競爭對手")

            for site in result_competitors:
                analysis = analyze_site_rankings(rankings, site, warning_threshold)

                with st.expander(f"📊 **{site}**", expanded=False):
                    cols = st.columns(6)

                    categories = [
                        ("🏆 前3名", "top3", "#F59E0B"),
                        ("📄 首頁(4-10)", "top10", "#D97706"),
                        ("📑 第2頁(11-20)", "top20", "#92400E"),
                        ("📋 第3頁(21-30)", "top30", "#78350F"),
                        (f">{warning_threshold}名", "warning", "#9CA3AF"),
                        ("❌ 未上榜", "na", "#D1D5DB")
                    ]

                    for i, (label, key, color) in enumerate(categories):
                        with cols[i]:
                            count = len(analysis[key])
                            st.markdown(f"""
                            <div style="text-align: center; padding: 0.5rem; background: white; border-radius: 8px; border-left: 3px solid {color};">
                                <div style="font-size: 1.5rem; font-weight: bold; color: {color};">{count}</div>
                                <div style="font-size: 0.75rem; color: #666;">{label}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    if analysis["top3"] or analysis["top10"]:
                        st.markdown("**優勢關鍵字：**")
                        for item in sorted(analysis["top3"] + analysis["top10"], key=lambda x: x["rank"]):
                            st.markdown(f"**#{item['rank']}** - {item['keyword']}")

# ============ Tab 1: 關鍵字管理 ============

elif st.session_state.current_tab == 1:
    st.markdown("### 🏷️ 關鍵字組管理")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### ➕ 新增關鍵字組")

        new_group_name = st.text_input("組名", placeholder="例如：到會相關", key="new_group_name")
        new_group_keywords = st.text_area(
            "關鍵字（每行一個）",
            height=200,
            placeholder="到會\n到會推介\n派對到會\n...",
            key="new_group_keywords"
        )
        new_group_desc = st.text_input("描述（選填）", placeholder="例如：到會服務相關關鍵字", key="new_group_desc")

        if st.button("💾 儲存關鍵字組", type="primary", use_container_width=True):
            if not new_group_name:
                st.error("❌ 請輸入組名")
            elif not new_group_keywords.strip():
                st.error("❌ 請輸入至少一個關鍵字")
            else:
                keywords_list = [k.strip() for k in new_group_keywords.split("\n") if k.strip()]
                st.session_state.keyword_groups[new_group_name] = {
                    "keywords": keywords_list,
                    "description": new_group_desc,
                    "created": datetime.now().isoformat(),
                    "updated": datetime.now().isoformat()
                }
                save_keyword_groups(st.session_state.keyword_groups)
                st.success(f"✅ 已儲存「{new_group_name}」（{len(keywords_list)} 個關鍵字）")
                st.rerun()

    with col_right:
        st.markdown("#### 📋 現有關鍵字組")

        keyword_groups = st.session_state.keyword_groups

        if not keyword_groups:
            st.info("💡 還沒有關鍵字組，請在左側新增")
        else:
            for group_name, group_data in keyword_groups.items():
                group_keywords = group_data.get("keywords", [])
                group_desc = group_data.get("description", "")

                with st.expander(f"📁 {group_name} ({len(group_keywords)}個)", expanded=False):
                    st.markdown(f"**描述：** {group_desc if group_desc else '無'}")

                    # 顯示關鍵字內容，可以複製
                    st.markdown("**關鍵字：**（點擊右上角複製）")
                    keywords_text = "\n".join(group_keywords)
                    st.code(keywords_text, language=None)

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button("✏️ 編輯", key=f"edit_{group_name}", use_container_width=True):
                            st.session_state[f"editing_{group_name}"] = True
                            st.rerun()

                    with col2:
                        if st.button("🗑️ 刪除", key=f"delete_{group_name}", use_container_width=True):
                            del st.session_state.keyword_groups[group_name]
                            save_keyword_groups(st.session_state.keyword_groups)
                            st.success(f"✅ 已刪除「{group_name}」")
                            st.rerun()

                    # 編輯模式
                    if st.session_state.get(f"editing_{group_name}", False):
                        st.markdown("---")
                        st.markdown("**✏️ 編輯模式**")

                        edit_keywords = st.text_area(
                            "修改關鍵字",
                            value="\n".join(group_keywords),
                            height=150,
                            key=f"edit_kw_{group_name}"
                        )
                        edit_desc = st.text_input(
                            "修改描述",
                            value=group_desc,
                            key=f"edit_desc_{group_name}"
                        )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 儲存", key=f"save_{group_name}", type="primary", use_container_width=True):
                                new_keywords = [k.strip() for k in edit_keywords.split("\n") if k.strip()]
                                st.session_state.keyword_groups[group_name]["keywords"] = new_keywords
                                st.session_state.keyword_groups[group_name]["description"] = edit_desc
                                st.session_state.keyword_groups[group_name]["updated"] = datetime.now().isoformat()
                                save_keyword_groups(st.session_state.keyword_groups)
                                st.session_state[f"editing_{group_name}"] = False
                                st.success("✅ 已更新")
                                st.rerun()

                        with col_cancel:
                            if st.button("❌ 取消", key=f"cancel_{group_name}", use_container_width=True):
                                st.session_state[f"editing_{group_name}"] = False
                                st.rerun()

    st.markdown("---")

    # 匯入/匯出功能
    st.markdown("#### 📤 匯入/匯出")

    col1, col2 = st.columns(2)

    with col1:
        if keyword_groups:
            json_data = json.dumps(keyword_groups, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 匯出所有關鍵字組",
                data=json_data,
                file_name=f"keyword_groups_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )

    with col2:
        uploaded_file = st.file_uploader("上傳關鍵字組 JSON", type=["json"], key="upload_kw_groups")
        if uploaded_file:
            try:
                imported_groups = json.load(uploaded_file)
                if st.button("確認匯入", use_container_width=True):
                    st.session_state.keyword_groups.update(imported_groups)
                    save_keyword_groups(st.session_state.keyword_groups)
                    st.success(f"✅ 已匯入 {len(imported_groups)} 個關鍵字組")
                    st.rerun()
            except Exception as e:
                st.error(f"匯入失敗：{e}")

# ============ Tab 2: 數據分析（移到歷史記錄前面）============

elif st.session_state.current_tab == 2:
    st.markdown("### 📊 SEO 數據分析")

    history_records = st.session_state.history.get("records", [])

    if not history_records:
        st.info("📊 還沒有數據，請先執行排名查詢")
    else:
        # 分析頁面的警告閾值
        analysis_warning_threshold = st.number_input(
            "⚠️ 分析警告閾值",
            min_value=10,
            max_value=100,
            value=20,
            step=5,
            key="analysis_warning_threshold"
        )

        st.markdown("---")

        # ============ 選擇歷史記錄 ============
        
        st.markdown("### 📅 選擇查詢記錄")
        
        record_options = []
        for i, record in enumerate(reversed(history_records)):
            record_idx = len(history_records) - 1 - i
            display_name = get_record_display_name(record)
            record_options.append((display_name, record_idx))
        
        selected_record_display = st.selectbox(
            "選擇要分析的記錄",
            options=[opt[0] for opt in record_options],
            key="analysis_record_select"
        )
        
        # 獲取選中的記錄
        selected_record_idx = None
        for display_name, idx in record_options:
            if display_name == selected_record_display:
                selected_record_idx = idx
                break
        
        if selected_record_idx is not None:
            selected_record = history_records[selected_record_idx]
            rankings = selected_record.get("rankings", [])
            tracked_my_sites = selected_record.get("my_sites", [])
            tracked_competitors = selected_record.get("competitors", [])
            all_sites_in_record = get_all_sites_from_record(selected_record)
            keyword_order_map = get_keyword_order_map(selected_record)

            st.info(f"📊 分析記錄: {selected_record.get('date', '')} {selected_record.get('time', '')} | {len(rankings)} 個關鍵字 | {len(all_sites_in_record)} 個網站")

            st.markdown("---")

            if rankings:
                # ============ 1. 關鍵字爭奪分析（第一位）============

                st.markdown("### 🥊 關鍵字爭奪分析")
                
                st.markdown("**可以比較任意兩個網站之間的關鍵字表現（包括自己的網站之間）**")

                col1, col2 = st.columns(2)
                with col1:
                    site_a = st.selectbox(
                        "選擇網站 A", 
                        all_sites_in_record, 
                        key="compete_site_a",
                        help="選擇第一個網站進行比較"
                    )
                with col2:
                    # 過濾掉已選的網站 A
                    site_b_options = [s for s in all_sites_in_record if normalize_domain(s) != normalize_domain(site_a)]
                    site_b = st.selectbox(
                        "選擇網站 B", 
                        site_b_options if site_b_options else all_sites_in_record, 
                        key="compete_site_b",
                        help="選擇第二個網站進行比較"
                    )

                if site_a and site_b and normalize_domain(site_a) != normalize_domain(site_b):
                    # 顯示比較類型
                    site_a_type = "🏠 我的網站" if site_a in tracked_my_sites else "🎯 競爭對手"
                    site_b_type = "🏠 我的網站" if site_b in tracked_my_sites else "🎯 競爭對手"
                    
                    st.markdown(f"""
                    **比較：** {site_a_type} `{site_a}` **vs** {site_b_type} `{site_b}`
                    """)
                    
                    # 分析競爭情況（傳入 keyword_order_map 以保持順序）
                    competition = analyze_keyword_competition(rankings, site_a, site_b, keyword_order_map)
                    
                    winning = competition["winning"]
                    losing = competition["losing"]
                    only_a = competition["only_a"]
                    only_b = competition["only_b"]
                    neither = competition["neither"]

                    # 顯示統計 - 修改標籤顯示對應的網站名稱
                    stat_cols = st.columns(5)
                    
                    # 截斷網站名稱以適應顯示
                    site_a_short = site_a[:15] + "..." if len(site_a) > 15 else site_a
                    site_b_short = site_b[:15] + "..." if len(site_b) > 15 else site_b
                    
                    with stat_cols[0]:
                        st.metric(f"🏆 {site_a_short} 贏", len(winning))
                    with stat_cols[1]:
                        st.metric(f"😢 {site_a_short} 輸", len(losing))
                    with stat_cols[2]:
                        st.metric(f"✅ 只有 {site_a_short}", len(only_a))
                    with stat_cols[3]:
                        st.metric(f"⚠️ 只有 {site_b_short}", len(only_b))
                    with stat_cols[4]:
                        st.metric("❌ 都沒排名", len(neither))

                    # Tab 標籤也顯示網站名稱
                    compete_tabs = st.tabs([
                        f"🏆 {site_a_short} 贏 ({len(winning)})",
                        f"😢 {site_a_short} 輸 ({len(losing)})",
                        f"✅ 只有 {site_a_short} ({len(only_a)})",
                        f"⚠️ 只有 {site_b_short} ({len(only_b)})",
                        f"❌ 都沒排名 ({len(neither)})"
                    ])

                    with compete_tabs[0]:
                        if winning:
                            st.success(f"🎉 以下 {len(winning)} 個關鍵字 **{site_a}** 排名領先！")
                            win_data = []
                            for item in winning:
                                win_data.append({
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"],
                                    f"{site_b} 排名": item["rank_b"],
                                    "優勢": item["rank_b"] - item["rank_a"]
                                })
                            win_df = pd.DataFrame(win_data)
                            st.dataframe(win_df, use_container_width=True, hide_index=True)
                        else:
                            st.info(f"**{site_a}** 沒有領先的關鍵字")

                    with compete_tabs[1]:
                        if losing:
                            st.error(f"⚠️ 以下 {len(losing)} 個關鍵字 **{site_a}** 需要加強！")
                            lose_data = []
                            for item in losing:
                                lose_data.append({
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"],
                                    f"{site_b} 排名": item["rank_b"],
                                    "落後": item["rank_a"] - item["rank_b"]
                                })
                            lose_df = pd.DataFrame(lose_data)
                            st.dataframe(lose_df, use_container_width=True, hide_index=True)
                        else:
                            st.success(f"**{site_a}** 沒有落後的關鍵字！")

                    with compete_tabs[2]:
                        if only_a:
                            st.success(f"✅ 以下 {len(only_a)} 個關鍵字只有 **{site_a}** 上榜！")
                            only_a_data = []
                            for item in only_a:
                                only_a_data.append({
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"]
                                })
                            only_a_df = pd.DataFrame(only_a_data)
                            st.dataframe(only_a_df, use_container_width=True, hide_index=True)
                        else:
                            st.info(f"**{site_a}** 沒有獨佔的關鍵字")

                    with compete_tabs[3]:
                        if only_b:
                            st.warning(f"⚠️ 以下 {len(only_b)} 個關鍵字只有 **{site_b}** 上榜！")
                            only_b_data = []
                            for item in only_b:
                                only_b_data.append({
                                    "關鍵字": item["keyword"],
                                    f"{site_b} 排名": item["rank_b"]
                                })
                            only_b_df = pd.DataFrame(only_b_data)
                            st.dataframe(only_b_df, use_container_width=True, hide_index=True)
                        else:
                            st.success(f"**{site_b}** 沒有獨佔的關鍵字！")

                    with compete_tabs[4]:
                        if neither:
                            st.info(f"以下 {len(neither)} 個關鍵字雙方都沒排名：")
                            neither_cols = st.columns(3)
                            for idx, item in enumerate(neither):
                                with neither_cols[idx % 3]:
                                    st.markdown(f"• {item['keyword']}")
                        else:
                            st.info("所有關鍵字至少有一方有排名")

                elif site_a and site_b:
                    st.warning("⚠️ 請選擇兩個不同的網站進行比較")

                st.markdown("---")

                # ============ 2. 查看各網站詳細關鍵字（第二位）============

                st.markdown("### 🔍 查看各網站詳細關鍵字")

                selected_site_detail = st.selectbox(
                    "選擇網站查看詳細",
                    all_sites_in_record,
                    key="detail_site_select"
                )

                if selected_site_detail:
                    details = analyze_site_keywords_detail(rankings, selected_site_detail, analysis_warning_threshold, keyword_order_map)
                    is_my_site = selected_site_detail in tracked_my_sites
                    site_type = "🏠 我的網站" if is_my_site else "🎯 競爭對手"

                    st.markdown(f"#### {site_type}: **{selected_site_detail}**")

                    # 統計數據
                    stat_cols = st.columns(6)
                    categories_info = [
                        ("🏆 前3名", len(details['top3']), "#10B981"),
                        ("📄 首頁4-10", len(details['top10']), "#3B82F6"),
                        ("📑 第2頁", len(details['top20']), "#F59E0B"),
                        ("📋 第3頁", len(details['top30']), "#8B5CF6"),
                        (f"⚠️ >{analysis_warning_threshold}名", len(details['warning']), "#EF4444"),
                        ("❌ 未上榜", len(details['na']), "#6B7280")
                    ]

                    for i, (label, count, color) in enumerate(categories_info):
                        with stat_cols[i]:
                            st.markdown(f"""
                            <div style="text-align: center; padding: 0.5rem; background: white; border-radius: 8px; border-left: 3px solid {color};">
                                <div style="font-size: 1.5rem; font-weight: bold; color: {color};">{count}</div>
                                <div style="font-size: 0.75rem; color: #666;">{label}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    detail_tabs = st.tabs([
                        f"🏆 前3名 ({len(details['top3'])})",
                        f"📄 首頁4-10 ({len(details['top10'])})",
                        f"📑 第2頁11-20 ({len(details['top20'])})",
                        f"📋 第3頁21-30 ({len(details['top30'])})",
                        f"⚠️ >{analysis_warning_threshold}名 ({len(details['warning'])})",
                        f"❌ 未上榜 ({len(details['na'])})"
                    ])

                    with detail_tabs[0]:
                        if details["top3"]:
                            for item in details["top3"]:
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在前3名")

                    with detail_tabs[1]:
                        if details["top10"]:
                            for item in details["top10"]:
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在首頁4-10名")

                    with detail_tabs[2]:
                        if details["top20"]:
                            for item in details["top20"]:
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在第2頁")

                    with detail_tabs[3]:
                        if details["top30"]:
                            for item in details["top30"]:
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.info("沒有關鍵字在第3頁")

                    with detail_tabs[4]:
                        if details["warning"]:
                            st.warning(f"⚠️ 以下 {len(details['warning'])} 個關鍵字排名超過 {analysis_warning_threshold}：")
                            for item in details["warning"]:
                                st.markdown(f"**#{item['rank']}** - {item['keyword']}")
                        else:
                            st.success(f"✅ 沒有關鍵字超過 {analysis_warning_threshold} 名！")

                    with detail_tabs[5]:
                        if details["na"]:
                            st.error(f"❌ 以下 {len(details['na'])} 個關鍵字未上榜：")
                            # 分列顯示
                            na_cols = st.columns(3)
                            for idx, item in enumerate(details["na"]):
                                with na_cols[idx % 3]:
                                    st.markdown(f"• {item['keyword']}")
                        else:
                            st.success("✅ 所有關鍵字都有排名！")

                st.markdown("---")

                # ============ 3. 關鍵字歷史變化（第三位）============

                st.markdown("### 📈 關鍵字排名歷史變化")

                if len(history_records) >= 2:
                    # 收集所有關鍵字和網站
                    all_keywords = set()
                    all_sites_history = set()
                    for record in history_records:
                        for item in record.get("rankings", []):
                            all_keywords.add(item.get("keyword"))
                        all_sites_history.update(record.get("my_sites", []))
                        all_sites_history.update(record.get("competitors", []))

                    # 標準化網站列表，合併相同網域
                    normalized_sites_map = {}  # normalized -> display name
                    for site in all_sites_history:
                        normalized = normalize_domain(site)
                        if normalized not in normalized_sites_map:
                            normalized_sites_map[normalized] = site

                    unique_sites_for_chart = list(normalized_sites_map.values())

                    col1, col2 = st.columns(2)
                    with col1:
                        # 多選關鍵字
                        selected_keywords = st.multiselect(
                            "選擇關鍵字（可多選）",
                            sorted(list(all_keywords)),
                            default=sorted(list(all_keywords))[:3] if len(all_keywords) >= 3 else sorted(
                                list(all_keywords)),
                            key="analysis_keywords"
                        )
                    with col2:
                        selected_site_for_chart = st.selectbox(
                            "選擇網站",
                            sorted(unique_sites_for_chart),
                            key="analysis_site"
                        )

                    if selected_keywords and selected_site_for_chart:
                        # 建立歷史數據
                        chart_data = []
                        selected_normalized = normalize_domain(selected_site_for_chart)

                        for record in history_records:
                            date = record.get("date", "")
                            time_str = record.get("time", "")
                            datetime_str = f"{date} {time_str}"

                            row = {"日期": datetime_str}
                            for item in record.get("rankings", []):
                                kw = item.get("keyword")
                                if kw in selected_keywords:
                                    # 查找匹配的網站（標準化比對）
                                    rank = None
                                    for site_key in item.keys():
                                        if site_key != "keyword" and normalize_domain(site_key) == selected_normalized:
                                            rank = item.get(site_key)
                                            break
                                    row[kw] = rank
                            chart_data.append(row)

                        df_chart = pd.DataFrame(chart_data)
                        df_chart = df_chart.set_index("日期")

                        # 顯示詳細數據表（用表格代替圖表）
                        st.markdown("#### 📊 排名變化數據")
                        st.dataframe(df_chart.reset_index(), use_container_width=True)

                        # 計算每個關鍵字的變化
                        st.markdown("#### 📈 排名變化統計")

                        change_data = []
                        for kw in selected_keywords:
                            if kw in df_chart.columns:
                                values = df_chart[kw].dropna()
                                if len(values) >= 1:
                                    first_rank = values.iloc[0] if len(values) >= 1 else None
                                    last_rank = values.iloc[-1] if len(values) >= 1 else None

                                    if len(values) >= 2:
                                        change = first_rank - last_rank  # 正數表示排名上升
                                        change_str = f"{'↑' if change > 0 else '↓' if change < 0 else '─'}{abs(int(change))}" if change != 0 else "─"
                                    else:
                                        change_str = "─"

                                    best_rank = values.min()
                                    worst_rank = values.max()
                                    avg_rank = values.mean()

                                    change_data.append({
                                        "關鍵字": kw,
                                        "首次排名": int(first_rank) if pd.notna(first_rank) else "N/A",
                                        "最新排名": int(last_rank) if pd.notna(last_rank) else "N/A",
                                        "變化": change_str,
                                        "最佳排名": int(best_rank) if pd.notna(best_rank) else "N/A",
                                        "最差排名": int(worst_rank) if pd.notna(worst_rank) else "N/A",
                                        "平均排名": f"{avg_rank:.1f}" if pd.notna(avg_rank) else "N/A"
                                    })

                        if change_data:
                            df_change = pd.DataFrame(change_data)
                            st.dataframe(df_change, use_container_width=True, hide_index=True)
                else:
                    st.info("需要至少2次查詢記錄才能顯示歷史變化")

                st.markdown("---")

                # ============ 4. 網站排名比較總覽（第四位）============

                st.markdown("### ⚔️ 網站排名比較總覽")

                comparison_data = []

                for site in all_sites_in_record:
                    details = analyze_site_keywords_detail(rankings, site, analysis_warning_threshold, keyword_order_map)
                    
                    # 計算平均排名
                    all_ranks = []
                    for cat in ["top3", "top10", "top20", "top30"]:
                        all_ranks.extend([item["rank"] for item in details[cat]])
                    
                    avg_rank = round(sum(all_ranks) / len(all_ranks), 1) if all_ranks else "N/A"
                    
                    comparison_data.append({
                        "網站": site,
                        "類型": "🏠 我的網站" if site in tracked_my_sites else "🎯 競爭對手",
                        "前3名": len(details["top3"]),
                        "首頁(4-10)": len(details["top10"]),
                        "第2頁(11-20)": len(details["top20"]),
                        "21-30名": len(details["top30"]),
                        f">{analysis_warning_threshold}名": len(details["warning"]),
                        "未上榜": len(details["na"]),
                        "平均排名": avg_rank
                    })

                df_comparison = pd.DataFrame(comparison_data)


                def highlight_comparison(row):
                    if "我的網站" in row["類型"]:
                        return ['background-color: #EFF6FF'] * len(row)
                    else:
                        return ['background-color: #FFFBEB'] * len(row)


                styled_comparison = df_comparison.style.apply(highlight_comparison, axis=1)
                st.dataframe(styled_comparison, use_container_width=True, hide_index=True)

# ============ Tab 3: 歷史記錄（移到數據分析後面）============

elif st.session_state.current_tab == 3:
    st.markdown("### 📜 歷史記錄")

    history_records = st.session_state.history.get("records", [])

    if not history_records:
        st.info("📊 還沒有歷史記錄，請先執行排名查詢")
    else:
        st.markdown(f"**共 {len(history_records)} 條記錄**")

        # 歷史記錄的警告閾值設定
        st.markdown("---")
        history_warning_threshold = st.number_input(
            "⚠️ 歷史記錄警告閾值",
            min_value=10,
            max_value=100,
            value=20,
            step=5,
            key="history_warning_threshold",
            help="用於歷史記錄中的排名顏色標示"
        )

        st.markdown("---")

        # 顯示每條記錄
        for i, record in enumerate(reversed(history_records)):
            record_idx = len(history_records) - 1 - i  # 實際索引
            record_date = record.get("date", "未知")
            record_time = record.get("time", "")
            record_id = record.get("id", f"record_{i}")
            keyword_count = len(record.get("rankings", []))
            my_sites_count = len(record.get("my_sites", []))
            competitor_count = len(record.get("competitors", []))
            autocorrect_status = "開" if record.get("autocorrect", False) else "關"

            col1, col2, col3 = st.columns([4, 1, 1])

            with col1:
                expander_title = f"📅 {record_date} {record_time} | {keyword_count}個關鍵字 | {my_sites_count}個網站 | {competitor_count}個對手 | 自動校正:{autocorrect_status}"

                with st.expander(expander_title, expanded=False):
                    # 基本資訊
                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.markdown("**🏠 查詢的網站：**")
                        st.write(", ".join(record.get("my_sites", [])))
                    with info_col2:
                        st.markdown("**🎯 競爭對手：**")
                        st.write(", ".join(record.get("competitors", [])))

                    st.markdown("**🔑 關鍵字：**")
                    st.write(", ".join(record.get("keywords", [])))

                    st.markdown("---")

                    # 使用相同的詳細排名格式顯示
                    st.markdown("### 📋 詳細排名")

                    record_my_sites = record.get("my_sites", [])
                    record_competitors = record.get("competitors", [])
                    record_rankings = record.get("rankings", [])

                    st.markdown("""
                    **圖例：** 🔵 我的網站（藍色系）| 🟠 競爭對手（橙色系）| ⚠️ 紅色 = 排名 > {} | N/A = 未上榜
                    """.format(history_warning_threshold))

                    # 獲取前一條記錄用於比較
                    prev_rankings_dict = {}
                    if record_idx > 0:
                        prev_record = history_records[record_idx - 1]
                        for item in prev_record.get("rankings", []):
                            prev_rankings_dict[item.get("keyword")] = item

                    # 創建帶樣式的表格
                    df_display, styled_df = create_styled_ranking_dataframe(
                        record_rankings,
                        record_my_sites,
                        record_competitors,
                        history_warning_threshold,
                        prev_rankings_dict
                    )

                    st.dataframe(styled_df, use_container_width=True, height=400)

                    # 網站排名總覽
                    st.markdown("---")
                    st.markdown("### 📊 排名分佈總覽")

                    all_record_sites = record_my_sites + record_competitors

                    summary_data = []
                    for site in all_record_sites:
                        analysis = analyze_site_rankings(record_rankings, site, history_warning_threshold)
                        summary_data.append({
                            "網站": site,
                            "類型": "🏠" if site in record_my_sites else "🎯",
                            "前3名": len(analysis["top3"]),
                            "首頁(4-10)": len(analysis["top10"]),
                            "第2頁(11-20)": len(analysis["top20"]),
                            "第3頁(21-30)": len(analysis["top30"]),
                            f">{history_warning_threshold}名": len(analysis["warning"]),
                            "未上榜": len(analysis["na"])
                        })

                    if summary_data:
                        df_summary = pd.DataFrame(summary_data)
                        st.dataframe(df_summary, use_container_width=True, hide_index=True)

            with col2:
                excel_data = export_single_record(record)
                st.download_button(
                    label="📥 Excel",
                    data=excel_data,
                    file_name=f"serp_{record_date}_{record_time.replace(':', '')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_excel_{record_id}_{i}"
                )

            with col3:
                json_data = json.dumps(record, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📥 JSON",
                    data=json_data,
                    file_name=f"serp_{record_date}_{record_time.replace(':', '')}.json",
                    mime="application/json",
                    key=f"dl_json_{record_id}_{i}"
                )

        st.markdown("---")

        # 趨勢分析
        st.markdown("### 📈 排名趨勢")

        if len(history_records) >= 2:
            all_keywords = set()
            all_tracked_sites = set()
            for record in history_records:
                for item in record.get("rankings", []):
                    all_keywords.add(item.get("keyword"))
                all_tracked_sites.update(record.get("my_sites", []))
                all_tracked_sites.update(record.get("competitors", []))

            # 標準化網站列表
            normalized_sites_map = {}  # normalized -> display name
            for site in all_tracked_sites:
                normalized = normalize_domain(site)
                if normalized not in normalized_sites_map:
                    normalized_sites_map[normalized] = site

            unique_sites = list(normalized_sites_map.values())

            col1, col2 = st.columns(2)
            with col1:
                selected_keyword = st.selectbox("選擇關鍵字", sorted(list(all_keywords)), key="trend_keyword")
            with col2:
                selected_site = st.selectbox("選擇網站", sorted(unique_sites), key="trend_site")

            trend_data = []
            selected_normalized = normalize_domain(selected_site)

            for record in history_records:
                date = record.get("date", "未知")
                time_str = record.get("time", "")
                for item in record.get("rankings", []):
                    if item.get("keyword") == selected_keyword:
                        # 查找匹配的網站（標準化比對）
                        rank = None
                        for site_key in item.keys():
                            if site_key != "keyword" and normalize_domain(site_key) == selected_normalized:
                                rank = item.get(site_key)
                                break
                        trend_data.append({
                            "日期時間": f"{date} {time_str}",
                            "排名": rank if rank else None
                        })
                        break

            if trend_data:
                df_trend = pd.DataFrame(trend_data).dropna()
                if not df_trend.empty:
                    st.line_chart(df_trend.set_index("日期時間")["排名"])

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("最佳排名", int(df_trend["排名"].min()))
                    with col2:
                        st.metric("平均排名", f"{df_trend['排名'].mean():.1f}")
                    with col3:
                        if len(df_trend) >= 2:
                            change = df_trend["排名"].iloc[0] - df_trend["排名"].iloc[-1]
                            st.metric("總變化", f"{change:+.0f}")
        else:
            st.info("需要至少2次記錄才能顯示趨勢")

# ============ Tab 4: 管理 ============

elif st.session_state.current_tab == 4:
    st.markdown("### ⚙️ 數據管理")

    history_records = st.session_state.history.get("records", [])
    st.markdown(f"**總記錄數：** {len(history_records)}")
    st.markdown(f"**關鍵字組數：** {len(st.session_state.keyword_groups)}")

    if st.session_state.debug_logs:
        st.markdown("#### 🐛 最近的調試日誌")
        with st.expander("查看日誌"):
            for log in st.session_state.debug_logs[-30:]:
                st.text(log)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📤 匯出所有數據")

        if history_records:
            json_data = json.dumps(st.session_state.history, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 匯出 JSON 備份",
                data=json_data,
                file_name=f"serp_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )

            all_records = []
            for record in history_records:
                date = record.get("date", "")
                time_str = record.get("time", "")
                for item in record.get("rankings", []):
                    all_records.append({"日期": date, "時間": time_str, **item})

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

    with col2:
        st.markdown("#### 📥 匯入數據")

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

    st.markdown("---")
    st.markdown("#### 🗑️ 清除數據")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 清除所有記錄", type="secondary"):
            st.session_state.history = {"records": [], "settings": {}}
            save_history(st.session_state.history)
            st.session_state.current_results = None
            st.success("✅ 已清除")
            st.rerun()

    with col2:
        if st.button("🗑️ 清除所有關鍵字組", type="secondary"):
            st.session_state.keyword_groups = {}
            save_keyword_groups({})
            st.success("✅ 已清除所有關鍵字組")
            st.rerun()

# ============ 頁尾 ============

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>🚀 SEO 排名追蹤工具 Pro v2.6</p>
    <p style="font-size: 0.8rem;">智能分析 | 競爭對手追蹤 | 關鍵字管理 | Powered by Serper API</p>
</div>
""", unsafe_allow_html=True)
