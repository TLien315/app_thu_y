import pymysql
import ssl
import bcrypt
import numpy as np
import cv2
from PIL import Image
import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime

# CẤU HÌNH GIAO DIỆN NÂNG CAO
hide_st_style = """
<style>
    /* Ẩn chữ Made with Streamlit ở dưới cùng */
    footer {visibility: hidden !important;}
    
    /* Ẩn thanh menu Hamburger và nút Deploy ở góc phải */
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* Ẩn đường viền màu trên cùng */
    div[data-testid="stDecoration"] {visibility: hidden !important;}
    
    /* ÉP BUỘC NÚT MỞ SIDEBAR PHẢI HIỆN RA */
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        display: flex !important;
        z-index: 999999 !important;
    }
    
    /* Đảm bảo phần đầu trang không bị ẩn toàn bộ */
    header {
        visibility: visible !important;
        background: transparent !important;
    }
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# CẤU HÌNH GIAO DIỆN HIỆN ĐẠI (BRIGHTER MODERN UI)
# ==========================================
st.set_page_config(
    page_title="PetCare Smart Clinic System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# GỘP TẤT CẢ CSS VÀO MỘT KHỐI DUY NHẤT ĐỂ TRÁNH LỖI CÚ PHÁP
st.markdown("""
    <style>
    /* Tổng thể ứng dụng */
    .stApp {
        background-color: #f8f9fa;
    }
    /* Style cho Sidebar - ĐÃ SỬA CHỖ NÀY */
    [data-testid="stSidebar"] img {
        max-width: 450px !important; 
        margin: 0 auto !important;
        display: block !important;
    }
    /* Nút bấm */
    div.stButton > button:first-child {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:first-child:hover {
        background-color: #0056b3;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    /* Các khối hiển thị */
    .feature-box {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)
# ==========================================
# 1. THIẾT LẬP CƠ SỞ DỮ LIỆU CHUẨN QUAN HỆ (MySQL)
# ==========================================

def get_db_connection():
    try:
        return pymysql.connect(
            host=st.secrets["DB_HOST"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASS"],
            database=st.secrets["DB_NAME"],
            port=int(st.secrets["DB_PORT"]),
            connect_timeout=10, # QUAN TRỌNG: Giới hạn thời gian đợi 10 giây
            autocommit=True,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            ssl={'ssl': {'cert_reqs': ssl.CERT_NONE}} # Cấu hình SSL
        )
    except Exception as e:
        st.error(f"Lỗi kết nối DB: {e}")
        return None

def update_pet_features(pet_id, features_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE pets SET image_features = %s WHERE id = %s",
        (features_data, pet_id)
    )
    cursor.close()
    conn.close()

@st.cache_resource
def init_db():
    try:
        conn = get_db_connection()
        if conn is None: return 
        cursor = conn.cursor()
        
        # Tạo bảng Users
        cursor.execute("CREATE TABLE IF NOT EXISTS users (username VARCHAR(50) PRIMARY KEY, password TEXT NOT NULL, full_name VARCHAR(100) NOT NULL, phone VARCHAR(20) NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
        # Tạo bảng Pets
        cursor.execute("CREATE TABLE IF NOT EXISTS pets (id INT AUTO_INCREMENT PRIMARY KEY, owner_username VARCHAR(50) NOT NULL, name VARCHAR(100) NOT NULL, species VARCHAR(50) NOT NULL, age INT NOT NULL, weight FLOAT NOT NULL, image_features LONGTEXT NULL, FOREIGN KEY (owner_username) REFERENCES users(username) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
        # Tạo bảng Appointments
        cursor.execute("CREATE TABLE IF NOT EXISTS appointments (id INT AUTO_INCREMENT PRIMARY KEY, pet_id INT NOT NULL, date VARCHAR(20) NOT NULL, reason TEXT NOT NULL, status VARCHAR(50) DEFAULT 'Chờ xác nhận', doctor_notes TEXT NULL, fee FLOAT NULL, FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
        
        # Khởi tạo Admin
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            hashed_admin_pw = bcrypt.hashpw("123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("INSERT INTO users (username, password, full_name) VALUES (%s, %s, %s)", ("admin", hashed_admin_pw, "Bác Sĩ Trưởng Khoa"))
            
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"🚨 LỖI KHỞI TẠO: {e}")
        st.stop()

# Gọi hàm khởi tạo ngay khi ứng dụng chạy
init_db()

# --- HÀM XỬ LÝ NGHIỆP VỤ DATABASE ---

def register_user(username, password, full_name, phone):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(
            "INSERT INTO users (username, password, full_name, phone) VALUES (%s, %s, %s, %s)",
            (username, hashed_pw, full_name, phone)
        )
        cursor.close()
        conn.close()
        return True
    except pymysql.err.IntegrityError:
        return False

def check_user_login(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password, full_name FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        if bcrypt.checkpw(password.encode('utf-8'), row['password'].encode('utf-8')):
            return row['full_name']
    return None

def change_user_password(username, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_pw, username))
    cursor.close()
    conn.close()

def add_pet_to_db(owner_username, name, species, age, weight):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pets (owner_username, name, species, age, weight) VALUES (%s, %s, %s, %s, %s)",
        (owner_username, name, species, age, weight)
    )
    cursor.close()
    conn.close()

def add_appointment_to_db(pet_id, date, reason):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO appointments (pet_id, date, reason) VALUES (%s, %s, %s)",
        (int(pet_id), date, reason)
    )
    cursor.close()
    conn.close()

def update_appointment_status(app_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = %s WHERE id = %s", (new_status, app_id))
    cursor.close()
    conn.close()

def update_appointment_notes(app_id, notes):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET doctor_notes = %s WHERE id = %s", (notes, app_id))
    cursor.close()
    conn.close()

def update_appointment_fee(app_id, fee):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET fee = %s WHERE id = %s", (fee, app_id))
    cursor.close()
    conn.close()

def delete_appointment(app_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE id = %s", (app_id,))
    cursor.close()
    conn.close()

def get_all_data(table_name):
    if table_name not in ["users", "pets", "appointments"]:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    result = []
    for r in rows:
        if table_name == "users":
            result.append((r['username'], r['password'], r['full_name'], r.get('phone') or ""))
        elif table_name == "pets":
            result.append((r['id'], r['owner_username'], r['name'], r['species'], r['age'], r['weight'], r.get('image_features') or ""))
        elif table_name == "appointments":
            result.append((r['id'], r['pet_id'], r['date'], r['reason'], r['status'], r.get('doctor_notes') or "", r.get('fee') or 0))
    return result


def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name, phone FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


# Khởi động Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "current_name" not in st.session_state:
    st.session_state.current_name = None

# GỌI KHỞI TẠO MỘT LẦN DUY NHẤT
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# ==========================================
# MÀN HÌNH CHƯA ĐĂNG NHẬP: ĐĂNG KÝ / ĐĂNG NHẬP
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #007bff; margin-top: 30px;'>🏥 HỆ THỐNG THÚ Y PETCARE</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6c757d;'>Vui lòng Đăng ký / Đăng nhập để sử dụng ứng dụng</p>", unsafe_allow_html=True)
    
    col_login_space, col_login_box, _ = st.columns([1, 1.8, 1])
    
    with col_login_box:
        st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
        login_role = st.selectbox("📍 BẠN TRUY CẬP VỚI TƯ CÁCH THÀNH VIÊN NÀO?", ["👤 Khách Hàng (Pet Owner)", "🩺 Bác Sĩ Thú Y / Quản Trị"])
        
        if login_role == "🩺 Bác Sĩ Thú Y / Quản Trị":
            st.markdown("#### ĐĂNG NHẬP BÁC SĨ / ADMIN")
            password = st.text_input("🔑 Nhập mật khẩu quản trị viên:", type="password")
            if st.button("Đăng Nhập Vai Trò Bác Sĩ"):
                name_found = check_user_login("admin", password)
                if name_found:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Bác Sĩ"
                    st.session_state.current_user = "admin"
                    st.session_state.current_name = name_found
                    st.rerun()
                else:
                    st.error("Mật khẩu Admin không chính xác!")
        else:
            tab_login, tab_register = st.tabs(["🔐 Đăng Nhập Khách Hàng", "📝 Đăng Ký Tài Khoản Mới"])
            
            with tab_login:
                c_user = st.text_input("Tên đăng nhập (Username):", key="log_user")
                c_pass = st.text_input("Mật khẩu:", type="password", key="log_pass")
                if st.button("Đăng Nhập"):
                    if c_user and c_pass:
                        name_found = check_user_login(c_user, c_pass)
                        if name_found:
                            st.session_state.logged_in = True
                            st.session_state.user_role = "Khách Hàng"
                            st.session_state.current_user = c_user
                            st.session_state.current_name = name_found
                            st.rerun()
                        else: st.error("Sai tên đăng nhập hoặc mật khẩu!")
                    else: st.warning("Vui lòng nhập đầy đủ thông tin!")
                    
            with tab_register:
                reg_name = st.text_input("Họ và tên của bạn:", placeholder="Ví dụ: Nguyễn Văn A")
                reg_phone = st.text_input("Số điện thoại liên hệ:", placeholder="Ví dụ: 0912345678")
                reg_user = st.text_input("Tạo tên đăng nhập (Username):", placeholder="Ví dụ: nguyenvana")
                reg_pass = st.text_input("Tạo mật khẩu:", type="password", placeholder="Tối thiểu 6 ký tự")
                if st.button("Xác Nhận Đăng Ký"):
                    if reg_name and reg_phone and reg_user and reg_pass:
                        success = register_user(reg_user, reg_pass, reg_name, reg_phone)
                        if success: st.success("🎉 Đăng ký tài khoản thành công! Mời bạn chuyển sang tab Đăng Nhập.")
                        else: st.error("Tên đăng nhập này đã tồn tại!")
                    else: st.warning("Vui lòng không để trống ô nào!")
                    
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()
# ==========================================
# 2. GIAO DIỆN THANH SIDEBAR SAU KHI ĐĂNG NHẬP
# ==========================================
with st.sidebar:
    # 1. Bỏ qua st.columns để logo có không gian tự do nhất
    # 2. Dùng use_container_width=True + CSS để ép nó to ra
    st.image("logo_petcare_clinic.png", use_container_width=True) 
    
    st.markdown("<h2 style='text-align: center; margin-top: -10px;'>PetCare Smart Clinic</h2>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.success(f"👤 Chào: **{st.session_state.current_name}**\n\n📌 Vai trò: **{st.session_state.user_role}**")
    
    if st.session_state.user_role == "Khách Hàng":
        with st.expander("🔑 Thay Đổi Mật Khẩu"):
            new_pass = st.text_input("Nhập mật khẩu mới:", type="password", key="new_p")
            if st.button("Cập Nhật Mật Khẩu"):
                if new_pass:
                    change_user_password(st.session_state.current_user, new_pass)
                    st.success("Đổi mật khẩu thành công!")
                else: st.error("Vui lòng điền mật khẩu mới!")

    st.markdown("---")
    if st.button("🚪 Đăng Xuất Ứng Dụng"):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.session_state.current_user = None
        st.session_state.current_name = None
        st.rerun()
        
    st.markdown("---")
    st.caption("⚡ @2026 Clinic Management System")


# ==========================================
# 3. ĐIỀU HƯỚNG VAI TRÒ CHỨC NĂNG
# ==========================================
if st.session_state.user_role == "Khách Hàng":
    st.markdown("<h1 style='color: #007bff; text-align: center;'>🏥 HỆ THỐNG QUẢN LÝ PHÒNG KHÁM THÚ Y TÍCH HỢP AI</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    left_col, right_col = st.columns([1.1, 1.0], gap="large")
    with left_col:
        st.markdown("### 📝 QUẢN LÝ THỦ TỤC & ĐẶT LỊCH")
        st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: #495057; margin-top:0;'>🐶 1. Đăng ký hồ sơ thú cưng</h4>", unsafe_allow_html=True)
        with st.form("form_pet", clear_on_submit=True):
            owner_name = st.session_state.current_name
            p_name = st.text_input("Tên thú cưng:", placeholder="Ví dụ: Bé Lu, Bé Gấu")
            species = st.selectbox("Loài thú cưng:", ["Chó", "Mèo", "Khác"])
            age = st.number_input("Tuổi (Theo tháng/năm):", min_value=1, value=1)
            weight = st.number_input("Cân nặng hiện tại (kg):", min_value=0.1, value=2.0)
            if st.form_submit_button("Lưu Hồ Sơ"):
                if p_name:
                    add_pet_to_db(st.session_state.current_user, p_name, species, age, weight)
                    st.session_state.pet_success_msg = f"🎉 Đã thêm bé {p_name} vào hệ thống thành công!"
                    st.rerun()
                else: st.error("Vui lòng điền tên thú cưng!")
        
        if "pet_success_msg" in st.session_state:
            st.success(st.session_state.pet_success_msg)
            del st.session_state.pet_success_msg
        
        st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: #495057; margin-top:0;'>📅 Đặt lịch khám bệnh</h4>", unsafe_allow_html=True)
        
        # 1. Lấy danh sách thú cưng thật từ DB
        all_pets = get_all_data("pets")
        my_pets = [p for p in all_pets if p[1] == st.session_state.current_user]
        
        pet_names = ["--- Chọn thú cưng ---"]
        pet_id_map = {}
        if my_pets:
            for p in my_pets:
                p_name_real = p[2]
                pet_names.append(p_name_real)
                pet_id_map[p_name_real] = p[0]

        # Khởi tạo giá trị lựa chọn mặc định trong bộ nhớ nếu chưa có
        if "selected_pet_temp" not in st.session_state:
            st.session_state.selected_pet_temp = "--- Chọn thú cưng ---"

        # ĐỒNG BỘ HÓA TRỰC TIẾP CHỨC NĂNG CHỌN VÀ NHẢY SỐ REAL-TIME QUA SELECTBOX
        selected_pet_name = st.selectbox(
            "Chọn thú cưng cần đặt lịch:",
            options=pet_names,
            index=pet_names.index(st.session_state.selected_pet_temp) if st.session_state.selected_pet_temp in pet_names else 0,
            key="pet_select_box"
        )
        st.session_state.selected_pet_temp = selected_pet_name
        
        # CHUYỂN Ô SỐ BÁO DANH SANG ENGINE RENDER HTML ĐỘNG ĐỂ KHÔNG BỊ KẸT BỘ NHỚ ĐỆM
        current_selection = st.session_state.selected_pet_temp
        if current_selection == "--- Chọn thú cưng ---":
            st.markdown("""
                <div style="background-color: #f1f3f5; padding: 10px; border-radius: 6px; border: 1px solid #ced4da; margin-bottom: 15px;">
                    <span style="color: #6c757d; font-size: 14px;">🔢 Số báo danh của bé (ID): <b>Chưa xác định</b></span>
                </div>
            """, unsafe_allow_html=True)
            target_pet_id = None
        else:
            target_pet_id = pet_id_map.get(current_selection)
            if target_pet_id:
                st.markdown(f"""
                    <div style="background-color: #e8f4fd; padding: 10px; border-radius: 6px; border: 1px solid #b8daff; margin-bottom: 15px;">
                        <span style="color: #004085; font-size: 14px;">🔢 Số báo danh của bé (ID): <b style="font-size: 16px;">PET-{target_pet_id:03d}</b></span>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div style="background-color: #f1f3f5; padding: 10px; border-radius: 6px; border: 1px solid #ced4da; margin-bottom: 15px;">
                        <span style="color: #6c757d; font-size: 14px;">🔢 Số báo danh của bé (ID): <b>Chưa xác định</b></span>
                    </div>
                """, unsafe_allow_html=True)
        
        date_str = st.date_input("Ngày đến khám:", key="app_date_input").strftime("%Y-%m-%d")
        reason = st.text_area("Triệu chứng lâm sàng sơ bộ:", key="app_reason_input")
        
        if st.button("Xác Nhận Đặt Lịch", key="btn_confirm_app"):
            if selected_pet_name == "--- Chọn thú cưng ---":
                st.error("Vui lòng chọn một thú cưng cụ thể trong danh sách!")
            else:
                add_appointment_to_db(target_pet_id, date_str, reason)
                # Reset lại lựa chọn về mặc định sau khi đặt lịch thành công
                st.session_state.selected_pet_temp = "--- Chọn thú cưng ---"
                st.session_state.app_success_msg = f"📅 Đã đặt lịch khám thành công cho bé {selected_pet_name}!"
                st.rerun()
                
        if "app_success_msg" in st.session_state:
            st.success(st.session_state.app_success_msg)
            del st.session_state.app_success_msg
            
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown('<h3 style="white-space: nowrap; margin-top: 0; margin-bottom: 0.5rem;">📸 CHUẨN ĐOÁN LÂM SÀNG AI VISION</h3>', unsafe_allow_html=True)
        st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
        
        # 1. Thêm ô lựa chọn phương thức nạp ảnh
        input_method = st.radio(
            "📍 Chọn phương thức nạp ảnh:",
            ["📁 Tải ảnh lên từ thiết bị", "📷 Chụp ảnh trực tiếp từ Camera"],
            horizontal=True,
            key="ai_input_method"
        )
        
        uploaded_file = None
        
        # 2. Hiển thị widget tương ứng dựa trên lựa chọn
        if input_method == "📁 Tải ảnh lên từ thiết bị":
            uploaded_file = st.file_uploader("Chọn tệp ảnh da liễu của thú cưng...", type=["jpg", "jpeg", "png"], key="file_viewer")
        else:
            uploaded_file = st.camera_input("Quét ảnh biểu mô da thú cưng qua camera:", key="camera_viewer")
        
        if uploaded_file:
            st.markdown("---")
            
            img_input = Image.open(uploaded_file)
            img_col, _ = st.columns([1, 2])
            with img_col:
                st.image(img_input, use_container_width=True, caption="Ảnh lâm sàng đầu vào")
            
            with st.spinner("🔬 Bác sĩ AI đang phân tích biểu mô bề mặt da..."):
                    try:
                        import requests
                        import base64
                        import json
                        
                        # Chuyển đổi ảnh sang dạng base64 để gửi qua API
                        uploaded_file.seek(0)
                        image_bytes = uploaded_file.read()
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        
                        # Gọi API Gemini 2.5 Flash
                        # Tự thay thế mã API Key thật của bạn trực tiếp vào đây
                        api_key_vision = st.secrets["GEMINI_API_KEY"]
                        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + api_key_vision
                        
                        prompt_analysis = (
                            "Bạn là một chuyên gia da liễu thú y cấp cao. Hãy phân tích bức ảnh biểu mô da này của chó/mèo. "
                            "Hãy trả về câu trả lời phân tách rõ ràng thành các mục sau (ngắn gọn, trực diện, chuyên nghiệp): "
                            "1. Tên bệnh dự đoán tốt nhất (ví dụ: Nấm, Viêm da dị ứng, Ghẻ, Nhiễm khuẩn). "
                            "2. Tỷ lệ phần trăm chính xác ước tính (từ 80.0% đến 99.0%). "
                            "3. Triệu chứng đặc trưng nhìn thấy trên ảnh. "
                            "4. Phác đồ điều trị chi tiết bằng thuốc hoặc sữa tắm thực tế tại Việt Nam."
                        )
                        
                        payload = {
                            "contents": [{
                                "parts": [
                                    {"text": prompt_analysis},
                                    {
                                        "inlineData": {
                                            "mimeType": uploaded_file.type if hasattr(uploaded_file, 'type') else "image/jpeg",
                                            "data": image_base64
                                        }
                                    }
                                ]
                            }]
                        }
                        
                        headers = {'Content-Type': 'application/json'}
                        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
                        
                        if response.status_code == 200:
                            result_data = response.json()
                            ai_raw_response = result_data['candidates'][0]['content']['parts'][0]['text']
                            
                            # Loại bỏ dòng trống thừa để văn bản không bị giãn cách quá xa
                            import re
                            ai_clean_response = re.sub(r'\n\s*\n+', '\n', ai_raw_response.strip())
                            
                            st.success("🏥 PHÂN TÍCH LÂM SÀNG HOÀN TẤT")
                            st.markdown(f"""
                                <div style="background-color: #e8f4fd; padding: 15px; border-radius: 8px; border: 1px solid #b8daff; margin-bottom: 15px; color: #004085;">
                                    <b>📊 Kết quả từ Bác sĩ AI Vision:</b>
                                    <div style="
                                        white-space: pre-wrap;
                                        line-height: 1.5;
                                        margin-top: 8px;
                                        font-size: 14.5px;
                                        max-height: 320px;
                                        overflow-y: auto;
                                        padding-right: 10px;
                                    ">{ai_clean_response}</div>
                                </div>
                                <style>
                                    div[style*="max-height: 320px"]::-webkit-scrollbar {{ width: 6px; }}
                                    div[style*="max-height: 320px"]::-webkit-scrollbar-thumb {{ background: #b8daff; border-radius: 10px; }}
                                    div[style*="max-height: 320px"]::-webkit-scrollbar-track {{ background: transparent; }}
                                </style>
                            """, unsafe_allow_html=True)
                        else:
                            st.error(f"Lỗi kết nối máy chủ AI (Code: {response.status_code})")
                            
                    except Exception as e:
                        st.error(f"Không thể kết nối API AI Vision. Chi tiết: {e}")
                            

    # 🔒 HIỂN THỊ LỊCH HẸN BẢO MẬT: ĐÃ ĐƯỢC ÉP KIỂU SỐ NGUYÊN ĐỂ KHỚP LỊCH HẸN CŨ TRÊN HỆ THỐNG THẬT
    st.markdown("### 📋 LỊCH HẸN KHÁM BỆNH CỦA TÔI")
    st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
    all_appointments = get_all_data("appointments")
    
    # Ép kiểu dữ liệu về int để việc đối chiếu giữa ID thú cưng và ID lịch hẹn luôn khớp 100%
    my_pet_ids = [int(p[0]) for p in my_pets] if my_pets else []
    my_appointments = [a for a in all_appointments if int(a[1]) in my_pet_ids]

    if my_appointments:
        display_client_apps = []
        for index, a in enumerate(my_appointments):
            # Tra cứu ngược tên thú cưng dựa trên ID để hiển thị trực quan
            pet_name = next((p[2] for p in my_pets if int(p[0]) == int(a[1])), "Không xác định")
            display_client_apps.append({
                "STT": index + 1,
                "Tên Thú Cưng": pet_name,
                "Ngày Hẹn Đến Khám": a[2],
                "Lý Do / Triệu Chứng": a[3],
                "Trạng Thái Kiểm Duyệt": a[4]
            })
        st.dataframe(display_client_apps, use_container_width=True)
    else:
        st.info("Bạn chưa ghi nhận lịch hẹn khám bệnh nào trên hệ thống.")
    st.markdown("</div>", unsafe_allow_html=True)

# GIAO DIỆN BÁC SĨ THÚ Y (ADMIN)
else:
    st.markdown("<h1 style='color: #28a745; text-align: center;'>🩺 TRUNG TÂM ĐIỀU HÀNH PHÒNG KHÁM PETCARE</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6c757d;'>Hệ thống quản lý dữ liệu bệnh án, tiếp nhận lịch hẹn và điều phối bác sĩ thời gian thực</p>", unsafe_allow_html=True)
    st.markdown("---")

    # 📊 1. KHỐI THỐNG KÊ TỔNG QUAN THỜI GIAN THỰC
    apps_data = get_all_data("appointments")
    pets_data = get_all_data("pets")
    users_data = get_all_data("users")
    
    total_appointments = len(apps_data)
    total_pets = len(pets_data)
    pending_apps = len([a for a in apps_data if a[4] == 'Chờ xác nhận'])
    approved_apps = len([a for a in apps_data if a[4] == 'Đã xác nhận'])

    total_revenue = sum(a[6] for a in apps_data if a[4] == "Đã xác nhận")

    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    with m_col1:
        st.markdown(f"<div class='metric-card' style='background: linear-gradient(135deg, #1d976c, #93f9b9); color:#113a23;'>🐾 TỔNG HỒ SƠ THÚ CƯNG<br><span style='font-size:26px;'>{total_pets} bé</span></div>", unsafe_allow_html=True)
    with m_col2:
        st.markdown(f"<div class='metric-card' style='background: linear-gradient(135deg, #ff9900, #ff5500);'>📅 TỔNG SỐ LỊCH HẸN<br><span style='font-size:26px;'>{total_appointments} ca</span></div>", unsafe_allow_html=True)
    with m_col3:
        st.markdown(f"<div class='metric-card' style='background: linear-gradient(135deg, #d31027, #ea384d);'>⏳ ĐANG CHỜ DUYỆT<br><span style='font-size:26px;'>{pending_apps} ca</span></div>", unsafe_allow_html=True)
    with m_col4:
        st.markdown(f"<div class='metric-card' style='background: linear-gradient(135deg, #00c6ff, #0072ff);'>🟢 LỊCH ĐÃ XÁC NHẬN<br><span style='font-size:26px;'>{approved_apps} ca</span></div>", unsafe_allow_html=True)
    with m_col5:
        st.markdown(f"<div class='metric-card' style='background: linear-gradient(135deg, #6a11cb, #2575fc);'>💰 TỔNG DOANH THU<br><span style='font-size:22px;'>{total_revenue:,.0f} đ</span></div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)


    # 📊 2. BIỂU ĐỒ THỐNG KÊ TRỰC QUAN
    st.markdown("### 📈 THỐNG KÊ TRỰC QUAN")
    chart_col1, chart_col2 = st.columns(2)

    if apps_data:
        df_apps = pd.DataFrame(apps_data, columns=["id", "pet_id", "date", "reason", "status", "doctor_notes", "fee"])

        with chart_col1:
            st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
            st.markdown("**📅 Số lịch hẹn theo ngày**")
            apps_by_date = df_apps.groupby("date").size().reset_index(name="Số lượng")
            apps_by_date = apps_by_date.sort_values("date")
            fig_date = px.line(apps_by_date, x="date", y="Số lượng", markers=True)
            fig_date.update_traces(line_color="#007bff")
            fig_date.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            st.plotly_chart(fig_date, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with chart_col2:
            st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
            st.markdown("**📌 Tỷ lệ trạng thái lịch hẹn**")
            status_counts = df_apps["status"].value_counts().reset_index()
            status_counts.columns = ["Trạng thái", "Số lượng"]
            fig_status = px.pie(
                status_counts, names="Trạng thái", values="Số lượng", hole=0.5,
                color="Trạng thái",
                color_discrete_map={"Chờ xác nhận": "#ff9900", "Đã xác nhận": "#007bff", "Đã hủy": "#dc3545"}
            )
            fig_status.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            st.plotly_chart(fig_status, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # 💰 Biểu đồ doanh thu theo ngày (chỉ tính ca đã xác nhận)
        df_revenue = df_apps[df_apps["status"] == "Đã xác nhận"]
        if not df_revenue.empty and df_revenue["fee"].sum() > 0:
            st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
            st.markdown("**💰 Doanh thu theo ngày (VNĐ)**")
            revenue_by_date = df_revenue.groupby("date")["fee"].sum().reset_index()
            revenue_by_date = revenue_by_date.sort_values("date")
            fig_revenue = px.bar(revenue_by_date, x="date", y="fee", labels={"fee": "Doanh thu (đ)", "date": "Ngày"})
            fig_revenue.update_traces(marker_color="#6a11cb")
            fig_revenue.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            st.plotly_chart(fig_revenue, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Chưa có dữ liệu lịch hẹn để thống kê.")

    if pets_data:
        st.markdown("<div class='feature-box'>", unsafe_allow_html=True)
        st.markdown("**🐾 Phân bố loài thú cưng đang quản lý**")
        df_pets = pd.DataFrame(pets_data, columns=["id", "owner", "name", "species", "age", "weight", "image_features"])
        species_counts = df_pets["species"].value_counts().reset_index()
        species_counts.columns = ["Loài", "Số lượng"]
        fig_species = px.bar(species_counts, x="Loài", y="Số lượng", color="Loài",
                              color_discrete_sequence=px.colors.qualitative.Set2)
        fig_species.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=260, showlegend=False)
        st.plotly_chart(fig_species, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_manage_apps, tab_manage_pets, tab_manage_customers, tab_face_id = st.tabs(
            ["📬 XỬ LÝ LỊCH HẸN", "🗂️ QUẢN LÝ BỆNH ÁN", "👥 QUẢN LÝ KHÁCH HÀNG", "📸 AI PET FACE ID"]
        )
    with tab_manage_apps:
        st.markdown("### 🔍 Bộ lọc & Điều phối ca bệnh")
        f_col1, f_col2 = st.columns([1, 2])
        with f_col1:
            status_filter = st.selectbox("Lọc lịch hẹn theo trạng thái:", ["Tất cả", "Chờ xác nhận", "Đã xác nhận", "Đã hủy"])
        with f_col2:
            search_query = st.text_input("🔍 Tìm nhanh theo tên thú cưng:", placeholder="Nhập tên bé để tìm kiếm...")

        # Ánh xạ thông tin chi tiết của thú cưng để phục vụ tìm kiếm và hiển thị
        pet_map = {p[0]: p[2] for p in pets_data} # {1: "Bé Lu"}
        
        filtered_apps = apps_data
        if status_filter != "Tất cả":
            filtered_apps = [a for a in filtered_apps if a[4] == status_filter]
        if search_query:
            # Lọc theo tên của thú cưng tương ứng với pet_id
            filtered_apps = [a for a in filtered_apps if search_query.lower() in pet_map.get(a[1], "").lower()]

        # Nút xuất Excel danh sách lịch hẹn đang lọc
        if filtered_apps:
            export_rows = []
            for a in filtered_apps:
                export_rows.append({
                    "Thú cưng": pet_map.get(a[1], "Không xác định"),
                    "Mã thú cưng": f"PET-{a[1]:03d}",
                    "Ngày hẹn": a[2],
                    "Triệu chứng": a[3],
                    "Trạng thái": a[4],
                    "Ghi chú bác sĩ": a[5],
                    "Phí khám (đ)": a[6]
                })
            df_export = pd.DataFrame(export_rows)
            excel_buffer = io.BytesIO()
            df_export.to_excel(excel_buffer, index=False, engine="openpyxl")
            st.download_button(
                "📥 Xuất Excel danh sách lịch hẹn (theo bộ lọc hiện tại)",
                data=excel_buffer.getvalue(),
                file_name=f"lich_hen_petcare_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.markdown("<br>", unsafe_allow_html=True)

        if filtered_apps:
            for app in filtered_apps:
                p_name_display = pet_map.get(app[1], "Không xác định")
                with st.container():
                    st.markdown(f"""
                    <div style='background-color: white; padding: 15px; border-radius: 8px; border-left: 5px solid {"#ff9900" if app[4]=="Chờ xác nhận" else "#007bff" if app[4]=="Đã xác nhận" else "#dc3545"}; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
                        <span style='font-size: 16px; font-weight: bold; color: #333;'>🐶 Thú cưng: {p_name_display} (Mã PET-{app[1]:03d})</span> | 📅 Ngày hẹn: <b>{app[2]}</b> | 📌 Trạng thái: <i>{app[4]}</i><br>
                        <span style='color: #666; font-size: 13.5px;'>📝 Triệu chứng lâm sàng: {app[3]}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    act_col1, act_col2, act_col3, _ = st.columns([1, 1, 1, 5])
                    with act_col1:
                        if app[4] == "Chờ xác nhận":
                            if st.button(f"✅ Duyệt", key=f"app_ok_{app[0]}"):
                                update_appointment_status(app[0], "Đã xác nhận")
                                st.toast(f"Đã duyệt lịch cho bé {p_name_display}!")
                                st.rerun()
                    with act_col2:
                        if app[4] != "Đã hủy":
                            if st.button(f"❌ Hủy ca", key=f"app_no_{app[0]}"):
                                update_appointment_status(app[0], "Đã hủy")
                                st.toast(f"Đã hủy ca bệnh của bé {p_name_display}")
                                st.rerun()
                    with act_col3:
                        if st.button(f"🗑️ Xóa", key=f"app_del_{app[0]}"):
                            delete_appointment(app[0])
                            st.toast("Đã xóa bản ghi khỏi dữ liệu phòng khám.")
                            st.rerun()

                    # 📝 Ghi chú / kết luận chẩn đoán của bác sĩ + Phí khám
                    with st.expander("📝 Ghi chú chẩn đoán & Phí khám"):
                        note_val = st.text_area(
                            "Kết luận / chỉ định điều trị:",
                            value=app[5],
                            key=f"note_input_{app[0]}",
                            placeholder="Ví dụ: Chẩn đoán viêm da dị ứng, kê đơn thuốc bôi X, tái khám sau 7 ngày..."
                        )
                        fee_val = st.number_input(
                            "💰 Phí khám (VNĐ):",
                            min_value=0,
                            step=10000,
                            value=int(app[6]),
                            key=f"fee_input_{app[0]}"
                        )
                        if st.button("💾 Lưu ghi chú & Phí khám", key=f"note_save_{app[0]}"):
                            update_appointment_notes(app[0], note_val)
                            update_appointment_fee(app[0], fee_val)
                            st.toast("Đã lưu ghi chú và phí khám!")
                            st.rerun()
        else:
            st.info("Không tìm thấy lịch hẹn nào phù hợp với bộ lọc hiện tại.")

        with tab_manage_pets:
            st.markdown("### 🗂️ Danh sách hồ sơ bệnh án thú cưng")
            if pets_data:
                df_pets = pd.DataFrame(pets_data, columns=["id", "owner", "name", "species", "age", "weight", "image_features"])
                excel_buffer_pets = io.BytesIO()
                ddf_pets_export = pd.DataFrame(pets_data, columns=["id", "owner_username", "name", "species", "age", "weight", "image_features"])
                st.download_button(
                    "📥 Xuất Excel danh sách thú cưng",
                    data=excel_buffer_pets.getvalue(),
                    file_name=f"benh_an_thu_cung_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                # Ánh xạ username sang Họ Tên thật của khách hàng
                user_map = {u[0]: u[2] for u in users_data}
                display_pets = []
                for p in pets_data:
                    owner_full_name = user_map.get(p[1], p[1])
                    display_pets.append({
                        "Mã Số": f"PET-{p[0]:03d}",
                        "Họ Tên Chủ Nuôi": owner_full_name,
                        "Tên Thú Cưng": p[2],
                        "Chủng Loài": p[3],
                        "Tuổi (Tháng/Năm)": f"{p[4]} tuổi",
                        "Cân Nặng Hiện Tại": f"{p[5]} kg"
                    })
                st.dataframe(display_pets, use_container_width=True)
            else:
                st.info("Hệ thống dữ liệu lưu trữ bệnh án trống.")
        
        with tab_manage_customers:
            st.markdown("### 👥 Danh sách khách hàng (chủ nuôi)")

            customer_search = st.text_input("🔍 Tìm khách hàng theo tên, username hoặc SĐT:", key="cust_search")

            # Chỉ liệt kê khách hàng thường (không gồm admin)
            customer_list = [u for u in users_data if u[0] != "admin"]

            customer_rows = []
            for u in customer_list:
                username, _, full_name, phone = u # <-- Giải nén thêm trường phone
                
                # Hỗ trợ tìm kiếm theo cả Số điện thoại
                if customer_search and (
                    customer_search.lower() not in full_name.lower() and 
                    customer_search.lower() not in username.lower() and 
                    customer_search.lower() not in phone.lower()
                ):
                    continue
                    
                owned_pets = [p for p in pets_data if p[1] == username]
                owned_pet_ids = [p[0] for p in owned_pets]
                owned_apps = [a for a in apps_data if a[1] in owned_pet_ids]
                
                customer_rows.append({
                    "username": username,
                    "Họ tên": full_name,
                    "Số điện thoại": phone, # <-- Thêm cột SĐT vào bảng
                    "Số thú cưng": len(owned_pets),
                    "Tổng lịch hẹn": len(owned_apps),
                    "Đang chờ duyệt": len([a for a in owned_apps if a[4] == "Chờ xác nhận"]),
                    "pets": owned_pets,
                    "apps": owned_apps
                })

            if customer_rows:
                # Tạo bảng thống kê (bỏ các cột chứa list để hiển thị dataframe chuẩn)
                summary_df = pd.DataFrame([
                    {k: v for k, v in r.items() if k not in ["pets", "apps", "username"]}
                    for r in customer_rows
                ])
                st.dataframe(summary_df, use_container_width=True)

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("#### 🔎 Chi tiết từng khách hàng")
                for r in customer_rows:
                    # Hiển thị số điện thoại trực quan ngay tiêu đề Expander
                    with st.expander(f"👤 {r['Họ tên']} ({r['username']}) — 📞 SĐT: {r['Số điện thoại']} — {r['Số thú cưng']} bé, {r['Tổng lịch hẹn']} lịch hẹn"):
                        if r["pets"]:
                            st.markdown("**🐾 Thú cưng đang sở hữu:**")
                            for p in r["pets"]:
                                st.markdown(f"- {p[2]} ({p[3]}, {p[4]} tuổi, {p[5]}kg) — Mã PET-{p[0]:03d}")
                        else:
                            st.caption("Chưa đăng ký thú cưng nào.")

                        if r["apps"]:
                            st.markdown("**📅 Lịch sử lịch hẹn:**")
                            for a in r["apps"]:
                                pet_nm = pet_map.get(a[1], "Không xác định") if 'pet_map' in dir() else next((p[2] for p in r["pets"] if p[0] == a[1]), "Không xác định")
                                st.markdown(f"- {a[2]} — {pet_nm} — *{a[4]}*")
                        else:
                            st.caption("Chưa có lịch hẹn nào.")
            else:
                st.info("Không tìm thấy khách hàng phù hợp.")

            with tab_face_id:
                st.markdown("### 📸 HỆ THỐNG NHẬN DIỆN THÚ CƯNG (PET FACE ID)")
                
                # 1. Trạng thái camera
                if "cam_active" not in st.session_state:
                    st.session_state.cam_active = False

                # 2. Khung Camera
                if st.session_state.cam_active:
                    face_id_img = st.camera_input("📸 Camera đang hoạt động:", key="pet_face_cam")
                else:
                    st.markdown("""
                        <div style="width: 100%; height: 300px; background-color: #f8f9fa; display: flex; 
                        flex-direction: column; align-items: center; justify-content: center; 
                        border: 2px dashed #20c997; border-radius: 15px; color: #20c997; margin-bottom: 15px;">
                            <span style="font-size: 40px;">📷</span>
                            <b style="font-size: 14px; margin-top: 10px;">MÀN HÌNH CHỜ - NHẤN "BẬT CAMERA" ĐỂ BẮT ĐẦU</b>
                        </div>
                    """, unsafe_allow_html=True)
                    face_id_img = None

                # 3. Các nút điều khiển
                if st.button("✅ BẬT CAMERA", use_container_width=True):
                    st.session_state.cam_active = True
                    st.rerun()
                    
                if st.button("❌ TẮT CAMERA", use_container_width=True):
                    st.session_state.cam_active = False
                    st.rerun()

                # 4. XỬ LÝ QUÉT NGAY KHI CÓ ẢNH
                if st.session_state.cam_active and face_id_img:
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.spinner("🔍 AI đang phân tích sinh trắc học..."):
                        try:
                            import requests, base64, json

                            face_id_img.seek(0)
                            new_image_base64 = base64.b64encode(face_id_img.read()).decode('utf-8')
                            api_key_vision = st.secrets["GEMINI_API_KEY"]
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key_vision}"

                            current_pets = get_all_data("pets")
                            # CHỈ lấy những bé ĐÃ có ảnh hồ sơ lưu trong DB để so sánh
                            pets_with_photo = [p for p in current_pets if p[6]]

                            prompt_face = (
                                "Bạn là chuyên gia AI nhận diện khuôn mặt thú cưng bằng cách so sánh HÌNH ẢNH THỰC TẾ, "
                                "KHÔNG dựa vào tên hay loài. "
                                "Ảnh ĐẦU TIÊN là ảnh vừa quét cần nhận diện. Các ảnh tiếp theo là ảnh hồ sơ đã lưu, "
                                "mỗi ảnh có nhãn PET_ID đứng ngay trước nó. "
                                "So sánh đặc điểm ngoại hình (màu lông, hoa văn/đốm, hình dạng tai, mũi, mắt...) giữa ảnh vừa quét "
                                "và từng ảnh hồ sơ. "
                                "Nếu khớp với một hồ sơ, CHỈ trả về DUY NHẤT con số PET_ID đó, không thêm chữ nào khác (ví dụ: 3). "
                                "Nếu không khớp với bất kỳ hồ sơ nào, trả về đúng định dạng: "
                                "NEW|Giống loài|Đặc điểm nhận diện lông và ngoại hình|Nhận xét chi tiết khuôn mặt."
                            )

                            parts = [
                                {"text": prompt_face},
                                {"text": "ẢNH CẦN NHẬN DIỆN:"},
                                {"inlineData": {"mimeType": "image/jpeg", "data": new_image_base64}}
                            ]

                            for p in pets_with_photo:
                                parts.append({"text": f"PET_ID {p[0]} - Ảnh hồ sơ đã lưu:"})
                                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": p[6]}})

                            payload = {"contents": [{"parts": parts}]}
                            response = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))

                            if response.status_code == 200:
                                result_text = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()

                                # --- TRƯỜNG HỢP NHẬN DIỆN ĐƯỢC THÚ CƯNG CŨ ---
                                if result_text.isdigit():
                                    matched_id = int(result_text)
                                    matched_pet = next((p for p in current_pets if p[0] == matched_id), None)
                                    if matched_pet:
                                        owner_info = get_user_by_username(matched_pet[1])
                                        st.success(f"✅ ĐÃ NHẬN DIỆN: {matched_pet[2]} (Mã: PET-{matched_id:03d})")
                                        if owner_info:
                                            st.markdown(f"""
                                            <div style="background-color:#e8f4fd;padding:15px;border-radius:8px;border:1px solid #b8daff;color:#004085;">
                                                <b>👤 Thông tin chủ nuôi:</b><br>
                                                • Họ tên: {owner_info['full_name']}<br>
                                                • Username: {owner_info['username']}<br>
                                                • SĐT: {owner_info['phone'] or 'Chưa cập nhật'}<br>
                                                • Loài: {matched_pet[3]} — Tuổi: {matched_pet[4]} — Cân nặng: {matched_pet[5]}kg
                                            </div>
                                            """, unsafe_allow_html=True)
                                        else:
                                            st.error(f"⚠️ Không tìm thấy chủ nuôi trong hệ thống (owner_username: '{matched_pet[1]}').")
                                    else:
                                        st.error("Không tìm thấy hồ sơ thú cưng tương ứng với ID nhận diện được.")

                                # --- TRƯỜNG HỢP LÀ THÚ CƯNG MỚI ---
                                elif "NEW" in result_text:
                                    parts_r = result_text.split("|")
                                    st.warning("⚠️ Thú cưng này chưa có trong danh sách hồ sơ (hoặc chưa từng được gán ảnh)!")
                                    st.markdown(f"""
                                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; margin-bottom: 15px;">
                                        <b>🤖 AI phân tích chi tiết:</b><br>
                                        • 🧬 <b>Giống loài:</b> {parts_r[1] if len(parts_r) > 1 else 'Khác'}<br>
                                        • 🐾 <b>Đặc điểm:</b> {parts_r[2] if len(parts_r) > 2 else 'Không rõ'}<br>
                                        • 📝 <b>Nhận xét:</b> {parts_r[3] if len(parts_r) > 3 else 'Không rõ'}
                                    </div>
                                    """, unsafe_allow_html=True)

                                    all_pets_db = get_all_data("pets")
                                    if all_pets_db:
                                        pet_options = {f"{p[2]} (Mã: PET-{p[0]:03d})": p[0] for p in all_pets_db}
                                        selected_pet_label = st.selectbox("Chọn hồ sơ thú cưng để gán Face ID:", list(pet_options.keys()))
                                        if st.button("🔗 Gán Face ID vào hồ sơ này"):
                                            selected_id = pet_options[selected_pet_label]
                                            update_pet_features(selected_id, new_image_base64)
                                            st.success(f"✅ Đã gán thành công khuôn mặt cho bé {selected_pet_label}!")
                                            st.rerun()
                                    else:
                                        st.error("Hệ thống chưa có hồ sơ nào để gán.")
                                else:
                                    st.warning("AI không xác định được kết quả rõ ràng, vui lòng thử quét lại với ánh sáng tốt hơn.")
                            else:
                                st.error(f"Lỗi API: {response.status_code}")
                        except Exception as e:
                            st.error(f"Lỗi hệ thống: {e}")
# =====================
# KHỐI CHATBOT ĐỘC LẬP 
# =====================
import streamlit.components.v1 as components

if st.session_state.logged_in and st.session_state.user_role == "Khách Hàng":
    api_key_chat = st.secrets["GEMINI_API_KEY"]

    chatbot_injector = f"""
    <script>
    (function() {{
        var doc = window.parent.document;

        // Tránh chèn trùng lặp mỗi khi Streamlit rerun
        var oldWrapper = doc.getElementById('petcare-chat-wrapper');
        if (oldWrapper) oldWrapper.remove();
        var oldStyle = doc.getElementById('petcare-chat-style');
        if (oldStyle) oldStyle.remove();

        // 1. Chèn CSS vào <head> của trang chính
        var style = doc.createElement('style');
        style.id = 'petcare-chat-style';
        style.innerHTML = `
            #petcare-chat-wrapper {{
                position: fixed !important;
                z-index: 2147483647 !important;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            #chat-bubble {{
                position: fixed !important;
                bottom: 25px !important;
                right: 25px !important;
                width: 60px; height: 60px;
                background: #007bff;
                border-radius: 50%;
                box-shadow: 0 4px 16px rgba(0,123,255,0.4);
                cursor: pointer;
                display: flex; align-items: center; justify-content: center;
                transition: all 0.3s ease;
            }}
            #chat-bubble:hover {{ transform: scale(1.1); background: #0056b3; }}
            #chat-bubble img {{ width: 35px; height: 35px; }}
            #chat-badge {{ position: absolute; top: -2px; right: -2px; background: #dc3545; color: white; border-radius: 50%; padding: 3px 7px; font-size: 10px; font-weight: bold; }}
            #chat-window {{
    position: fixed !important;
    bottom: 95px !important;
    right: 25px !important;
    top: auto !important;
    width: 330px;
    height: 440px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 5px 25px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.1, 0.8, 0.25, 1);
}}
.chat-hidden {{ opacity: 0; transform: translateY(20px) scale(0.9); pointer-events: none; }}
            #chat-header {{ background: #007bff; padding: 16px; display: flex; align-items: center; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }}
            #chat-body {{ flex: 1; padding: 15px; overflow-y: auto; background: #f8f9fa; display: flex; flex-direction: column; gap: 10px; }}
            .msg-bot, .msg-user {{ max-width: 80%; padding: 10px 14px; border-radius: 14px; font-size: 13.5px; line-height: 1.4; }}
            .msg-bot {{ background: #e9ecef; color: #212529; align-self: flex-start; border-bottom-left-radius: 2px; }}
            .msg-user {{ background: #007bff; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }}
            #chat-footer {{ padding: 10px; border-top: 1px solid #dee2e6; display: flex; gap: 8px; }}
            #chat-input {{ flex: 1; border: 1px solid #ced4da; border-radius: 20px; padding: 8px 16px; outline: none; font-size: 13px; }}
            #chat-send {{ background: #007bff; color: white; border: none; border-radius: 20px; padding: 8px 16px; cursor: pointer; font-weight: bold; font-size: 13px; }}
            #chat-poweredby {{ text-align: center; font-size: 11px; color: #adb5bd; font-style: italic; padding: 6px 0 10px; background: white; }}
        `;
        doc.head.appendChild(style);

        // 2. Chèn HTML vào cuối <body> của trang chính
        var wrapper = doc.createElement('div');
        wrapper.id = 'petcare-chat-wrapper';
        wrapper.innerHTML = `
            <div id="chat-bubble">
                <img src="https://cdn-icons-png.flaticon.com/512/616/616408.png" alt="Logo AI">
                <span id="chat-badge">1</span>
            </div>
            <div id="chat-window" class="chat-hidden">
                <div id="chat-header">
                    <img src="https://cdn-icons-png.flaticon.com/512/616/616408.png" style="width:28px; height:28px; margin-right:10px;">
                    <div style="flex:1;">
                        <strong style="color:white; font-size:15px;">Bác Sĩ Thú Y AI</strong>
                        <div style="color:#b2d4ff; font-size:11px;">🟢 Đang hoạt động trực tuyến</div>
                    </div>
                    <span id="chat-close-btn" style="cursor:pointer; font-size:20px; color:white; padding:0 6px;">×</span>
                </div>
                <div id="chat-body"><div class="msg-bot">Xin chào! Tôi là trợ lý ảo y khoa PetCare. Bé cưng của bạn đang có triệu chứng gì cần tôi tư vấn không?</div></div>
                <div id="chat-footer">
                    <input type="text" id="chat-input" placeholder="Nhập triệu chứng bệnh lý...">
                    <button id="chat-send">Gửi</button>
                </div>
            </div>
        `;
        doc.body.appendChild(wrapper);

        // 3. Gắn sự kiện (thay vì onclick inline, vì innerHTML đôi khi không nhận inline handler ổn định)
        var bubble = doc.getElementById('chat-bubble');
        var win = doc.getElementById('chat-window');
        var badge = doc.getElementById('chat-badge');
        var closeBtn = doc.getElementById('chat-close-btn');
        var input = doc.getElementById('chat-input');
        var sendBtn = doc.getElementById('chat-send');
        var body = doc.getElementById('chat-body');

        function toggleChat() {{
            win.classList.toggle('chat-hidden');
            badge.style.display = 'none';
        }}
        bubble.addEventListener('click', toggleChat);
        closeBtn.addEventListener('click', toggleChat);

        function sendMessage() {{
            var text = input.value.trim();
            if (!text) return;
            var userDiv = doc.createElement('div');
            userDiv.className = 'msg-user';
            userDiv.innerText = text;
            body.appendChild(userDiv);
            input.value = '';
            body.scrollTop = body.scrollHeight;

            var loadingDiv = doc.createElement('div');
            loadingDiv.className = 'msg-bot';
            loadingDiv.id = 'chat-loading';
            loadingDiv.innerText = 'Bác sĩ AI đang phân tích dữ liệu...';
            body.appendChild(loadingDiv);
            body.scrollTop = body.scrollHeight;

            var url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key_chat}";
            var promptContext = "Bạn là một bác sĩ thú y chuyên nghiệp tại Việt Nam. Hãy trả lời câu hỏi sau của chủ nuôi thật ngắn gọn dưới 3 dòng, đưa ra giải pháp thực tế: " + text;
            var payload = {{ "contents": [{{ "parts": [{{ "text": promptContext }}] }}] }};

            fetch(url, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload)
            }})
            .then(function(response) {{ return response.json(); }})
            .then(function(data) {{
                var loading = doc.getElementById('chat-loading');
                if (loading) loading.remove();
                var botText = data.candidates[0].content.parts[0].text;
                var botDiv = doc.createElement('div');
                botDiv.className = 'msg-bot';
                botDiv.innerText = botText;
                body.appendChild(botDiv);
                body.scrollTop = body.scrollHeight;
            }})
            .catch(function(error) {{
                var loading = doc.getElementById('chat-loading');
                if (loading) loading.remove();
                var errDiv = doc.createElement('div');
                errDiv.className = 'msg-bot';
                errDiv.innerText = 'Xin lỗi, hệ thống đang bận. Vui lòng thử lại sau.';
                body.appendChild(errDiv);
            }});
        }}

        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') sendMessage();
        }});
    }})();
    </script>
    """

    components.html(chatbot_injector, height=0, width=0)
