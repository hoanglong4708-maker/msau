# app.py - Facebook MQTT Sender Multi-Tab (Streamlit)
import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import threading
import uuid
import ssl
from datetime import datetime

# Khởi tạo session state cho nhiều tab
if "tab_states" not in st.session_state:
    st.session_state.tab_states = {}
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0
if "next_tab_id" not in st.session_state:
    st.session_state.next_tab_id = 1

def get_tab_state(tab_id):
    if tab_id not in st.session_state.tab_states:
        st.session_state.tab_states[tab_id] = {
            "logs": [],
            "running": False,
            "threads": [],
            "cookies": "",
            "thread_ids": "",
            "message": "",
            "delay": 15.0,
            "message_type": "Nhập trực tiếp"
        }
    return st.session_state.tab_states[tab_id]

def tab_log(tab_id, msg, level="info"):
    state = get_tab_state(tab_id)
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}.get(level, "→")
    line = f"[{timestamp}] {prefix} {msg}"
    state["logs"].append(line)
    print(line)

def get_token(cookie):
    parts = cookie.split(';')
    c_user = xs = None
    for part in parts:
        part = part.strip()
        if part.startswith('c_user='):
            c_user = part.split('=', 1)[1]
        elif part.startswith('xs='):
            xs = part.split('=', 1)[1]
    return f"{c_user}|{xs}" if c_user and xs else cookie

