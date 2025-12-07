import streamlit as st
from google import genai
from google.genai import types
import os

# [중요] 페이지 설정은 반드시 코드의 가장 맨 윗부분(import 바로 다음)에 딱 1번만 와야 합니다.
st.set_page_config(page_title="사내 지식 챗봇", layout="wide")


# ==========================================
# 🔐 [보안] 로그인 기능 구현
# ==========================================
def check_password():
    """아이디와 비밀번호를 확인하는 함수"""
    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 로그인이 필요합니다")

    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")

    if st.button("로그인"):
        if "passwords" in st.secrets and username in st.secrets["passwords"]:
            if st.secrets["passwords"][username] == password:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        else:
            st.error("등록되지 않은 아이디입니다.")

    return False


# 로그인을 통과하지 못하면 여기서 중단
if not check_password():
    st.stop()

# ==========================================
# 👋 [성공] 여기서부터 챗봇 메인 코드
# ==========================================

# 1. API 키 설정
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    # ⚠️ GitHub에 올릴 때는 반드시 이 부분을 지우거나 가짜 값으로 두세요!
    API_KEY = "xxxxxxxxxxxxxxxxxxxxx"
# 2. 저장소 ID 설정
VECTOR_STORE_IDS = {
    "인수인계서": "fileSearchStores/8scrfafyxnfi-u9i5vtvyrfoe",
    # "회사내규": "아직_ID가_없으므로_주석처리",
    "장비매뉴얼": "fileSearchStores/xqjyvxsq7rlp-4g8fuqnmt2x4"
}

# 클라이언트 초기화
client = genai.Client(api_key=API_KEY)

# (중복된 st.set_page_config 삭제됨)

# 사이드바 설정
st.sidebar.title("🗂️ 지식 저장소 선택")

# 로그아웃 버튼 추가 (선택사항)
if st.sidebar.button("로그아웃"):
    st.session_state["password_correct"] = False
    st.rerun()

available_categories = [k for k, v in VECTOR_STORE_IDS.items() if "fileSearchStores" in v]

if not available_categories:
    st.error("유효한 저장소 ID가 없습니다. 코드를 확인해주세요.")
    st.stop()

selected_category = st.sidebar.radio(
    "질문할 분야를 선택하세요:",
    available_categories
)

# 메인 화면
st.title(f"💬 {selected_category} 챗봇")
st.caption("업로드된 문서를 바탕으로 AI가 답변합니다.")

# 대화 기록 관리
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_category" not in st.session_state:
    st.session_state.current_category = selected_category

if st.session_state.current_category != selected_category:
    st.session_state.messages = []
    st.session_state.current_category = selected_category

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 질문 처리
if prompt := st.chat_input("궁금한 내용을 물어보세요..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🔍 문서를 검색하고 있습니다...")

        try:
            store_id = VECTOR_STORE_IDS[selected_category]

            # 모델 설정 (혹시 2.5 버전 오류가 나면 gemini-1.5-flash-002 로 변경하세요)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_id]
                            )
                        )
                    ]
                )
            )

            full_response = response.text
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            # 에러 메시지를 좀 더 친절하게 표시
            if "NOT_FOUND" in str(e):
                error_msg = "모델을 찾을 수 없습니다. 코드에서 모델명을 'gemini-1.5-flash-002'로 변경해보세요."
            else:
                error_msg = f"오류가 발생했습니다: {str(e)}"
            message_placeholder.error(error_msg)