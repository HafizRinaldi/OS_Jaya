import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from dotenv import load_dotenv
import os
import json
from datetime import datetime, timedelta, timezone
import urllib.parse
import pydeck as pdk  # untuk peta interaktif pin GPS

# ============================================================
#  CONFIG & UTIL
# ============================================================

st.set_page_config(
    page_title="Mitratel Monitoring Dashboard",
    layout="wide",
    page_icon="📡",
)

def now_wib() -> datetime:
    """Waktu sekarang dalam zona WIB (UTC+7)."""
    return datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=7))
    )

def format_duration(delta: timedelta) -> str:
    """Format timedelta jadi string 'X jam Y menit Z detik'."""
    total_seconds = int(delta.total_seconds())
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if hours:
        parts.append(f"{hours} jam")
    if minutes:
        parts.append(f"{minutes} menit")
    if seconds or not parts:
        parts.append(f"{seconds} detik")

    return " ".join(parts)

# Load credential dari secrets atau .env
load_dotenv()
USERNAME_1 = os.getenv("LOGIN_USERNAME_1")
PASSWORD_1 = os.getenv("LOGIN_PASSWORD_1")
USERNAME = os.getenv("LOGIN_USERNAME")
PASSWORD = os.getenv("LOGIN_PASSWORD")

# ============================================================
#  THEME / WARNA MITRATEL (MERAH PUTIH)
# ============================================================

PRIMARY_RED = "#E30613"   # Merah Mitratel
SECONDARY_RED = "#B00011" # Merah tua (aksen)
DARK_GREY = "#232323"
LIGHT_BG = "#FFF5F5"      # Putih dengan sedikit merah muda
BLUE_SKY = "#2B74C8"
GREEN_NORMAL = "#4CAF50"

# ICON PIN UNTUK MAP
RED_PIN_URL = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png"
GREEN_PIN_URL = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png"

