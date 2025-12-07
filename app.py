import streamlit as st
from google import genai
from google.genai import types
import os


# --------------------------------------------------------------------
# 1. API 키 설정 [사용자 설정 구간]
# --------------------------------------------------------------------
# 1. API 키를 입력하세요
if "GOOGLE_API_KEY" in st.secrets:
    # GitHub에 올린 뒤, Streamlit 서버에서 실행될 때는 여기서 키를 가져옵니다.
    API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    # 내 컴퓨터에서 테스트할 때는 이 키를 사용합니다. (따옴표 안에 키 입력)
    API_KEY = "xxxxxxxxxxxxx"

# --------------------------------------------------------------------
# 2. 저장소 ID 설정 (1단계 실행 결과로 나온 ID들을 복사해서 여기에 붙여넣으세요)
# (없는 항목은 비워두거나 줄을 지워도 됩니다)
# --------------------------------------------------------------------
VECTOR_STORE_IDS = {
    "인수인계서": "fileSearchStores/8scrfafyxnfi-u9i5vtvyrfoe",
    "회사내규": "fileSearchStores/여기에_복사한_ID_붙여넣기",
    "장비매뉴얼": "fileSearchStores/xqjyvxsq7rlp-4g8fuqnmt2x4"
}
# -----------------------

# 클라이언트 초기화 (New SDK)
client = genai.Client(api_key=API_KEY)

# 페이지 기본 설정
st.set_page_config(page_title="사내 지식 챗봇", layout="wide")

# 사이드바: 지식 저장소 선택
st.sidebar.title("🗂️ 지식 저장소 선택")
# ID가 있는(유효한) 카테고리만 선택지로 표시
available_categories = [k for k, v in VECTOR_STORE_IDS.items() if "fileSearchStores" in v]

if not available_categories:
    st.error("설정된 저장소 ID가 없습니다. app.py 코드를 열어 VECTOR_STORE_IDS를 수정해주세요.")
    st.stop()

selected_category = st.sidebar.radio(
    "질문할 분야를 선택하세요:",
    available_categories
)

# 메인 화면
st.title(f"💬 {selected_category} 챗봇")
st.caption("업로드된 문서를 바탕으로 AI가 답변합니다.")

# 세션 상태 초기화 (대화 기록 유지)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_category" not in st.session_state:
    st.session_state.current_category = selected_category

# 카테고리를 바꾸면 대화 내용 초기화
if st.session_state.current_category != selected_category:
    st.session_state.messages = []
    st.session_state.current_category = selected_category

# 이전 대화 내용 화면에 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 질문 입력
if prompt := st.chat_input("궁금한 내용을 물어보세요..."):
    # 1. 사용자 질문 표시
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. AI 답변 생성
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🔍 문서를 검색하고 있습니다...")

        try:
            # 선택된 카테고리의 저장소 ID 가져오기
            store_id = VECTOR_STORE_IDS[selected_category]

            # [핵심 수정] 최신 라이브러리(V1) 문법으로 답변 요청
            response = client.models.generate_content(
                model='gemini-2.5-flash',  # 속도가 빠르고 성능이 좋은 모델
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # 0에 가까울수록 사실 기반 답변
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_id]
                            )
                        )
                    ]
                )
            )

            # 답변 텍스트 추출
            full_response = response.text

            # 화면에 출력
            message_placeholder.markdown(full_response)

            # 대화 기록에 저장
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            error_msg = f"오류가 발생했습니다: {str(e)}"
            message_placeholder.error(error_msg)