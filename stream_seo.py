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

    .project-header {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1rem 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
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
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 0.5rem;
        border-left: 4px solid #667eea;
    }

    .keyword-item {
        padding: 0.4rem 0;
        border-bottom: 1px solid #f0f0f0;
        font-size: 0.95rem;
    }

    .keyword-item:last-child {
        border-bottom: none;
    }

    .keyword-rank {
        display: inline-block;
        min-width: 45px;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
        margin-right: 0.5rem;
    }

    .rank-top3 {
        background: #DBEAFE;
        color: #1E40AF;
    }

    .rank-top10 {
        background: #E0F2FE;
        color: #0369A1;
    }

    .rank-top20 {
        background: #FEF3C7;
        color: #92400E;
    }

    .rank-top30 {
        background: #F3E8FF;
        color: #7C3AED;
    }

    .rank-warning {
        background: #FEE2E2;
        color: #DC2626;
    }

    .rank-na {
        background: #F3F4F6;
        color: #6B7280;
    }

    .site-analysis-card {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    /* 減少側邊欄元素間距 */
    .sidebar-section {
        margin-bottom: 0.5rem !important;
    }

    [data-testid="stSidebar"] .stSelectbox,
    [data-testid="stSidebar"] .stRadio,
    [data-testid="stSidebar"] .stSlider {
        margin-bottom: 0.3rem !important;
    }

    [data-testid="stSidebar"] .stMarkdown p {
        margin-bottom: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ============ 數據儲存功能 ============

DATA_DIR = "seo_data"
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")


def ensure_data_dir():
    """確保數據目錄存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def get_project_file(project_id):
    """獲取專案數據檔案路徑"""
    ensure_data_dir()
    return os.path.join(DATA_DIR, f"project_{project_id}.json")


def load_projects():
    """載入所有專案列表"""
    ensure_data_dir()
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"projects": [], "active_project": None}
    return {"projects": [], "active_project": None}


def save_projects(data):
    """儲存專案列表"""
    ensure_data_dir()
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project_data(project_id):
    """載入特定專案的數據"""
    file_path = get_project_file(project_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"records": [], "keyword_groups": {}, "settings": {}}
    return {"records": [], "keyword_groups": {}, "settings": {}}


def save_project_data(project_id, data):
    """儲存特定專案的數據"""
    file_path = get_project_file(project_id)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_project(name, industry, description="", my_sites=None, competitors=None, icon="📊"):
    """創建新專案"""
    projects_data = load_projects()

    project_id = f"proj_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

    new_project = {
        "id": project_id,
        "name": name,
        "industry": industry,
        "description": description,
        "icon": icon,
        "my_sites": my_sites or [],
        "competitors": competitors or [],
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "record_count": 0
    }

    projects_data["projects"].append(new_project)

    if len(projects_data["projects"]) == 1:
        projects_data["active_project"] = project_id

    save_projects(projects_data)
    save_project_data(project_id, {"records": [], "keyword_groups": {}, "settings": {}})

    return project_id


def delete_project(project_id):
    """刪除專案"""
    projects_data = load_projects()

    projects_data["projects"] = [p for p in projects_data["projects"] if p["id"] != project_id]

    if projects_data["active_project"] == project_id:
        if projects_data["projects"]:
            projects_data["active_project"] = projects_data["projects"][0]["id"]
        else:
            projects_data["active_project"] = None

    save_projects(projects_data)

    file_path = get_project_file(project_id)
    if os.path.exists(file_path):
        os.remove(file_path)


def update_project(project_id, updates):
    """更新專案資訊"""
    projects_data = load_projects()

    for project in projects_data["projects"]:
        if project["id"] == project_id:
            project.update(updates)
            project["updated"] = datetime.now().isoformat()
            break

    save_projects(projects_data)


def set_active_project(project_id):
    """設定活躍專案"""
    projects_data = load_projects()
    projects_data["active_project"] = project_id
    save_projects(projects_data)


def get_active_project():
    """獲取當前活躍專案"""
    projects_data = load_projects()
    active_id = projects_data.get("active_project")

    if active_id:
        for project in projects_data["projects"]:
            if project["id"] == active_id:
                return project

    return None


def add_record_to_project(project_id, record):
    """添加記錄到專案"""
    record["timestamp"] = datetime.now().isoformat()
    record["date"] = datetime.now().strftime("%Y-%m-%d")
    record["time"] = datetime.now().strftime("%H:%M:%S")
    record["id"] = f"{record['date']}_{record['time'].replace(':', '')}"

    project_data = load_project_data(project_id)
    project_data["records"].append(record)
    save_project_data(project_id, project_data)

    projects_data = load_projects()
    for project in projects_data["projects"]:
        if project["id"] == project_id:
            project["record_count"] = len(project_data["records"])
            project["updated"] = datetime.now().isoformat()
            break
    save_projects(projects_data)

    return record


# ============ 行業預設配置 ============

INDUSTRY_PRESETS = {
    "catering": {
        "name": "到會/餐飲",
        "icon": "🍽️",
        "keywords_example": "到會\n到會推介\n派對到會\n公司到會\n生日會到會\n百日宴到會\n滿月酒到會\n外賣到會",
        "sites_example": "daynightcatering.com\ncateringbear.com",
        "competitors_example": "cateringmama.com\nkamadelivery.com"
    },
    "smoking": {
        "name": "煙具",
        "icon": "🚬",
        "keywords_example": "電子煙\nvape\n煙油\n霧化器\n一次性電子煙",
        "sites_example": "",
        "competitors_example": ""
    },
    "moving": {
        "name": "搬屋/搬運",
        "icon": "🚚",
        "keywords_example": "搬屋\n搬屋公司\n搬運服務\n搬屋價錢\n迷你倉",
        "sites_example": "",
        "competitors_example": ""
    },
    "renovation": {
        "name": "裝修",
        "icon": "🔨",
        "keywords_example": "裝修\n裝修公司\n室內設計\n家居裝修\n廚房裝修",
        "sites_example": "",
        "competitors_example": ""
    },
    "education": {
        "name": "教育/補習",
        "icon": "📚",
        "keywords_example": "補習\n補習社\n私人補習\n英文補習\n數學補習",
        "sites_example": "",
        "competitors_example": ""
    },
    "beauty": {
        "name": "美容",
        "icon": "💄",
        "keywords_example": "美容院\nfacial\n護膚\n脫毛\n醫美",
        "sites_example": "",
        "competitors_example": ""
    },
    "medical": {
        "name": "醫療/診所",
        "icon": "🏥",
        "keywords_example": "診所\n牙醫\n中醫\n物理治療\n皮膚科",
        "sites_example": "",
        "competitors_example": ""
    },
    "legal": {
        "name": "法律",
        "icon": "⚖️",
        "keywords_example": "律師\n離婚律師\n法律諮詢\n刑事律師\n民事訴訟",
        "sites_example": "",
        "competitors_example": ""
    },
    "realestate": {
        "name": "地產",
        "icon": "🏠",
        "keywords_example": "買樓\n租屋\n地產代理\n樓盤\n二手樓",
        "sites_example": "",
        "competitors_example": ""
    },
    "other": {
        "name": "其他",
        "icon": "📊",
        "keywords_example": "",
        "sites_example": "",
        "competitors_example": ""
    }
}


# ============ 工具函數 ============

def normalize_domain(domain):
    """標準化網域名稱"""
    domain = domain.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.rstrip("/")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def get_record_display_name(record):
    """獲取記錄的顯示名稱"""
    date = record.get("date", "未知")
    time_str = record.get("time", "")
    keyword_count = len(record.get("rankings", []))
    return f"{date} {time_str} ({keyword_count}個關鍵字)"


def get_all_sites_from_record(record):
    """從記錄中獲取所有網站"""
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
    winning = []
    losing = []
    both_ranked = []
    only_a = []
    only_b = []
    neither = []

    site_a_normalized = normalize_domain(site_a)
    site_b_normalized = normalize_domain(site_b)

    for item in rankings:
        keyword = item.get("keyword")

        rank_a = None
        for key in item.keys():
            if key != "keyword" and normalize_domain(key) == site_a_normalized:
                rank_a = item.get(key)
                break

        rank_b = None
        for key in item.keys():
            if key != "keyword" and normalize_domain(key) == site_b_normalized:
                rank_b = item.get(key)
                break

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
    """分析單一網站的關鍵字詳情（帶排名）"""
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

    for key in details:
        details[key].sort(key=lambda x: x["order"])

    return details


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


def create_styled_ranking_dataframe(rankings, my_sites, competitors, warning_threshold, previous_rankings=None):
    """創建帶樣式的排名 DataFrame"""
    all_sites = my_sites + competitors

    display_data = []
    for rank_data in rankings:
        row = {"關鍵字": rank_data.get("keyword")}

        for site in all_sites:
            site_normalized = normalize_domain(site)
            rank = None

            for key in rank_data.keys():
                if key != "keyword" and normalize_domain(key) == site_normalized:
                    rank = rank_data.get(key)
                    break

            kw = rank_data.get("keyword")

            change = ""
            if previous_rankings and kw in previous_rankings:
                prev_data = previous_rankings[kw]
                prev_rank = None
                for key in prev_data.keys():
                    if key != "keyword" and normalize_domain(key) == site_normalized:
                        prev_rank = prev_data.get(key)
                        break

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


# ============ 顯示關鍵字列表的函數（一行一個）============

def display_keyword_list(keywords_list, rank_class="rank-top10", show_rank=True):
    """顯示關鍵字列表（一行一個）"""
    if not keywords_list:
        return

    for item in keywords_list:
        if isinstance(item, dict):
            keyword = item.get("keyword", "")
            rank = item.get("rank", "")

            if show_rank and rank:
                # 根據排名決定顏色
                if rank <= 3:
                    bg_color = "#DBEAFE"
                    text_color = "#1E40AF"
                elif rank <= 10:
                    bg_color = "#E0F2FE"
                    text_color = "#0369A1"
                elif rank <= 20:
                    bg_color = "#FEF3C7"
                    text_color = "#92400E"
                elif rank <= 30:
                    bg_color = "#F3E8FF"
                    text_color = "#7C3AED"
                else:
                    bg_color = "#FEE2E2"
                    text_color = "#DC2626"

                col1, col2 = st.columns([1, 8])
                with col1:
                    st.markdown(f"""
                    <span style="
                        display: inline-block;
                        min-width: 45px;
                        padding: 0.2rem 0.6rem;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 0.85rem;
                        background: {bg_color};
                        color: {text_color};
                        text-align: center;
                    ">#{rank}</span>
                    """, unsafe_allow_html=True)
                with col2:
                    st.markdown(f"**{keyword}**")
            else:
                col1, col2 = st.columns([1, 8])
                with col1:
                    st.markdown("""
                    <span style="
                        display: inline-block;
                        min-width: 45px;
                        padding: 0.2rem 0.6rem;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 0.85rem;
                        background: #F3F4F6;
                        color: #6B7280;
                        text-align: center;
                    ">N/A</span>
                    """, unsafe_allow_html=True)
                with col2:
                    st.markdown(f"{keyword}")
        else:
            # 純字串
            st.markdown(f"• {item}")

# ============ 搜尋引擎類別 ============

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


# ============ 初始化 Session State ============

if "projects_data" not in st.session_state:
    st.session_state.projects_data = load_projects()

if "current_results" not in st.session_state:
    st.session_state.current_results = None

if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

if "current_tab" not in st.session_state:
    st.session_state.current_tab = 0

if "show_project_manager" not in st.session_state:
    st.session_state.show_project_manager = False

# ============ 獲取當前專案 ============

active_project = get_active_project()
projects_data = st.session_state.projects_data

# ============ 標題 ============

st.markdown("""
<div class="main-header">
    <h1>🚀 SEO 排名追蹤工具 Pro</h1>
    <p>多專案管理 · 智能分析 · 競爭對手追蹤</p>
</div>
""", unsafe_allow_html=True)

# ============ 專案選擇器（頂部） ============

projects_data = load_projects()

if projects_data["projects"]:
    col_project, col_btn = st.columns([4, 1])

    with col_project:
        project_options = [(p["id"], f"{p['icon']} {p['name']} ({p['industry']})") for p in projects_data["projects"]]
        current_project_id = active_project["id"] if active_project else None

        selected_idx = 0
        for i, (pid, _) in enumerate(project_options):
            if pid == current_project_id:
                selected_idx = i
                break

        selected_project = st.selectbox(
            "🎯 當前專案",
            options=[p[1] for p in project_options],
            index=selected_idx,
            key="project_selector",
            label_visibility="collapsed"
        )

        for pid, pname in project_options:
            if pname == selected_project:
                if pid != current_project_id:
                    set_active_project(pid)
                    st.session_state.projects_data = load_projects()
                    st.session_state.current_results = None
                    st.rerun()
                break

    with col_btn:
        if st.button("⚙️ 管理專案", use_container_width=True):
            st.session_state.show_project_manager = not st.session_state.show_project_manager
            st.rerun()

    active_project = get_active_project()

    if active_project:
        project_data = load_project_data(active_project["id"])
        record_count = len(project_data.get("records", []))

        st.markdown(f"""
        <div class="project-header">
            <span style="font-size: 1.5rem;">{active_project['icon']}</span>
            <span style="font-size: 1.2rem; font-weight: bold; margin-left: 0.5rem;">{active_project['name']}</span>
            <span style="opacity: 0.8; margin-left: 1rem;">| {active_project['industry']} | {record_count} 條記錄</span>
        </div>
        """, unsafe_allow_html=True)

else:
    st.info("👋 歡迎使用！請先創建一個專案來開始追蹤 SEO 排名。")
    st.session_state.show_project_manager = True

# ============ 專案管理面板 ============

if st.session_state.show_project_manager:
    st.markdown("---")
    st.markdown("## 📁 專案管理")

    tab_create, tab_list, tab_import = st.tabs(["➕ 創建專案", "📋 專案列表", "📤 匯入/匯出"])

    with tab_create:
        st.markdown("### 創建新專案")

        col1, col2 = st.columns(2)

        with col1:
            new_project_name = st.text_input("專案名稱 *", placeholder="例如：到會業務 SEO")

            industry_options = list(INDUSTRY_PRESETS.keys())
            industry_labels = [f"{INDUSTRY_PRESETS[k]['icon']} {INDUSTRY_PRESETS[k]['name']}" for k in industry_options]

            selected_industry_label = st.selectbox("行業類型 *", industry_labels)
            selected_industry = industry_options[industry_labels.index(selected_industry_label)]

            preset = INDUSTRY_PRESETS[selected_industry]

            new_project_desc = st.text_area("專案描述（選填）", placeholder="描述這個專案的目標或備註")

        with col2:
            st.markdown("**我的網站**")
            new_my_sites = st.text_area(
                "每行一個網域",
                value=preset["sites_example"],
                height=100,
                key="new_proj_sites"
            )

            st.markdown("**競爭對手**")
            new_competitors = st.text_area(
                "每行一個網域",
                value=preset["competitors_example"],
                height=100,
                key="new_proj_competitors"
            )

        if st.button("✅ 創建專案", type="primary", use_container_width=True):
            if not new_project_name:
                st.error("❌ 請輸入專案名稱")
            else:
                my_sites_list = [s.strip() for s in new_my_sites.split("\n") if s.strip()]
                competitors_list = [s.strip() for s in new_competitors.split("\n") if s.strip()]

                project_id = create_project(
                    name=new_project_name,
                    industry=preset["name"],
                    description=new_project_desc,
                    my_sites=my_sites_list,
                    competitors=competitors_list,
                    icon=preset["icon"]
                )

                st.session_state.projects_data = load_projects()
                set_active_project(project_id)
                st.success(f"✅ 專案「{new_project_name}」創建成功！")
                st.session_state.show_project_manager = False
                st.rerun()

    with tab_list:
        st.markdown("### 所有專案")

        projects = load_projects()["projects"]

        if not projects:
            st.info("還沒有任何專案")
        else:
            for project in projects:
                proj_data = load_project_data(project["id"])
                record_count = len(proj_data.get("records", []))
                keyword_group_count = len(proj_data.get("keyword_groups", {}))
                is_active = project["id"] == (active_project["id"] if active_project else None)

                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                    with col1:
                        status = "🟢 " if is_active else ""
                        st.markdown(f"""
                        **{status}{project['icon']} {project['name']}**  
                        {project['industry']} | {record_count} 記錄 | {keyword_group_count} 關鍵字組
                        """)
                        if project.get("description"):
                            st.caption(project["description"])

                    with col2:
                        if not is_active:
                            if st.button("切換", key=f"switch_{project['id']}", use_container_width=True):
                                set_active_project(project["id"])
                                st.session_state.projects_data = load_projects()
                                st.session_state.current_results = None
                                st.rerun()
                        else:
                            st.markdown("**使用中**")

                    with col3:
                        if st.button("✏️ 編輯", key=f"edit_{project['id']}", use_container_width=True):
                            st.session_state[f"editing_project_{project['id']}"] = True
                            st.rerun()

                    with col4:
                        if st.button("🗑️", key=f"delete_{project['id']}", use_container_width=True):
                            st.session_state[f"confirm_delete_{project['id']}"] = True
                            st.rerun()

                    if st.session_state.get(f"confirm_delete_{project['id']}", False):
                        st.warning(f"⚠️ 確定要刪除專案「{project['name']}」嗎？所有數據將被永久刪除！")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("確認刪除", key=f"confirm_yes_{project['id']}", type="primary"):
                                delete_project(project["id"])
                                st.session_state.projects_data = load_projects()
                                del st.session_state[f"confirm_delete_{project['id']}"]
                                st.success("已刪除")
                                st.rerun()
                        with col_no:
                            if st.button("取消", key=f"confirm_no_{project['id']}"):
                                del st.session_state[f"confirm_delete_{project['id']}"]
                                st.rerun()

                    if st.session_state.get(f"editing_project_{project['id']}", False):
                        st.markdown("---")
                        col_e1, col_e2 = st.columns(2)

                        with col_e1:
                            edit_name = st.text_input("專案名稱", value=project["name"],
                                                      key=f"edit_name_{project['id']}")
                            edit_desc = st.text_area("描述", value=project.get("description", ""),
                                                     key=f"edit_desc_{project['id']}")

                        with col_e2:
                            edit_sites = st.text_area(
                                "我的網站",
                                value="\n".join(project.get("my_sites", [])),
                                key=f"edit_sites_{project['id']}"
                            )
                            edit_competitors = st.text_area(
                                "競爭對手",
                                value="\n".join(project.get("competitors", [])),
                                key=f"edit_comp_{project['id']}"
                            )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 儲存", key=f"save_edit_{project['id']}", type="primary",
                                         use_container_width=True):
                                update_project(project["id"], {
                                    "name": edit_name,
                                    "description": edit_desc,
                                    "my_sites": [s.strip() for s in edit_sites.split("\n") if s.strip()],
                                    "competitors": [s.strip() for s in edit_competitors.split("\n") if s.strip()]
                                })
                                st.session_state.projects_data = load_projects()
                                del st.session_state[f"editing_project_{project['id']}"]
                                st.success("✅ 已更新")
                                st.rerun()
                        with col_cancel:
                            if st.button("取消", key=f"cancel_edit_{project['id']}", use_container_width=True):
                                del st.session_state[f"editing_project_{project['id']}"]
                                st.rerun()

                    st.markdown("---")

    with tab_import:
        st.markdown("### 匯入/匯出專案")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📥 匯出")

            if projects_data["projects"]:
                export_data = {
                    "projects": projects_data["projects"],
                    "project_data": {}
                }
                for project in projects_data["projects"]:
                    export_data["project_data"][project["id"]] = load_project_data(project["id"])

                json_export = json.dumps(export_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📥 匯出所有專案",
                    data=json_export,
                    file_name=f"seo_projects_backup_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )

                if active_project:
                    single_export = {
                        "project": active_project,
                        "data": load_project_data(active_project["id"])
                    }
                    json_single = json.dumps(single_export, ensure_ascii=False, indent=2)
                    st.download_button(
                        label=f"📥 只匯出「{active_project['name']}」",
                        data=json_single,
                        file_name=f"seo_project_{active_project['name']}_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json",
                        use_container_width=True
                    )

        with col2:
            st.markdown("#### 📤 匯入")

            uploaded_file = st.file_uploader("上傳專案備份 JSON", type=["json"], key="import_projects")

            if uploaded_file:
                try:
                    imported = json.load(uploaded_file)

                    if "projects" in imported:
                        st.info(f"檢測到 {len(imported['projects'])} 個專案")
                        if st.button("確認匯入所有專案", type="primary"):
                            for project in imported["projects"]:
                                existing_ids = [p["id"] for p in projects_data["projects"]]
                                if project["id"] not in existing_ids:
                                    projects_data["projects"].append(project)
                                    if project["id"] in imported.get("project_data", {}):
                                        save_project_data(project["id"], imported["project_data"][project["id"]])

                            save_projects(projects_data)
                            st.session_state.projects_data = load_projects()
                            st.success("✅ 匯入成功！")
                            st.rerun()

                    elif "project" in imported:
                        project = imported["project"]
                        st.info(f"檢測到專案：{project['name']}")
                        if st.button("確認匯入此專案", type="primary"):
                            new_id = f"proj_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
                            project["id"] = new_id

                            projects_data["projects"].append(project)
                            save_projects(projects_data)
                            save_project_data(new_id, imported.get("data", {}))

                            st.session_state.projects_data = load_projects()
                            st.success("✅ 匯入成功！")
                            st.rerun()

                except Exception as e:
                    st.error(f"匯入失敗：{e}")

    st.markdown("---")

# ============ 主功能區（需要有活躍專案）============

if active_project:
    current_project_data = load_project_data(active_project["id"])

    # ============ 側邊欄設定 ============

    with st.sidebar:
        st.markdown("## ⚙️ 設定")

        api_key = st.text_input("🔑 Serper API Key", type="password")

        if api_key:
            st.success("✅ API Key 已設定")
        else:
            st.warning("⚠️ 請輸入 API Key")

        st.markdown("---")

        # 搜尋設定（緊湊版）
        st.markdown("### 🔍 搜尋設定")

        col1, col2 = st.columns(2)
        with col1:
            search_region = st.selectbox(
                "地區",
                options=["hk", "tw", "sg", "my", "us", "uk"],
                format_func=lambda x: {"hk": "🇭🇰 香港", "tw": "🇹🇼 台灣", "sg": "🇸🇬 新加坡",
                                       "my": "🇲🇾 馬來西亞", "us": "🇺🇸 美國", "uk": "🇬🇧 英國"}[x],
                label_visibility="collapsed"
            )

        with col2:
            search_lang = st.selectbox(
                "語言",
                options=["zh-tw", "zh-cn", "en"],
                format_func=lambda x: {"zh-tw": "繁體", "zh-cn": "简体", "en": "EN"}[x],
                label_visibility="collapsed"
            )

        max_pages = st.slider("📄 爬取頁數", 1, 10, 5)

        autocorrect_enabled = st.toggle("🔤 自動校正", value=False, help="關閉時會搜尋原始關鍵字")
        if not autocorrect_enabled:
            st.caption("📝 已關閉自動校正")

        st.markdown("---")

        st.markdown("### 🏠 我的網站")
        default_my_sites = "\n".join(active_project.get("my_sites", []))
        my_sites_input = st.text_area(
            "每行一個網域",
            value=default_my_sites,
            height=80,
            key="my_sites",
            label_visibility="collapsed"
        )
        my_sites = [s.strip() for s in my_sites_input.split("\n") if s.strip()]

        st.markdown("### 🎯 競爭對手")
        default_competitors = "\n".join(active_project.get("competitors", []))
        competitors_input = st.text_area(
            "每行一個網域",
            value=default_competitors,
            height=60,
            key="competitors",
            label_visibility="collapsed"
        )
        competitors = [s.strip() for s in competitors_input.split("\n") if s.strip()]

        st.markdown("---")

        st.markdown("### 🎨 顯示設定")
        warning_threshold = st.number_input(
            "⚠️ 警告閾值",
            min_value=10,
            max_value=100,
            value=20,
            step=5
        )

        st.markdown("---")

        # 速度模式移到最下面
        st.markdown("### ⚡ 速度模式")
        speed_mode = st.radio(
            "選擇模式",
            options=["stable", "balanced", "fast"],
            format_func=lambda x: {
                "stable": "🐢 穩定模式",
                "balanced": "⚖️ 平衡模式",
                "fast": "🚀 高速模式"
            }[x],
            index=1,
            label_visibility="collapsed"
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
        debug_mode = st.checkbox("🐛 調試信息", value=False)

    # ============ 導航按鈕 ============

    st.markdown("---")

    nav_cols = st.columns(5)
    tab_names = ["🔍 排名查詢", "🏷️ 關鍵字管理", "📊 數據分析", "📈 歷史記錄", "⚙️ 管理"]

    for i, (col, name) in enumerate(zip(nav_cols, tab_names)):
        with col:
            if st.button(name, key=f"nav_{i}", use_container_width=True,
                         type="primary" if st.session_state.current_tab == i else "secondary"):
                st.session_state.current_tab = i
                st.rerun()

    st.markdown("---")

    # ============ Tab 0: 排名查詢 ============

    if st.session_state.current_tab == 0:
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown("### 📝 輸入關鍵字")

            industry_key = None
            for key, preset in INDUSTRY_PRESETS.items():
                if preset["name"] == active_project.get("industry"):
                    industry_key = key
                    break

            default_keywords = INDUSTRY_PRESETS.get(industry_key, {}).get("keywords_example",
                                                                          "") if industry_key else ""

            keywords_input = st.text_area(
                "每行一個關鍵字",
                value=st.session_state.get("keywords_input", default_keywords),
                height=200,
                key="keywords_text_area"
            )
            st.session_state["keywords_input"] = keywords_input
            keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

        with col_right:
            st.markdown("### 📂 關鍵字組（點擊複製）")

            keyword_groups = current_project_data.get("keyword_groups", {})

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

                    keywords_text = "\n".join(group_keywords)
                    st.code(keywords_text, language=None)
                    st.caption("👆 點擊右上角複製")
            else:
                st.info("💡 還沒有關鍵字組")

            st.markdown("---")
            st.markdown("### 📋 查詢資訊")
            st.markdown(f"**關鍵字數量：** {len(keywords)}")
            st.markdown(f"**API 請求數：** {len(keywords) * max_pages}")

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

            success_rate = searcher.success_count / (
                        searcher.success_count + searcher.fail_count) * 100 if (searcher.success_count + searcher.fail_count) > 0 else 0

            if success_rate >= 90:
                st.success(f"✅ 完成！耗時 {elapsed_time:.1f}s，成功率 {success_rate:.0f}%")
            elif success_rate >= 70:
                st.warning(f"⚠️ 完成，部分失敗。耗時 {elapsed_time:.1f}s，成功率 {success_rate:.0f}%")
            else:
                st.error(f"❌ 大量失敗。成功率 {success_rate:.0f}%")

            st.session_state.current_results = {
                "rankings": all_rankings,
                "serp_data": serp_results,
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": elapsed_time,
                "success_rate": success_rate,
                "my_sites": my_sites,
                "competitors": competitors,
                "keywords": keywords
            }

            record = {
                "rankings": all_rankings,
                "my_sites": my_sites,
                "competitors": competitors,
                "region": search_region,
                "keywords": keywords,
                "autocorrect": autocorrect_enabled
            }
            add_record_to_project(active_project["id"], record)

        # ============ 顯示結果 ============

        if st.session_state.current_results:
            st.markdown("---")

            results = st.session_state.current_results
            rankings = results["rankings"]
            result_my_sites = results.get("my_sites", my_sites)
            result_competitors = results.get("competitors", competitors)
            result_keywords = results.get("keywords", [])
            keyword_order_map = {kw: idx for idx, kw in enumerate(result_keywords)}

            history_records = current_project_data.get("records", [])
            previous_rankings = {}
            if len(history_records) >= 2:
                prev_record = history_records[-2]
                for item in prev_record.get("rankings", []):
                    previous_rankings[item.get("keyword")] = item

            st.markdown("## 📋 詳細排名")

            st.markdown(f"""
            **圖例：** 🔵 我的網站（藍色系）| 🟠 競爭對手（橙色系）| ⚠️ 紅色 = 排名 > {warning_threshold} | N/A = 未上榜
            """)

            df_display, styled_df = create_styled_ranking_dataframe(
                rankings, result_my_sites, result_competitors, warning_threshold, previous_rankings
            )

            st.dataframe(styled_df, use_container_width=True, height=500)

            def create_excel(rankings_data, serp_data, my_sites_list, competitors_list):
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_rankings = pd.DataFrame(rankings_data)
                    df_rankings.to_excel(writer, sheet_name="排名總覽", index=False)

                    serp_records = []
                    for keyword, results_list in serp_data.items():
                        for result in results_list:
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
                    file_name=f"{active_project['name']}_排名_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col_dl2:
                csv_data = df_display.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 下載 CSV",
                    data=csv_data,
                    file_name=f"{active_project['name']}_排名_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # ============ 排名總覽（一行一個關鍵字樣式） ============

            st.markdown("---")
            st.markdown("## 📊 排名總覽")

            if result_my_sites:
                st.markdown("### 🏠 我的網站")

                for site in result_my_sites:
                    analysis = analyze_site_keywords_detail(rankings, site, warning_threshold, keyword_order_map)

                    with st.expander(f"📊 **{site}**", expanded=True):
                        cols = st.columns(6)

                        categories = [
                            ("🏆 前3名", "top3", "#10B981", len(analysis["top3"])),
                            ("📄 首頁(4-10)", "top10", "#3B82F6", len(analysis["top10"])),
                            ("📑 第2頁(11-20)", "top20", "#F59E0B", len(analysis["top20"])),
                            ("📋 第3頁(21-30)", "top30", "#8B5CF6", len(analysis["top30"])),
                            (f"⚠️ >{warning_threshold}名", "warning", "#EF4444", len(analysis["warning"])),
                            ("❌ 未上榜", "na", "#6B7280", len(analysis["na"]))
                        ]

                        for i, (label, key, color, count) in enumerate(categories):
                            with cols[i]:
                                st.markdown(f"""
                                <div style="text-align: center; padding: 0.5rem; background: white; border-radius: 8px; border-left: 3px solid {color};">
                                    <div style="font-size: 1.5rem; font-weight: bold; color: {color};">{count}</div>
                                    <div style="font-size: 0.75rem; color: #666;">{label}</div>
                                </div>
                                """, unsafe_allow_html=True)

                        st.markdown("---")

                        detail_tabs = st.tabs([
                            f"🏆 前3名 ({len(analysis['top3'])})",
                            f"📄 首頁 ({len(analysis['top10'])})",
                            f"📑 第2頁 ({len(analysis['top20'])})",
                            f"📋 第3頁 ({len(analysis['top30'])})",
                            f"⚠️ 警告 ({len(analysis['warning'])})",
                            f"❌ 未上榜 ({len(analysis['na'])})"
                        ])

                        with detail_tabs[0]:
                            if analysis["top3"]:
                                display_keyword_list(analysis["top3"], "rank-top3")
                            else:
                                st.info("沒有排在前3名的關鍵字")

                        with detail_tabs[1]:
                            if analysis["top10"]:
                                display_keyword_list(analysis["top10"], "rank-top10")
                            else:
                                st.info("沒有排在4-10名的關鍵字")

                        with detail_tabs[2]:
                            if analysis["top20"]:
                                display_keyword_list(analysis["top20"], "rank-top20")
                            else:
                                st.info("沒有排在11-20名的關鍵字")

                        with detail_tabs[3]:
                            if analysis["top30"]:
                                display_keyword_list(analysis["top30"], "rank-top30")
                            else:
                                st.info("沒有排在21-30名的關鍵字")

                        with detail_tabs[4]:
                            if analysis["warning"]:
                                st.warning(f"⚠️ 以下 {len(analysis['warning'])} 個關鍵字排名超過 {warning_threshold}：")
                                display_keyword_list(analysis["warning"], "rank-warning")
                            else:
                                st.success("沒有需要警告的關鍵字！")

                        with detail_tabs[5]:
                            if analysis["na"]:
                                display_keyword_list(analysis["na"], "rank-na", show_rank=False)
                            else:
                                st.success("所有關鍵字都有排名！")

            if result_competitors:
                st.markdown("### 🎯 競爭對手")
            
                for site in result_competitors:
                    analysis = analyze_site_keywords_detail(rankings, site, warning_threshold, keyword_order_map)
            
                    with st.expander(f"📊 **{site}**", expanded=False):
                        cols = st.columns(6)
            
                        categories = [
                            ("🏆 前3名", "top3", "#DC2626", len(analysis["top3"])),
                            ("📄 首頁(4-10)", "top10", "#F59E0B", len(analysis["top10"])),
                            ("📑 第2頁(11-20)", "top20", "#6B7280", len(analysis["top20"])),
                            ("📋 第3頁(21-30)", "top30", "#9CA3AF", len(analysis["top30"])),
                            (f"⚠️ >{warning_threshold}名", "warning", "#10B981", len(analysis["warning"])),
                            ("❌ 未上榜", "na", "#10B981", len(analysis["na"]))
                        ]
            
                        for i, (label, key, color, count) in enumerate(categories):
                            with cols[i]:
                                st.markdown(f"""
                                <div style="text-align: center; padding: 0.5rem; background: white; border-radius: 8px; border-left: 3px solid {color};">
                                    <div style="font-size: 1.5rem; font-weight: bold; color: {color};">{count}</div>
                                    <div style="font-size: 0.75rem; color: #666;">{label}</div>
                                </div>
                                """, unsafe_allow_html=True)
            
                        st.markdown("---")
            
                        # ✅ 修改這裡：6 個 tabs
                        detail_tabs = st.tabs([
                            f"🏆 前3名 ({len(analysis['top3'])})",
                            f"📄 首頁 ({len(analysis['top10'])})",
                            f"📑 第2頁 ({len(analysis['top20'])})",
                            f"📋 第3頁 ({len(analysis['top30'])})",
                            f"⚠️ 警告 ({len(analysis['warning'])})",
                            f"❌ 未上榜 ({len(analysis['na'])})"
                        ])
            
                        with detail_tabs[0]:
                            if analysis["top3"]:
                                st.warning("⚠️ 競爭對手在這些關鍵字排名很高：")
                                display_keyword_list(analysis["top3"], "rank-warning")
                            else:
                                st.success("競爭對手沒有排在前3名的關鍵字")
            
                        with detail_tabs[1]:
                            if analysis["top10"]:
                                st.warning("⚠️ 競爭對手在首頁：")
                                display_keyword_list(analysis["top10"], "rank-top10")
                            else:
                                st.info("競爭對手沒有排在4-10名的關鍵字")
            
                        with detail_tabs[2]:
                            if analysis["top20"]:
                                display_keyword_list(analysis["top20"], "rank-top20")
                            else:
                                st.info("競爭對手沒有排在11-20名的關鍵字")
            
                        with detail_tabs[3]:
                            if analysis["top30"]:
                                display_keyword_list(analysis["top30"], "rank-top30")
                            else:
                                st.info("競爭對手沒有排在21-30名的關鍵字")
            
                        with detail_tabs[4]:
                            if analysis["warning"]:
                                st.success(f"✅ 競爭對手這些關鍵字排名差（>{warning_threshold}）：")
                                display_keyword_list(analysis["warning"], "rank-warning")
                            else:
                                st.info("競爭對手沒有排名很差的關鍵字")
            
                        with detail_tabs[5]:
                            if analysis["na"]:
                                st.success("✅ 競爭對手在這些關鍵字沒有排名：")
                                display_keyword_list(analysis["na"], "rank-na", show_rank=False)
                            else:
                                st.warning("競爭對手在所有關鍵字都有排名")

    # ============ Tab 1: 關鍵字管理 ============

    elif st.session_state.current_tab == 1:
        st.markdown("### 🏷️ 關鍵字組管理")
        st.caption(f"專案：{active_project['icon']} {active_project['name']}")

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("#### ➕ 新增關鍵字組")

            new_group_name = st.text_input("組名", placeholder="例如：核心關鍵字", key="new_group_name")
            new_group_keywords = st.text_area(
                "關鍵字（每行一個）",
                height=200,
                key="new_group_keywords"
            )
            new_group_desc = st.text_input("描述（選填）", key="new_group_desc")

            if st.button("💾 儲存關鍵字組", type="primary", use_container_width=True):
                if not new_group_name:
                    st.error("❌ 請輸入組名")
                elif not new_group_keywords.strip():
                    st.error("❌ 請輸入至少一個關鍵字")
                else:
                    keywords_list = [k.strip() for k in new_group_keywords.split("\n") if k.strip()]

                    project_data = load_project_data(active_project["id"])
                    if "keyword_groups" not in project_data:
                        project_data["keyword_groups"] = {}

                    project_data["keyword_groups"][new_group_name] = {
                        "keywords": keywords_list,
                        "description": new_group_desc,
                        "created": datetime.now().isoformat(),
                        "updated": datetime.now().isoformat()
                    }
                    save_project_data(active_project["id"], project_data)
                    st.success(f"✅ 已儲存「{new_group_name}」（{len(keywords_list)} 個關鍵字）")
                    st.rerun()

        with col_right:
            st.markdown("#### 📋 現有關鍵字組")

            keyword_groups = current_project_data.get("keyword_groups", {})

            if not keyword_groups:
                st.info("💡 還沒有關鍵字組")
            else:
                for group_name, group_data in keyword_groups.items():
                    group_keywords = group_data.get("keywords", [])
                    group_desc = group_data.get("description", "")

                    with st.expander(f"📁 {group_name} ({len(group_keywords)}個)", expanded=False):
                        st.markdown(f"**描述：** {group_desc if group_desc else '無'}")

                        keywords_text = "\n".join(group_keywords)
                        st.code(keywords_text, language=None)

                        col1, col2 = st.columns(2)

                        with col2:
                            if st.button("🗑️ 刪除", key=f"delete_{group_name}", use_container_width=True):
                                project_data = load_project_data(active_project["id"])
                                del project_data["keyword_groups"][group_name]
                                save_project_data(active_project["id"], project_data)
                                st.success(f"✅ 已刪除「{group_name}」")
                                st.rerun()

    # ============ Tab 2: 數據分析 ============

    elif st.session_state.current_tab == 2:
        st.markdown("### 📊 SEO 數據分析")
        st.caption(f"專案：{active_project['icon']} {active_project['name']}")

        history_records = current_project_data.get("records", [])

        if not history_records:
            st.info("📊 還沒有數據，請先執行排名查詢")
        else:
            analysis_warning_threshold = st.number_input(
                "⚠️ 分析警告閾值",
                min_value=10,
                max_value=100,
                value=20,
                step=5,
                key="analysis_warning_threshold"
            )

            st.markdown("---")

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

                st.info(
                    f"📊 分析記錄: {selected_record.get('date', '')} {selected_record.get('time', '')} | {len(rankings)} 個關鍵字")

                st.markdown("---")

                if rankings:
                    # ============ 🔍 各網站詳細關鍵字分析 ============

                    st.markdown("### 🔍 各網站詳細關鍵字")

                    analysis_site = st.selectbox(
                        "選擇要查看的網站",
                        options=all_sites_in_record,
                        key="detail_analysis_site"
                    )

                    if analysis_site:
                        site_type = "🏠 我的網站" if analysis_site in tracked_my_sites else "🎯 競爭對手"
                        st.markdown(f"**{site_type}：** `{analysis_site}`")

                        details = analyze_site_keywords_detail(rankings, analysis_site, analysis_warning_threshold,
                                                               keyword_order_map)

                        cols = st.columns(6)
                        categories = [
                            ("🏆 前3名", "top3", "#10B981"),
                            ("📄 首頁(4-10)", "top10", "#3B82F6"),
                            ("📑 第2頁(11-20)", "top20", "#F59E0B"),
                            ("📋 第3頁(21-30)", "top30", "#8B5CF6"),
                            (f"⚠️ >{analysis_warning_threshold}名", "warning", "#EF4444"),
                            ("❌ 未上榜", "na", "#6B7280")
                        ]

                        for i, (label, key, color) in enumerate(categories):
                            with cols[i]:
                                count = len(details[key])
                                st.markdown(f"""
                                <div class="stat-card" style="border-left-color: {color};">
                                    <div style="font-size: 1.8rem; font-weight: bold; color: {color};">{count}</div>
                                    <div style="font-size: 0.8rem; color: #666;">{label}</div>
                                </div>
                                """, unsafe_allow_html=True)

                        st.markdown("---")

                        detail_tabs = st.tabs([
                            f"🏆 前3名 ({len(details['top3'])})",
                            f"📄 首頁4-10 ({len(details['top10'])})",
                            f"📑 第2頁11-20 ({len(details['top20'])})",
                            f"📋 第3頁21-30 ({len(details['top30'])})",
                            f"⚠️ 警告 ({len(details['warning'])})",
                            f"❌ 未上榜 ({len(details['na'])})"
                        ])

                        with detail_tabs[0]:
                            if details["top3"]:
                                st.success("🏆 這些關鍵字排名很好！")
                                display_keyword_list(details["top3"], "rank-top3")
                            else:
                                st.info("沒有排在前3名的關鍵字")

                        with detail_tabs[1]:
                            if details["top10"]:
                                display_keyword_list(details["top10"], "rank-top10")
                            else:
                                st.info("沒有排在4-10名的關鍵字")

                        with detail_tabs[2]:
                            if details["top20"]:
                                display_keyword_list(details["top20"], "rank-top20")
                            else:
                                st.info("沒有排在11-20名的關鍵字")

                        with detail_tabs[3]:
                            if details["top30"]:
                                display_keyword_list(details["top30"], "rank-top30")
                            else:
                                st.info("沒有排在21-30名的關鍵字")

                        with detail_tabs[4]:
                            if details["warning"]:
                                st.warning(f"⚠️ 以下 {len(details['warning'])} 個關鍵字排名超過 {analysis_warning_threshold}：")
                                display_keyword_list(details["warning"], "rank-warning")
                            else:
                                st.success("沒有需要警告的關鍵字！")

                        with detail_tabs[5]:
                            if details["na"]:
                                st.error("❌ 這些關鍵字完全沒有排名：")
                                display_keyword_list(details["na"], "rank-na", show_rank=False)
                            else:
                                st.success("所有關鍵字都有排名！")

                    st.markdown("---")

                    # ============ 🥊 關鍵字爭奪分析 ============

                    st.markdown("### 🥊 關鍵字爭奪分析")

                    col1, col2 = st.columns(2)
                    with col1:
                        site_a = st.selectbox("選擇網站 A", all_sites_in_record, key="compete_site_a")
                    with col2:
                        site_b_options = [s for s in all_sites_in_record if
                                          normalize_domain(s) != normalize_domain(site_a)]
                        site_b = st.selectbox("選擇網站 B",
                                              site_b_options if site_b_options else all_sites_in_record,
                                              key="compete_site_b")

                    if site_a and site_b and normalize_domain(site_a) != normalize_domain(site_b):
                        site_a_type = "🏠 我的網站" if site_a in tracked_my_sites else "🎯 競爭對手"
                        site_b_type = "🏠 我的網站" if site_b in tracked_my_sites else "🎯 競爭對手"

                        st.markdown(f"**比較：** {site_a_type} `{site_a}` **vs** {site_b_type} `{site_b}`")

                        competition = analyze_keyword_competition(rankings, site_a, site_b, keyword_order_map)

                        winning = competition["winning"]
                        losing = competition["losing"]
                        only_a = competition["only_a"]
                        only_b = competition["only_b"]
                        neither = competition["neither"]
                        both_ranked = competition["both_ranked"]

                        site_a_short = site_a[:15] + "..." if len(site_a) > 15 else site_a
                        site_b_short = site_b[:15] + "..." if len(site_b) > 15 else site_b

                        stat_cols = st.columns(5)
                        with stat_cols[0]:
                            st.metric(f"🏆 {site_a_short} 贏", len(winning))
                        with stat_cols[1]:
                            st.metric(f"😢 {site_a_short} 輸", len(losing))
                        with stat_cols[2]:
                            st.metric(f"✅ 只有 A", len(only_a))
                        with stat_cols[3]:
                            st.metric(f"⚠️ 只有 B", len(only_b))
                        with stat_cols[4]:
                            st.metric("❌ 都沒排名", len(neither))

                        compete_tabs = st.tabs([
                            f"🏆 {site_a_short} 贏 ({len(winning)})",
                            f"😢 {site_a_short} 輸 ({len(losing)})",
                            f"✅ 只有 {site_a_short} ({len(only_a)})",
                            f"⚠️ 只有 {site_b_short} ({len(only_b)})",
                            f"❌ 都沒排名 ({len(neither)})",
                            f"📊 雙方都有排名 ({len(both_ranked)})"
                        ])

                        with compete_tabs[0]:
                            if winning:
                                st.success(f"🏆 {site_a} 在這些關鍵字領先：")
                                win_data = [{
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"],
                                    f"{site_b} 排名": item["rank_b"],
                                    "優勢": item["rank_b"] - item["rank_a"]
                                } for item in winning]
                                st.dataframe(pd.DataFrame(win_data), use_container_width=True, hide_index=True)
                            else:
                                st.info("沒有領先的關鍵字")

                        with compete_tabs[1]:
                            if losing:
                                st.warning(f"😢 {site_a} 在這些關鍵字落後：")
                                lose_data = [{
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"],
                                    f"{site_b} 排名": item["rank_b"],
                                    "落後": item["rank_a"] - item["rank_b"]
                                } for item in losing]
                                st.dataframe(pd.DataFrame(lose_data), use_container_width=True, hide_index=True)
                            else:
                                st.success("沒有落後的關鍵字！")

                        with compete_tabs[2]:
                            if only_a:
                                st.success(f"✅ 只有 {site_a} 有排名：")
                                only_a_data = [{
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"]
                                } for item in only_a]
                                st.dataframe(pd.DataFrame(only_a_data), use_container_width=True, hide_index=True)
                            else:
                                st.info("沒有獨佔的關鍵字")

                        with compete_tabs[3]:
                            if only_b:
                                st.warning(f"⚠️ 只有 {site_b} 有排名（需要加強）：")
                                only_b_data = [{
                                    "關鍵字": item["keyword"],
                                    f"{site_b} 排名": item["rank_b"]
                                } for item in only_b]
                                st.dataframe(pd.DataFrame(only_b_data), use_container_width=True, hide_index=True)
                            else:
                                st.success("對手沒有獨佔的關鍵字！")

                        with compete_tabs[4]:
                            if neither:
                                st.info("這些關鍵字雙方都沒有排名：")
                                neither_cols = st.columns(3)
                                for idx, item in enumerate(neither):
                                    with neither_cols[idx % 3]:
                                        st.markdown(f"• {item['keyword']}")
                            else:
                                st.success("所有關鍵字至少有一方有排名")

                        with compete_tabs[5]:
                            if both_ranked:
                                both_data = [{
                                    "關鍵字": item["keyword"],
                                    f"{site_a} 排名": item["rank_a"],
                                    f"{site_b} 排名": item["rank_b"],
                                    "差距": item["diff"],
                                    "狀態": "✅ 領先" if item["diff"] > 0 else ("😢 落後" if item["diff"] < 0 else "⚖️ 平手")
                                } for item in both_ranked]
                                st.dataframe(pd.DataFrame(both_data), use_container_width=True, hide_index=True)
                            else:
                                st.info("沒有雙方都有排名的關鍵字")

    # ============ Tab 3: 歷史記錄 ============

    elif st.session_state.current_tab == 3:
        st.markdown("### 📜 歷史記錄")
        st.caption(f"專案：{active_project['icon']} {active_project['name']}")

        history_records = current_project_data.get("records", [])

        if not history_records:
            st.info("📊 還沒有歷史記錄")
        else:
            st.markdown(f"**共 {len(history_records)} 條記錄**")

            history_warning_threshold = st.number_input(
                "⚠️ 警告閾值",
                min_value=10,
                max_value=100,
                value=20,
                step=5,
                key="history_warning_threshold"
            )

            st.markdown("---")

            for i, record in enumerate(reversed(history_records)):
                record_idx = len(history_records) - 1 - i
                record_date = record.get("date", "未知")
                record_time = record.get("time", "")
                record_id = record.get("id", f"record_{i}")
                keyword_count = len(record.get("rankings", []))

                col1, col2, col3 = st.columns([4, 1, 1])

                with col1:
                    expander_title = f"📅 {record_date} {record_time} | {keyword_count}個關鍵字"

                    with st.expander(expander_title, expanded=False):
                        info_col1, info_col2 = st.columns(2)
                        with info_col1:
                            st.markdown("**🏠 網站：**")
                            st.write(", ".join(record.get("my_sites", [])))
                        with info_col2:
                            st.markdown("**🎯 競爭對手：**")
                            st.write(", ".join(record.get("competitors", [])))

                        st.markdown("---")

                        record_my_sites = record.get("my_sites", [])
                        record_competitors = record.get("competitors", [])
                        record_rankings = record.get("rankings", [])

                        prev_rankings_dict = {}
                        if record_idx > 0:
                            prev_record = history_records[record_idx - 1]
                            for item in prev_record.get("rankings", []):
                                prev_rankings_dict[item.get("keyword")] = item

                        df_display, styled_df = create_styled_ranking_dataframe(
                            record_rankings,
                            record_my_sites,
                            record_competitors,
                            history_warning_threshold,
                            prev_rankings_dict
                        )

                        st.dataframe(styled_df, use_container_width=True, height=400)

                        st.markdown("---")
                        st.markdown("**📊 各網站排名統計：**")

                        all_record_sites = record_my_sites + record_competitors
                        keyword_order = get_keyword_order_map(record)

                        for site in all_record_sites:
                            site_analysis = analyze_site_keywords_detail(record_rankings, site,
                                                                         history_warning_threshold, keyword_order)
                            site_type = "🏠" if site in record_my_sites else "🎯"

                            col_stats = st.columns(7)
                            with col_stats[0]:
                                st.markdown(f"**{site_type} {site[:20]}**")
                            with col_stats[1]:
                                st.markdown(f"🏆 {len(site_analysis['top3'])}")
                            with col_stats[2]:
                                st.markdown(f"📄 {len(site_analysis['top10'])}")
                            with col_stats[3]:
                                st.markdown(f"📑 {len(site_analysis['top20'])}")
                            with col_stats[4]:
                                st.markdown(f"📋 {len(site_analysis['top30'])}")
                            with col_stats[5]:
                                st.markdown(f"⚠️ {len(site_analysis['warning'])}")
                            with col_stats[6]:
                                st.markdown(f"❌ {len(site_analysis['na'])}")

                with col2:
                    excel_data = export_single_record(record)
                    st.download_button(
                        label="📥 Excel",
                        data=excel_data,
                        file_name=f"{active_project['name']}_{record_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_excel_{record_id}_{i}"
                    )

                with col3:
                    if st.button("🗑️", key=f"del_record_{record_id}_{i}"):
                        project_data = load_project_data(active_project["id"])
                        project_data["records"] = [r for r in project_data["records"] if r.get("id") != record_id]
                        save_project_data(active_project["id"], project_data)
                        st.success("已刪除")
                        st.rerun()

    # ============ Tab 4: 管理 ============

    elif st.session_state.current_tab == 4:
        st.markdown("### ⚙️ 專案數據管理")
        st.caption(f"專案：{active_project['icon']} {active_project['name']}")

        history_records = current_project_data.get("records", [])
        keyword_groups = current_project_data.get("keyword_groups", {})

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div style="font-size: 2rem; font-weight: bold; color: #667eea;">{len(history_records)}</div>
                <div>總記錄數</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div style="font-size: 2rem; font-weight: bold; color: #10B981;">{len(keyword_groups)}</div>
                <div>關鍵字組</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            total_keywords = sum(len(g.get("keywords", [])) for g in keyword_groups.values())
            st.markdown(f"""
            <div class="stat-card">
                <div style="font-size: 2rem; font-weight: bold; color: #F59E0B;">{total_keywords}</div>
                <div>總關鍵字數</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📤 匯出專案數據")

            if history_records or keyword_groups:
                export_data = {
                    "project": active_project,
                    "data": current_project_data
                }
                json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📥 匯出完整專案 (JSON)",
                    data=json_data,
                    file_name=f"{active_project['name']}_backup_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )

                if history_records:
                    all_records_output = BytesIO()
                    with pd.ExcelWriter(all_records_output, engine="openpyxl") as writer:
                        for idx, record in enumerate(history_records):
                            sheet_name = f"{record.get('date', 'unknown')}_{idx}"[:31]
                            df = pd.DataFrame(record.get("rankings", []))
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                    all_records_output.seek(0)

                    st.download_button(
                        label="📥 匯出所有記錄 (Excel)",
                        data=all_records_output,
                        file_name=f"{active_project['name']}_all_records_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

        with col2:
            st.markdown("#### 🗑️ 清除數據")

            if st.button("🗑️ 清除所有記錄", type="secondary", use_container_width=True):
                st.session_state["confirm_clear_records"] = True

            if st.session_state.get("confirm_clear_records"):
                st.warning("⚠️ 確定要清除所有歷史記錄嗎？")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("確認清除", key="confirm_clear_yes"):
                        project_data = load_project_data(active_project["id"])
                        project_data["records"] = []
                        save_project_data(active_project["id"], project_data)
                        st.session_state.current_results = None
                        del st.session_state["confirm_clear_records"]
                        st.success("✅ 已清除所有記錄")
                        st.rerun()
                with col_no:
                    if st.button("取消", key="confirm_clear_no"):
                        del st.session_state["confirm_clear_records"]
                        st.rerun()

            if st.button("🗑️ 清除關鍵字組", type="secondary", use_container_width=True):
                st.session_state["confirm_clear_groups"] = True

            if st.session_state.get("confirm_clear_groups"):
                st.warning("⚠️ 確定要清除所有關鍵字組嗎？")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("確認清除", key="confirm_clear_groups_yes"):
                        project_data = load_project_data(active_project["id"])
                        project_data["keyword_groups"] = {}
                        save_project_data(active_project["id"], project_data)
                        del st.session_state["confirm_clear_groups"]
                        st.success("✅ 已清除所有關鍵字組")
                        st.rerun()
                with col_no:
                    if st.button("取消", key="confirm_clear_groups_no"):
                        del st.session_state["confirm_clear_groups"]
                        st.rerun()

        st.markdown("---")

        st.markdown("#### 📊 專案資訊")

        st.markdown(f"""
        | 項目 | 內容 |
        |------|------|
        | 專案名稱 | {active_project['name']} |
        | 行業 | {active_project['industry']} |
        | 創建時間 | {active_project.get('created', 'N/A')[:10]} |
        | 最後更新 | {active_project.get('updated', 'N/A')[:10]} |
        | 我的網站 | {', '.join(active_project.get('my_sites', [])) or '未設定'} |
        | 競爭對手 | {', '.join(active_project.get('competitors', [])) or '未設定'} |
        """)

# ============ 頁尾 ============

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>🚀 SEO 排名追蹤工具 Pro v3.0</p>
    <p style="font-size: 0.8rem;">多專案管理 · 智能分析 · 競爭對手追蹤</p>
</div>
""", unsafe_allow_html=True)