# CSS global
st.markdown(
    f"""
    <style>
    .main {{
        background: linear-gradient(180deg, #FFFFFF, {LIGHT_BG});
    }}

    /* Sidebar merah gradasi */
    [data-testid="stSidebar"] > div {{
        background: linear-gradient(
            180deg,
            rgba(227, 6, 19, 0.95),
            rgba(176, 0, 17, 0.9)
        );
        color: white;
    }}

    /* Semua teks di sidebar jadi putih */
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}

    .big-title {{
        font-size: 30px;
        font-weight: 700;
        color: {DARK_GREY};
        margin-bottom: 0px;
    }}
    .sub-title {{
        font-size: 14px;
        color: #555555;
    }}
    .section-title {{
        font-size: 18px;
        font-weight: 700;
        margin-top: 10px;
        color: {DARK_GREY};
    }}
    .mit-card {{
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        margin-bottom: 16px;
        border: 1px solid rgba(227,6,19,0.07);
    }}
    .footer-text {{
        font-size: 11px;
        color: #777777;
        text-align: center;
        margin-top: 24px;
    }}

    .sidebar-logo {{
        text-align: center;
        margin-bottom: 10px;
        padding: 8px 4px 0 4px;
    }}
    .sidebar-logo img {{
        max-width: 170px;
    }}
    .sidebar-bottom {{
        text-align: left;
        font-size: 11px;
        color: rgba(255,255,255,0.9);
        margin-top: 12px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
#  HEADER (TENGAH ATAS)
# ============================================================

header_col1, header_col2 = st.columns([3, 2])

with header_col1:
    st.markdown(
        '<div class="big-title">Mitratel Monitoring Dashboard</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">'
        'Tower Online/Offline & Site Inspection Status (SISS) • '
        'Data internal, waktu WIB'
        '</div>',
        unsafe_allow_html=True,
    )

with header_col2:
    # Foto tower opsional
    try:
        st.image("tower-header.jpg", width="stretch")
    except Exception:
        pass

st.write("")

# ============================================================
#  SIDEBAR (LOGO > MENU > FILTER > TANGGAL > PENJELASAN > COPYRIGHT)
# ============================================================

# default nilai range tanggal SISS
siss_start_date = None
siss_end_date = None

with st.sidebar:

    # 1. Logo atas
    st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
    try:
        st.image("mitratel-removebg-preview.png", width="content")
    except Exception:
        st.write("")
    st.markdown('</div>', unsafe_allow_html=True)

    # 2. Menu halaman
    st.title("📂 Menu")
    page = st.radio(
        "Pilih halaman:",
        ["Tower Online / Offline", "SISS Site Status"],
        key="menu_page"
    )

    st.markdown("---")

    # 3. Filter status (tower / SISS)
    st.subheader("Filter Status")
    if page == "Tower Online / Offline":
        status_filter_label = st.radio(
            "Status tower:",
            ["Semua", "Offline saja", "Online saja"],
            key="filter_tower"
        )
    else:
        status_filter_label = st.radio(
            "Status site:",
            ["Semua", "NORMAL saja", "CRITICAL saja"],
            key="filter_siss"
        )

        # 3b. Range tanggal untuk SISS (dari – sampai)
        today = now_wib().date()
        default_start = today - timedelta(days=7)  # default 7 hari ke belakang
        siss_start_date = st.date_input(
            "Tanggal awal (WIB)", value=default_start, key="siss_start_date"
        )
        siss_end_date = st.date_input(
            "Tanggal akhir (WIB)", value=today, key="siss_end_date"
        )

    st.markdown("---")

    # 4. Penjelasan singkat
    st.markdown(
        """
        ### Mitratel Monitoring Dashboard

        Dashboard internal untuk memantau:

        • Status **tower online/offline**  
        • Status **SISS (NORMAL & CRITICAL)**  

        Catatan: **CRITICAL = status NOT INSTALLED pada sistem SISS**.  

        Waktu ditampilkan dalam zona **WIB**.
        """
    )

    st.markdown("---")

    # 5. Copyright
    st.markdown(
        """
        <div class="sidebar-bottom">
            © 2025 PT Dayamitra Telekomunikasi Tbk (Mitratel)<br>
            Internal Use Only
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
#  COMMON: DOWNLOAD EXCEL
# ============================================================

def download_excel(df: pd.DataFrame, filename: str, label: str, key: str):
    buf = BytesIO()
    df.to_excel(buf, index=False)
    st.download_button(
        label=label,
        data=buf.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )

# ============================================================
#  BAGIAN 1 — TOWER ONLINE / OFFLINE
# ============================================================

LOGIN_URL_REPORT = "https://maiviewmitratel.id/Auth/login"
REPORT_URL_REPORT = "https://maiviewmitratel.id/get-report"

def fetch_report_html() -> str:
    if not USERNAME or not PASSWORD:
        raise RuntimeError(
            "USERNAME/PASSWORD tidak ditemukan (LOGIN_USERNAME / LOGIN_PASSWORD)."
        )

    session = requests.Session()
    login_data = {"username": USERNAME, "password": PASSWORD}

    login_response = session.post(LOGIN_URL_REPORT, data=login_data)
    if login_response.status_code != 200 or "login" in login_response.url.lower():
        raise RuntimeError("Login gagal ke server report tower.")

    report_response = session.get(REPORT_URL_REPORT)
    if report_response.status_code != 200:
        raise RuntimeError("Gagal mengambil halaman report tower.")

    return report_response.text


def parse_report_to_df(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("Tidak ada tabel di halaman report tower.")

    table = tables[0]
    thead = table.find("thead")
    tbody = table.find("tbody")

    if thead is None or tbody is None:
        raise RuntimeError("thead/tbody tidak ditemukan pada tabel tower.")

    headers = [th.text.strip() for th in thead.find_all("th")]
    rows = [
        [td.text.strip() for td in tr.find_all("td")]
        for tr in tbody.find_all("tr")
    ]

    df = pd.DataFrame(rows, columns=headers)
    if "#" in df.columns:
        df = df.drop(columns=["#"])

    return df


def filter_by_status_tower(df: pd.DataFrame, status: str | None) -> pd.DataFrame:
    if status is None or "Status" not in df.columns:
        return df
    return df[df["Status"] == status].copy()

# Fungsi lama (tidak dipakai lagi)
def tower_sidebar_filters() -> str | None:
    with st.sidebar:
        st.markdown("### Filter Tower")
        pilihan = st.radio(
            "Status tower:",
            ["Semua", "Offline saja", "Online saja"],
            key="radio_tower",
        )
    if pilihan == "Semua":
        return None
    elif pilihan == "Offline saja":
        return "Offline"
    else:
        return "Online"

# ============================================================
#  BAGIAN 2 — SISS SITE STATUS
# ============================================================

LOGIN_URL_SISS = "https://siss-service.smartsol.id/Auth/login"
REPORT_URL_SISS_BASE = (
    "https://siss-service.smartsol.id/"
    "v1/panels/59b7e0f9-2f83-45cb-bde4-a6f4d890022c/panelData"
)

def build_siss_url(start_dt: datetime, end_dt: datetime) -> str:
    """Bangun URL SISS dengan range waktu (WIB) yang diinginkan."""
    # Pastikan sudah ada timezone
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone(timedelta(hours=7)))
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone(timedelta(hours=7)))

    def to_ms(dt: datetime) -> int:
        # timestamp dalam milidetik
        return int(dt.timestamp() * 1000)

    payload = {
        "beginTs": to_ms(start_dt),
        "endTs": to_ms(end_dt),
    }
    encoded = urllib.parse.quote(json.dumps(payload))
    return f"{REPORT_URL_SISS_BASE}?&requestOnDemand={encoded}"

