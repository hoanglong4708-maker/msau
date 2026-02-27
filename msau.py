import streamlit as st
import subprocess
import os
import time
from pathlib import Path
import threading
import shutil

st.set_page_config(page_title="HoangLong Python Hosting - Per-Tab Files", layout="wide", page_icon="🛠️")
st.title("🛠️ HoangLong Web Hosting - Mỗi Tab Upload Riêng + Requirements Chung")

# Thư mục chính lưu tất cả hosts
BASE_DIR = Path("tools")
BASE_DIR.mkdir(exist_ok=True)

# ====================== SIDEBAR: TẠO HOST MỚI ======================
st.sidebar.header("➕ Tạo Host/Tab Mới")
new_host_name = st.sidebar.text_input("Tên Host (ví dụ: http_sender, mqtt_bot)", "")
if st.sidebar.button("Tạo Host Mới") and new_host_name.strip():
    host_dir = BASE_DIR / new_host_name.strip()
    host_dir.mkdir(exist_ok=True)
    st.sidebar.success(f"✅ Đã tạo host: **{new_host_name}** (thư mục riêng cho files)")

# Danh sách hosts hiện có
hosts = [d.name for d in BASE_DIR.iterdir() if d.is_dir() and d.name != "__pycache__"]

if not hosts:
    st.info("Chưa có host nào. Hãy tạo ở sidebar bên trái và upload files vào.")
else:
    # Tạo tabs động
    tab_list = ["📊 Dashboard"] + [f"🔧 {host}" for host in hosts]
    tabs = st.tabs(tab_list)

    # Tab Dashboard
    with tabs[0]:
        st.write(f"**Tổng số host: {len(hosts)}**")
        st.write("Requirements đã install (từ requirements.txt chung):")
        st.code(open("requirements.txt").read() if Path("requirements.txt").exists() else "Không tìm thấy requirements.txt", language="txt")
        for host in hosts:
            st.markdown(f"- **{host}** (click tab để quản lý)")

    # Tab cho từng host
    for idx, host_name in enumerate(hosts, start=1):
        with tabs[idx]:
            st.subheader(f"🔧 Host: **{host_name}**")
            host_dir = BASE_DIR / host_name

            # Upload files riêng cho host này (tool.py + txt + json + ...)
            uploaded_files = st.file_uploader(
                f"Upload files cho {host_name} (.py, .txt, .json, cookies folder nếu cần)",
                accept_multiple_files=True,
                key=f"upload_{host_name}"
            )
            if uploaded_files:
                for uf in uploaded_files:
                    save_path = host_dir / uf.name
                    with open(save_path, "wb") as f:
                        f.write(uf.getbuffer())
                    st.success(f"Đã upload: **{uf.name}** → thư mục {host_dir}")

            # Hiển thị files hiện có trong host
            files = [f for f in host_dir.iterdir() if f.is_file()]
            if files:
                st.write("Files hiện có trong host này:")
                for f in files:
                    st.code(f"- {f.name} ({f.stat().st_size / 1024:.1f} KB)")
            else:
                st.info("Chưa có file nào. Upload ở trên để bắt đầu.")

            # Chọn script .py để chạy
            scripts = [f.name for f in host_dir.glob("*.py")]
            if not scripts:
                st.warning("Chưa upload file .py nào cho host này.")
            else:
                selected_script = st.selectbox("Chọn tool để chạy", scripts, key=f"script_sel_{host_name}")
                script_path = host_dir / selected_script

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("▶️ Start Tool", key=f"start_{host_name}"):
                        st.session_state[f"running_{host_name}"] = True
                        st.session_state[f"log_{host_name}"] = f"🚀 Bắt đầu chạy {selected_script}...\n"
                with col2:
                    if st.button("⏹️ Stop Tool", key=f"stop_{host_name}"):
                        st.session_state[f"running_{host_name}"] = False
                with col3:
                    if st.button("🗑️ Xóa Log", key=f"clearlog_{host_name}"):
                        st.session_state[f"log_{host_name}"] = ""

                # Placeholder cho log realtime
                log_placeholder = st.empty()

                if st.session_state.get(f"running_{host_name}", False):
                    def run_tool_thread():
                        try:
                            # Chạy subprocess với cwd = host_dir → tool đọc file.txt đúng chỗ
                            process = subprocess.Popen(
                                ["python", str(script_path)],
                                cwd=str(host_dir),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True,
                                bufsize=1,
                                universal_newlines=True
                            )
                            while st.session_state.get(f"running_{host_name}", False):
                                line = process.stdout.readline()
                                if line:
                                    current_log = st.session_state.get(f"log_{host_name}", "") + line
                                    st.session_state[f"log_{host_name}"] = current_log
                                    log_placeholder.code(current_log, language="bash")
                                time.sleep(0.1)
                            process.terminate()
                            st.session_state[f"log_{host_name}"] += "\n⏹️ Tool đã dừng.\n"
                        except Exception as e:
                            st.session_state[f"log_{host_name}"] += f"\n❌ Lỗi runtime: {str(e)}\n"

                    # Khởi động thread nếu chưa có
                    thread_key = f"thread_{host_name}"
                    if thread_key not in st.session_state:
                        thread = threading.Thread(target=run_tool_thread, daemon=True)
                        thread.start()
                        st.session_state[thread_key] = thread

                    # Cập nhật log
                    log_placeholder.code(st.session_state.get(f"log_{host_name}", "Đang chờ output..."), language="bash")

# Footer
st.markdown("---")
st.caption("HoangLong Hosting © 2026 • Requirements chung từ requirements.txt • Miễn phí trên Streamlit Cloud • Up tool thoải mái!")
