import streamlit as st
import google.generativeai as genai
import chromadb
import uuid
import json
import os  # <--- 確保這行在這裡！

# 網頁設定
st.set_page_config(page_title="多重宇宙 AI 系統", layout="wide")

# 設定檔檔名
ROLES_FILE = "my_roles_config.json"

# ==========================================
# 1. 設定檔讀寫邏輯
# ==========================================
def load_roles():
    if not os.path.exists(ROLES_FILE):
        default_roles = {
            "廢土傭兵": {
                "db_collection": "memory_mercenary",
                "avatar": "🐺",
                "char_setting": "你是一個名叫「雷」的流浪傭兵。說話冷酷、簡短。絕對不要承認自己是 AI。",
                "world_bg": "經歷了核戰的末日廢土世界。",
                "user_role": "剛來到營地的菜鳥。"
            }
        }
        with open(ROLES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_roles, f, ensure_ascii=False, indent=4)
        return default_roles
    
    with open(ROLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_roles(roles_data):
    with open(ROLES_FILE, "w", encoding="utf-8") as f:
        json.dump(roles_data, f, ensure_ascii=False, indent=4)

def auto_scribe_update(role_name, user_msg, ai_msg):
    """讓 AI 判斷是否需要更新角色設定或世界觀"""
    scribe_model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 建立一個專門給書記官的指令
    prompt = f"""
    你是劇本紀錄員。根據以下對話：
    玩家：{user_msg}
    角色：{ai_msg}
    
    請判斷是否有新的【角色特徵】、【重要人設】或【世界觀事實】出現？
    如果有，請以「條列式」簡短描述。如果沒有重要資訊，請回傳「無」。
    """
    
    res = scribe_model.generate_content(prompt)
    new_info = res.text.strip()
    
    if "無" not in new_info and len(new_info) > 2:
        # 將新資訊追加到目前的「世界觀」設定中
        ROLES[role_name]["world_bg"] += f"\n- {new_info}"
        save_roles(ROLES)
        return new_info
    return None

ROLES = load_roles()

@st.cache_resource
def get_chroma_client():
    return chromadb.PersistentClient(path="./my_ai_memory")

chroma_client = get_chroma_client()

# ==========================================
# 2. 側邊欄：安全金鑰與頻道控制
# ==========================================
with st.sidebar:
    st.header("🔑 系統啟動設定")
    user_api_key = st.text_input("輸入 Google API Key：", type="password")
    st.info("前往 [Google AI Studio](https://aistudio.google.com/app/apikey) 獲取金鑰。")
    
    if not user_api_key:
        st.warning("⚠️ 請輸入金鑰以開始使用。")
        st.stop()
    
    genai.configure(api_key=user_api_key)
    st.divider()

    st.header("🌌 頻道切換")
    channel_list = ["🎪 群聊大廳"] + list(ROLES.keys())
    selected_channel = st.selectbox("選擇頻道", channel_list)
    
    # 切換偵測
    if "current_channel" not in st.session_state:
        st.session_state.current_channel = selected_channel
    if selected_channel != st.session_state.current_channel:
        st.session_state.current_channel = selected_channel
        if "chat_session" in st.session_state: del st.session_state["chat_session"]
        if "group_history" in st.session_state: del st.session_state["group_history"]
        st.rerun()

    # 單人頻道管理
    if selected_channel != "🎪 群聊大廳":
        cur_cfg = ROLES[selected_channel]
        mem_coll = chroma_client.get_or_create_collection(name=cur_cfg["db_collection"])
        
        if st.button("🔄 清除短期記憶", use_container_width=True):
            if "chat_session" in st.session_state: del st.session_state["chat_session"]
            st.rerun()
            
        with st.expander("✏️ 編輯劇本設定"):
            new_char = st.text_area("🎭 角色性格", value=cur_cfg["char_setting"])
            new_bg = st.text_area("🌍 世界觀", value=cur_cfg["world_bg"])
            new_user = st.text_area("👤 你的角色", value=cur_cfg["user_role"])
            if st.button("💾 儲存並套用"):
                ROLES[selected_channel].update({"char_setting":new_char, "world_bg":new_bg, "user_role":new_user})
                save_roles(ROLES)
                if "chat_session" in st.session_state: del st.session_state["chat_session"]
                st.rerun()
                
        with st.expander("➕ 新增角色頻道"):
            new_n = st.text_input("名稱")
            if st.button("✅ 建立"):
                if new_n and new_n not in ROLES:
                    ROLES[new_n] = {"db_collection":f"mem_{uuid.uuid4().hex[:6]}", "avatar":"👤", "char_setting":"新設定", "world_bg":"", "user_role":""}
                    save_roles(ROLES); st.rerun()

# ==========================================
# 3. 聊天主畫面
# ==========================================
if selected_channel == "🎪 群聊大廳":
    st.title("🎪 群聊大廳")
    active_chars = st.multiselect("邀請角色：", list(ROLES.keys()))
    if "group_history" not in st.session_state: st.session_state.group_history = []
    
    for msg in st.session_state.group_history:
        with st.chat_message(msg["role"], avatar=msg["avatar"]):
            st.markdown(f"**{msg['name']}**：\n{msg['text']}")

    u_in = st.chat_input("發言...")
    if u_in:
        st.session_state.group_history.append({"role":"user", "name":"玩家", "text":u_in, "avatar":"👤"})
        st.rerun()

    if active_chars and st.session_state.group_history:
        cols = st.columns(len(active_chars))
        for i, char in enumerate(active_chars):
            if cols[i].button(f"讓 {char} 回話"):
                cfg = ROLES[char]
                p = f"角色：{cfg['char_setting']}\n歷史：\n"
                for m in st.session_state.group_history[-8:]: p += f"{m['name']}:{m['text']}\n"
                res = genai.GenerativeModel('gemini-2.5-flash').generate_content(p + f"\n{char}:")
                st.session_state.group_history.append({"role":"assistant", "name":char, "text":res.text, "avatar":cfg["avatar"]})
                st.rerun()
else:
    # --- 單人聊天邏輯 ---
    st.title(f"🤖 {selected_channel}")
    cur_cfg = ROLES[selected_channel]
    mem_coll = chroma_client.get_or_create_collection(name=cur_cfg["db_collection"])
    
    if "chat_session" not in st.session_state:
        sys_p = f"【角色】{cur_cfg['char_setting']}\n【背景】{cur_cfg['world_bg']}\n【你扮演】{cur_cfg['user_role']}"
        st.session_state.chat_session = genai.GenerativeModel('gemini-2.5-flash', system_instruction=sys_p).start_chat(history=[])

    for m in st.session_state.chat_session.history:
        role = "user" if m.role == "user" else "assistant"
        with st.chat_message(role, avatar="👤" if role=="user" else cur_cfg["avatar"]):
            st.markdown(m.parts[0].text.split("）\n\n")[-1])

    u_in = st.chat_input("說話...")
    if u_in:
        with st.chat_message("user", avatar="👤"): st.markdown(u_in)
        p_mem = ""
        if mem_coll.count() > 0:
            r = mem_coll.query(query_texts=[u_in], n_results=1)
            if r['documents'][0]: p_mem = f"（記憶：{r['documents'][0][0]}）\n\n"
        
       # 原有的 AI 回覆與顯示邏輯...
        with st.chat_message("assistant", avatar=cur_cfg["avatar"]):
            res = st.session_state.chat_session.send_message(p_mem + u_in)
            st.markdown(res.text)
            
            # --- 【新加入：自動書記官執行區】 ---
            with st.spinner("書記官正在記錄重要設定..."):
                update_log = auto_scribe_update(selected_channel, u_in, res.text)
                if update_log:
                    st.toast(f"📔 書記官已更新記憶：{update_log[:20]}...", icon="✍️")
            
            # 原有的 ChromaDB 存儲邏輯
            mem_coll.add(documents=[f"玩家:{u_in}/你:{res.text}"], ids=[str(uuid.uuid4())])
        
        st.rerun()