def extract_auth_token(login_response) -> str | None:
    """Cari field yang mengandung kata 'token' di JSON hasil login."""
    try:
        data = login_response.json()
    except Exception:
        return None

    if not isinstance(data, (dict, list)):
        return None

    stack = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(v, (dict, list)):
                    stack.append(v)
                elif isinstance(v, str) and "token" in k.lower():
                    return v
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return None


def fetch_siss_raw(start_dt: datetime, end_dt: datetime) -> str:
    if not USERNAME_1 or not PASSWORD_1:
        raise RuntimeError(
            "USERNAME_1/PASSWORD_1 tidak ditemukan (LOGIN_USERNAME_1 / LOGIN_PASSWORD_1)."
        )

    # Bangun URL dengan range waktu
    report_url = build_siss_url(start_dt, end_dt)

    session = requests.Session()

    common_headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": "https://mitratel-siss.smartsol.id",
        "Referer": "https://mitratel-siss.smartsol.id/",
    }

    # LOGIN
    login_data = {"username": USERNAME_1, "password": PASSWORD_1}
    login_headers = {**common_headers, "Content-Type": "application/json"}

    login_response = session.post(
        LOGIN_URL_SISS,
        json=login_data,
        headers=login_headers,
    )
    if login_response.status_code != 200:
        raise RuntimeError(
            f"Login gagal ke SISS (status {login_response.status_code})."
        )

    auth_token = extract_auth_token(login_response)

    base_report_headers = {**common_headers, "Accept": "application/json"}

    attempts = []
    if auth_token:
        bearer = auth_token if auth_token.lower().startswith("bearer ") else f"Bearer {auth_token}"
        attempts.append({"Authorization": bearer})
        attempts.append({"Authorization": auth_token})
    attempts.append({})  # fallback tanpa Authorization

    last_status = None
    last_text = None
    for extra in attempts:
        headers = {**base_report_headers, **extra}
        resp = session.get(report_url, headers=headers)
        last_status = resp.status_code
        last_text = resp.text
        if resp.status_code == 200:
            return resp.text

    snippet = (last_text or "")[:200]
    raise RuntimeError(
        f"Gagal mengambil data SISS (status {last_status}). "
        f"Cuplikan response: {snippet}"
    )