def create_mqtt(cookie):
    try:
        token = get_token(cookie)
        client_id = f"mqttwsclient_{uuid.uuid4().hex[:8]}"
        client = mqtt.Client(
            client_id=client_id, transport="websockets", protocol=mqtt.MQTTv31, clean_session=True
        )
        
        username_payload = {
            "u": token.split('|')[0] if '|' in token else token,
            "s": 1, "chat_on": True, "fg": True,
            "d": str(uuid.uuid4()),
            "ct": "websocket", "mqtt_sid": "",
            "aid": 219994525426954,
            "st": [], "pm": [], "cp": 3, "ecp": 10, "pack": []
        }
        
        client.username_pw_set(username=json.dumps(username_payload), password="")
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        
        client.ws_set_options(
            path="/chat",
            headers={
                "Cookie": cookie,
                "Origin": "https://www.facebook.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        
        client.connect("edge-chat.facebook.com", 443, 60)
        client.loop_start()
        time.sleep(1.5)
        return client, token
    except Exception as e:
        return None, None

def send_message_loop(client, token, thread_id, message, delay_sec, tab_id):
    state = get_tab_state(tab_id)
    while state["running"]:
        try:
            msg_id = str(int(time.time() * 1000))
            payload = {
                "body": message,
                "msgid": msg_id,
                "sender_fbid": token.split('|')[0] if '|' in token else token,
                "to": thread_id,
                "offline_threading_id": msg_id
            }
            result = client.publish("/send_message2", json.dumps(payload), qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                tab_log(tab_id, f"Gửi thành công → {thread_id}")
            else:
                tab_log(tab_id, f"Gửi thất bại → {thread_id} (rc={result.rc})", "error")
                
            time.sleep(max(0.3, delay_sec))
        except Exception as e:
            tab_log(tab_id, f"Lỗi khi gửi: {e}", "error")
            time.sleep(5)

def worker(cookie_idx, cookie, thread_ids, message, delay_sec, tab_id):
    client, token = create_mqtt(cookie)
    if not client or not token:
        tab_log(tab_id, f"Cookie {cookie_idx+1}: Không kết nối được MQTT", "error")
        return
    
    tab_log(tab_id, f"Cookie {cookie_idx+1} kết nối MQTT thành công")
    
    state = get_tab_state(tab_id)
    for tid in thread_ids:
        t = threading.Thread(
            target=send_message_loop,
            args=(client, token, tid, message, delay_sec, tab_id),
            daemon=True
        )
        t.start()
        state["threads"].append(t)
    
    try:
        while state["running"]:
            time.sleep(1.2)
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass
        tab_log(tab_id, f"Cookie {cookie_idx+1} đã ngắt kết nối")

# Giao diện
st.set_page_config(page_title="FB MQTT Multi-Tab Sender", layout="wide")

st.title("Facebook MQTT Sender - Multi Tab / Multi Instance")
st.caption("Mỗi tab chạy độc lập • cookie, thread, message, delay riêng • log riêng")

if st.button("➕ Thêm Tab Mới", type="primary"):
    new_id = st.session_state.next_tab_id
    st.session_state.next_tab_id += 1
    st.session_state.active_tab = new_id
    st.rerun()

tab_names = [f"Tab {i}" for i in range(1, st.session_state.next_tab_id)]
if not tab_names:
    tab_names = ["Tab 1"]
    st.session_state.next_tab_id = 2

tabs = st.tabs(tab_names)

for idx, tab in enumerate(tabs):
    tab_id = idx + 1
    state = get_tab_state(tab_id)
    
    with tab:
        st.subheader(f"Tab {tab_id} - Cài đặt & Điều khiển")
        
        col1, col2 = st.columns([5, 3])
        
        with col1:
            cookies_text = st.text_area(
                "Danh sách Cookie (mỗi cookie 1 dòng)",
                value=state["cookies"],
                height=110,
                key=f"cookies_{tab_id}"
            )
            state["cookies"] = cookies_text

        with col2:
            state["delay"] = st.number_input(
                "Delay (giây)", min_value=0.3, value=state["delay"], step=0.5,
                key=f"delay_{tab_id}"
            )

        st.subheader("Danh sách Thread ID / Group ID (mỗi ID 1 dòng)")
        thread_ids_text = st.text_area(
            "Thread ID",
            value=state["thread_ids"],
            height=90,
            key=f"threads_{tab_id}"
        )
        state["thread_ids"] = thread_ids_text

        st.subheader("Nội dung tin nhắn")
        msg_type = st.radio(
            "Loại", ["Nhập trực tiếp", "Upload file .txt"],
            horizontal=True, key=f"msgtype_{tab_id}"
        )
        state["message_type"] = msg_type

        if msg_type == "Nhập trực tiếp":
            msg = st.text_area("Tin nhắn", value=state["message"], height=110, key=f"msg_{tab_id}")
            state["message"] = msg
        else:
            uploaded = st.file_uploader("Chọn file .txt", type=["txt"], key=f"upload_{tab_id}")
            if uploaded:
                try:
                    state["message"] = uploaded.read().decode("utf-8").strip()
                    st.success("Đã đọc file")
                except:
                    st.error("Không đọc được file")
                    state["message"] = ""

        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶️ BẮT ĐẦU", type="primary", disabled=state["running"], key=f"start_{tab_id}"):
                if not state["cookies"].strip():
                    st.error("Chưa nhập cookie!")
                elif not state["thread_ids"].strip():
                    st.error("Chưa nhập thread ID!")
                elif not state["message"].strip():
                    st.error("Chưa có nội dung tin nhắn!")
                else:
                    state["logs"] = []
                    state["threads"] = []
                    state["running"] = True
                    
                    cookies = [c.strip() for c in state["cookies"].splitlines() if c.strip()]
                    thread_ids = [t.strip() for t in state["thread_ids"].splitlines() if t.strip()]
                    
                    tab_log(tab_id, f"Bắt đầu • {len(cookies)} cookie • {len(thread_ids)} thread • delay {state['delay']}s")
                    
                    for i, cookie in enumerate(cookies):
                        if not state["running"]:
                            break
                        t = threading.Thread(
                            target=worker,
                            args=(i, cookie, thread_ids, state["message"], state["delay"], tab_id),
                            daemon=True
                        )
                        t.start()
                        state["threads"].append(t)
                        time.sleep(0.7)

        with c2:
            if st.button("⏹ DỪNG", disabled=not state["running"], key=f"stop_{tab_id}"):
                state["running"] = False
                tab_log(tab_id, "Yêu cầu dừng tất cả thread...", "warning")
                time.sleep(1.2)
                st.rerun()

        if st.button("🗑 Xóa log tab này", key=f"clearlog_{tab_id}"):
            state["logs"] = []
            st.rerun()

        st.subheader(f"Log - Tab {tab_id}")
        log_container = st.container(border=True, height=320)
        with log_container:
            if state["logs"]:
                for line in state["logs"][-60:]:
                    st.text(line)
            else:
                st.info("Chưa có log. Nhấn BẮT ĐẦU để chạy.")

any_running = any(s["running"] for s in st.session_state.tab_states.values())
if any_running:
    time.sleep(2.8)
    st.rerun()