def parse_siss_to_df(raw_text: str) -> pd.DataFrame:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        raise RuntimeError("Respon SISS bukan JSON valid.")

    if not isinstance(data, dict) or "responseDataValue" not in data:
        raise RuntimeError("Field 'responseDataValue' tidak ditemukan di JSON SISS.")

    items = data["responseDataValue"]
    if not isinstance(items, list):
        raise RuntimeError("'responseDataValue' bukan list.")

    df = pd.DataFrame(items)

    rename_map = {}
    if "name" in df.columns:
        rename_map["name"] = "Site Name"
    if "region" in df.columns:
        rename_map["region"] = "Region"
    if "status" in df.columns:
        rename_map["status"] = "Status"
    df = df.rename(columns=rename_map)

    # Filter hanya NORMAL & NOT INSTALLED dari sistem,
    # lalu tampilkan NOT INSTALLED sebagai CRITICAL di dashboard
        # Filter status yang relevan dari sistem,
    # dan satukan NOT INSTALLED / CRITICAL jadi "CRITICAL" di dashboard
    if "Status" in df.columns:
        valid_status = ["NORMAL", "NOT INSTALLED", "CRITICAL"]
        df = df[df["Status"].isin(valid_status)].copy()
        df["Status"] = df["Status"].replace(
            {
                "NOT INSTALLED": "CRITICAL",
                "Critical": "CRITICAL",      # kalau ada variasi huruf besar/kecil
                "critical": "CRITICAL",
            }
        )

    cols = [
        c
        for c in ["Site Name", "Region", "Status", "longitude", "latitude", "tenantId"]
        if c in df.columns
    ]
    if cols:
        df = df[cols]

    return df


def filter_by_status_siss(df: pd.DataFrame, status: str | None) -> pd.DataFrame:
    if status is None or "Status" not in df.columns:
        return df
    return df[df["Status"] == status].copy()

def update_siss_status_history(df_new: pd.DataFrame):
    """
    Merekam perubahan status per site:
    - Simpan kapan status NORMAL/CRITICAL mulai
    - Jika terjadi perubahan, hitung durasi status sebelumnya
      dan simpan ke log riwayat.
    """
    if "Site Name" not in df_new.columns or "Status" not in df_new.columns:
        return

    now = now_wib()

    # mapping status terbaru per site
    new_map = {
        row["Site Name"]: row["Status"]
        for _, row in df_new.iterrows()
        if pd.notna(row.get("Site Name")) and pd.notna(row.get("Status"))
    }

    # state sebelumnya di session
    prev_state = st.session_state.get("siss_status_state", {})
    status_log = st.session_state.get("siss_status_log", [])

    for site_name, new_status in new_map.items():
        prev_info = prev_state.get(site_name)

        if prev_info is None:
            # pertama kali terlihat di sesi ini
            prev_state[site_name] = {
                "status": new_status,
                "since": now,
            }
            continue

        prev_status = prev_info["status"]
        prev_since = prev_info["since"]

        # Kalau status berubah -> catat periode lama
        if prev_status != new_status:
            duration = now - prev_since

            log_entry = {
                "Site Name": site_name,
                "From Status": prev_status,
                "To Status": new_status,
                "Start Time (WIB)": prev_since.strftime("%Y-%m-%d %H:%M:%S"),
                "End Time (WIB)": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Duration": format_duration(duration),
            }
            status_log.append(log_entry)

            # update status baru dan waktu mulai status baru
            prev_state[site_name] = {
                "status": new_status,
                "since": now,
            }

    # simpan kembali ke session_state
    st.session_state["siss_status_state"] = prev_state
    st.session_state["siss_status_log"] = status_log

# Fungsi lama (tidak dipakai lagi)
def siss_sidebar_filters() -> str | None:
    with st.sidebar:
        st.markdown("### Filter SISS")
        pilihan = st.radio(
            "Status site:",
            ["Semua (NORMAL + CRITICAL)", "NORMAL saja", "CRITICAL saja"],
            key="radio_siss",
        )
    if pilihan == "Semua (NORMAL + CRITICAL)":
        return None
    elif pilihan == "NORMAL saja":
        return "NORMAL"
    else:
        return "CRITICAL"

# ============================================================
#  HALAMAN TOWER
# ============================================================

def page_tower(status_filter: str | None):
    st.markdown('<div class="section-title">📡 Tower Online / Offline</div>', unsafe_allow_html=True)
    st.caption("Data tower online/offline dari web report internal (otomatis login).")

    banner_container = st.container()

    refresh_clicked = st.button("🔄 Refresh Tower dari Web", type="primary", key="btn_tower")

    if refresh_clicked:
        try:
            with st.spinner("Sedang login & mengambil report tower..."):
                html = fetch_report_html()
                df_report = parse_report_to_df(html)

            st.session_state["df_tower"] = df_report
            st.session_state["last_update_tower"] = now_wib()
            st.success("Data tower berhasil diambil.")
        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}")

    with banner_container:
        last_update = st.session_state.get("last_update_tower")
        info_waktu = last_update.strftime("%Y-%m-%d %H:%M:%S") if last_update else "-"
        banner_html = f"""
<div style="
    background: linear-gradient(90deg,{PRIMARY_RED},#FF6B6B);
    padding: 16px 20px;
    border-radius: 16px;
    color: white;
    margin-top: 8px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
">
  <div style="
      background: white;
      color: {PRIMARY_RED};
      width: 40px;
      height: 40px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      font-weight: bold;
  ">
    📶
  </div>
  <div style="flex: 1;">
    <div style="font-size: 16px; font-weight: 700; margin-bottom: 2px;">
      Status Tower Online / Offline
    </div>
    <div style="font-size: 13px;">
      Update terakhir: {info_waktu} (WIB). Klik tombol <b>Refresh Tower</b> untuk mengambil data terbaru.
    </div>
  </div>
</div>
"""
        st.markdown(banner_html, unsafe_allow_html=True)

    if "df_tower" in st.session_state:
        df = st.session_state["df_tower"]
        df_filtered = filter_by_status_tower(df, status_filter)

        last_update = st.session_state.get("last_update_tower")
        timestamp = (
            last_update.strftime("%Y-%m-%d_%H-%M-%S")
            if last_update
            else now_wib().strftime("%Y-%m-%d_%H-%M-%S")
        )

        st.markdown("### 💾 Export / Download")
        col1, col2 = st.columns(2)

        with col1:
            download_excel(
                df,
                f"tower_semua_{timestamp}.xlsx",
                "Download Semua Data Tower",
                key="dl_tower_all",
            )

        if status_filter is None:
            export_label = "Download Data (Semua)"
            export_filename = f"tower_semua_{timestamp}.xlsx"
        elif status_filter == "Offline":
            export_label = "Download Data Offline"
            export_filename = f"tower_offline_{timestamp}.xlsx"
        else:
            export_label = "Download Data Online"
            export_filename = f"tower_online_{timestamp}.xlsx"

        with col2:
            download_excel(
                df_filtered,
                export_filename,
                export_label,
                key="dl_tower_filtered",
            )

        st.write("---")

        st.subheader("📄 Data Tower (Semua)")
        st.dataframe(df, width="stretch", height=350)

        if status_filter is None:
            title = "Data Tower Offline & Online"
        elif status_filter == "Offline":
            title = "Data Tower OFFLINE"
        else:
            title = "Data Tower ONLINE"

        st.subheader(f"🔍 {title}")
        st.dataframe(df_filtered, width="stretch", height=350)

        # Grafik jumlah tower per status
        st.subheader("📈 Grafik Jumlah Tower per Status")
        if "Status" in df.columns:
            counts = df["Status"].value_counts().reset_index()
            counts.columns = ["Status", "Jumlah Tower"]
            st.dataframe(counts, width="stretch")
            st.bar_chart(counts.set_index("Status")["Jumlah Tower"])
        else:
            st.info("Kolom 'Status' tidak ditemukan, grafik tidak bisa dibuat.")

    else:
        st.info("Belum ada data tower. Klik tombol **🔄 Refresh Tower dari Web** terlebih dahulu.")

# ============================================================
#  HALAMAN SISS
# ============================================================

def page_siss(status_filter: str | None, start_date, end_date):
    st.markdown('<div class="section-title">🛰️ SISS Site Status</div>', unsafe_allow_html=True)
    st.caption("Data Site List dari SISS (status NORMAL & CRITICAL, dengan range tanggal yang dipilih).")

    # Pastikan ada tanggal (fallback ke hari ini kalau None)
    if start_date is None or end_date is None:
        today = now_wib().date()
        start_date = today
        end_date = today

    # Kalau user kebalik (end < start), kita tukar
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    # Konversi ke datetime WIB untuk beginTs & endTs
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone(timedelta(hours=7)))
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone(timedelta(hours=7)))

    range_str = f"{start_date.strftime('%Y-%m-%d')} s.d. {end_date.strftime('%Y-%m-%d')}"

    banner_container = st.container()

    refresh_clicked = st.button("🔄 Refresh Data SISS", type="primary", key="btn_siss")

    if refresh_clicked:
        try:
            with st.spinner("Sedang login & mengambil data SISS..."):
                raw = fetch_siss_raw(start_dt, end_dt)
                df_report = parse_siss_to_df(raw)

            # 🔹 Update riwayat status (ON/OFF + durasi)
            update_siss_status_history(df_report)

            st.session_state["df_siss"] = df_report
            st.session_state["last_update_siss"] = now_wib()
            st.success("Data SISS berhasil diambil.")
        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}")

    with banner_container:
        last_update = st.session_state.get("last_update_siss")
        info_waktu = last_update.strftime("%Y-%m-%d %H:%M:%S") if last_update else "-"
        banner_html = f"""
<div style="
    background: linear-gradient(90deg,{PRIMARY_RED},#FF8A65);
    padding: 16px 20px;
    border-radius: 16px;
    color: white;
    margin-top: 8px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
">
  <div style="
      background: white;
      color: {PRIMARY_RED};
      width: 40px;
      height: 40px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      font-weight: bold;
  ">
    📍
  </div>
  <div style="flex: 1;">
    <div style="font-size: 16px; font-weight: 700; margin-bottom: 2px;">
      Status Site SISS (NORMAL & CRITICAL)
    </div>
    <div style="font-size: 13px;">
      Range data: {range_str} (WIB).<br>
      Update terakhir: {info_waktu} (WIB). Klik tombol <b>Refresh Data SISS</b> untuk mengambil data sesuai range di sidebar.
    </div>
  </div>
</div>
"""
        st.markdown(banner_html, unsafe_allow_html=True)

    if "df_siss" in st.session_state:
        df = st.session_state["df_siss"]
        df_filtered = filter_by_status_siss(df, status_filter)

        # ==== PETA INTERAKTIF DENGAN PIN GPS (DI ATAS TABEL) ====
        st.subheader("🗺️ Peta Lokasi Site (Pin GPS – CRITICAL = MERAH)")
        if {"latitude", "longitude", "Status"}.issubset(df_filtered.columns):
            df_map = df_filtered.dropna(subset=["latitude", "longitude"]).copy()
            df_map["lat"] = df_map["latitude"].astype(float)
            df_map["lon"] = df_map["longitude"].astype(float)

            # Icon URL: merah untuk CRITICAL, hijau untuk NORMAL
            df_map["icon_url"] = df_map["Status"].apply(
                lambda x: RED_PIN_URL if x == "CRITICAL" else GREEN_PIN_URL
            )

            df_map["icon_data"] = df_map.apply(
                lambda row: {
                    "url": row["icon_url"],
                    "width": 128,
                    "height": 128,
                    "anchorY": 128,
                    "anchorX": 64,
                },
                axis=1,
            )

            view_state = pdk.ViewState(
                latitude=df_map["lat"].mean(),
                longitude=df_map["lon"].mean(),
                zoom=6,
                pitch=0,
            )

            icon_layer = pdk.Layer(
                "IconLayer",
                data=df_map,
                get_icon="icon_data",
                get_position=["lon", "lat"],
                get_size=35,
                pickable=True,
            )

            # Tooltip simple: muncul saat hover/klik pin
            tooltip = {
                "html": "<b>Site:</b> {Site Name}<br><b>Status:</b> {Status}",
                "style": {"color": "white"}
            }

            st.pydeck_chart(
                pdk.Deck(
                    layers=[icon_layer],
                    initial_view_state=view_state,
                    tooltip=tooltip,
                )
            )

            st.markdown(
                "🟢 <b>NORMAL</b> &nbsp;&nbsp; 🔴 <b>CRITICAL</b>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Kolom latitude/longitude/Status tidak lengkap, peta tidak bisa ditampilkan.")

        # =================================================
        # Download, tabel & grafik seperti biasa
        # =================================================

        last_update = st.session_state.get("last_update_siss")
        timestamp = (
            last_update.strftime("%Y-%m-%d_%H-%M-%S")
            if last_update
            else now_wib().strftime("%Y-%m-%d_%H-%M-%S")
        )

        st.markdown("### 💾 Export / Download")
        col1, col2 = st.columns(2)

        with col1:
            download_excel(
                df,
                f"siss_semua_{timestamp}.xlsx",
                "Download Semua Data SISS",
                key="dl_siss_all",
            )

        if status_filter is None:
            export_label = "Download Data (Semua)"
            export_filename = f"siss_semua_{timestamp}.xlsx"
        elif status_filter == "NORMAL":
            export_label = "Download Data NORMAL"
            export_filename = f"siss_normal_{timestamp}.xlsx"
        else:
            export_label = "Download Data CRITICAL"
            export_filename = f"siss_critical_{timestamp}.xlsx"

        with col2:
            download_excel(
                df_filtered,
                export_filename,
                export_label,
                key="dl_siss_filtered",
            )

        st.write("---")

        st.subheader("📄 Data Site SISS (NORMAL & CRITICAL)")
        st.dataframe(df, width="stretch", height=350)

        if status_filter is None:
            title = "Semua Status (NORMAL + CRITICAL)"
        elif status_filter == "NORMAL":
            title = "Status NORMAL"
        else:
            title = "Status CRITICAL"

        st.subheader(f"🔍 {title}")
        st.dataframe(df_filtered, width="stretch", height=350)

        # Grafik jumlah site per status
        st.subheader("📈 Grafik Jumlah Site per Status")
        if "Status" in df.columns:
            counts = df["Status"].value_counts().reset_index()
            counts.columns = ["Status", "Jumlah Site"]
            st.dataframe(counts, width="stretch")
            st.bar_chart(counts.set_index("Status")["Jumlah Site"])
        else:
            st.info("Kolom 'Status' tidak ditemukan, grafik tidak bisa dibuat.")

        # =================================================
        # RIWAYAT PERUBAHAN STATUS (ON/OFF + DURASI)
        # =================================================
        st.subheader("⏱️ Riwayat Perubahan Status (NORMAL ↔ CRITICAL)")

        status_log = st.session_state.get("siss_status_log", [])

        if status_log:
            log_df = pd.DataFrame(status_log)
            st.dataframe(log_df, width="stretch", height=250)

            download_excel(
                log_df,
                f"riwayat_status_siss_{timestamp}.xlsx",
                "Download Riwayat Status NORMAL/CRITICAL",
                key="dl_siss_history",
            )
        else:
            st.info("Belum ada perubahan status yang terekam pada sesi ini.")
    else:
        st.info("Belum ada data SISS. Klik tombol **🔄 Refresh Data SISS** terlebih dahulu.")

# ============================================================
#  ROUTING HALAMAN (PAKAI FILTER DARI SIDEBAR UTAMA)
# ============================================================

if page == "Tower Online / Offline":
    if status_filter_label == "Semua":
        sf = None
    elif status_filter_label == "Offline saja":
        sf = "Offline"
    else:
        sf = "Online"
    page_tower(sf)
else:
    if status_filter_label == "Semua":
        sf = None
    elif status_filter_label == "NORMAL saja":
        sf = "NORMAL"
    else:
        sf = "CRITICAL"
    page_siss(sf, siss_start_date, siss_end_date)

# Footer di bawah konten utama (tengah)
st.markdown(
    '<div class="footer-text">'
    '© 2025 – Tim Operation Support (Planning Operation), Mitratel'
    '</div>',
    unsafe_allow_html=True,
)
