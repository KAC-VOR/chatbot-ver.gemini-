import streamlit as st
from google import genai
from google.genai import types
import os

# [중요] 페이지 설정은 반드시 코드 최상단(import 바로 다음)에 한 번만 호출해야 합니다.
st.set_page_config(page_title="사내 지식 챗봇", layout="wide")


# --- 로그인 기능 ---
def check_password():
    """세션 상태를 확인하여 로그인 여부를 반환하고, 로그인 폼을 표시합니다."""
    # 이미 로그인했다면 True 반환
    if st.session_state.get("password_correct", False):
        return True

    # 로그인 폼 UI
    st.title("🔒 로그인이 필요합니다")
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")

    # 로그인 버튼 클릭 시 처리
    if st.button("로그인"):
        # Streamlit secrets에서 사용자 정보 확인
        if "passwords" in st.secrets and username in st.secrets["passwords"]:
            if st.secrets["passwords"][username] == password:
                st.session_state["password_correct"] = True
                st.rerun()  # 로그인 성공 시 페이지 새로고침
            else:
                st.error("비밀번호가 틀렸습니다.")
        else:
            st.error("등록되지 않은 아이디입니다.")

    return False

# 로그인에 성공하지 못했다면, 아래 코드를 실행하지 않고 여기서 멈춥니다.
if not check_password():
    st.stop()


# --- 챗봇 메인 로직 ---

# API 키 및 벡터 저장소 ID 설정
# Streamlit secrets에서 API 키를 가져옵니다.
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    # 경고: 로컬 테스트용 API 키입니다. GitHub에 푸시하기 전에 반드시 제거하거나 secrets으로 관리하세요.
    API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 질문 대상이 될 지식 저장소(Vector Store) ID 목록
VECTOR_STORE_IDS = {
    "인수인계서": "fileSearchStores/akeoiuo84m6g-rj6t83gogxzu",
    # "회사내규": "아직_ID가_없으므로_주석처리", # 예시: 새 저장소 추가
    "장비매뉴얼": "fileSearchStores/i4hjxqmty7uu-ecb1998kaknf"
}

# GenAI 클라이언트 초기화
client = genai.Client(api_key=API_KEY)


# --- 사이드바 UI ---
st.sidebar.title("🗂️ 지식 저장소 선택")

# 로그아웃 버튼
if st.sidebar.button("로그아웃"):
    st.session_state["password_correct"] = False
    st.rerun()

# 유효한 저장소만 필터링하여 라디오 버튼으로 표시
available_categories = [k for k, v in VECTOR_STORE_IDS.items() if "fileSearchStores" in v]
if not available_categories:
    st.error("설정된 지식 저장소가 없습니다. VECTOR_STORE_IDS를 확인해주세요.")
    st.stop()

selected_category = st.sidebar.radio("질문할 분야를 선택하세요:", available_categories)


# --- 메인 화면 UI ---
st.title(f"💬 {selected_category} 챗봇")
st.caption("업로드된 문서를 바탕으로 AI가 답변합니다.")

# 대화 기록 초기화 및 관리
# 선택한 카테고리가 변경되면 대화 기록을 초기화합니다.
if "messages" not in st.session_state or st.session_state.get("current_category") != selected_category:
    st.session_state.messages = []
    st.session_state.current_category = selected_category

# 이전 대화 기록을 화면에 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --- 질문 및 답변 처리 ---
if prompt := st.chat_input("궁금한 내용을 물어보세요..."):
    # 사용자 질문을 화면에 표시하고 대화 기록에 추가
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # AI 답변 생성
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🔍 문서를 검색하고 답변을 생성하는 중입니다...")

        try:
            store_id = VECTOR_STORE_IDS[selected_category]

            # Gemini 모델을 호출하여 콘텐츠 생성
            # 참고: gemini-2.5-flash 모델에서 오류 발생 시 'gemini-1.5-flash-002'로 변경하여 테스트
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

            # 답변을 화면에 표시하고 대화 기록에 추가
            full_response = response.text

            # [추가된 기능] 출처(Citation) 정보 추출 및 표시
            citations = []

            # 응답에 메타데이터(참고 정보)가 있는지 확인
            if response.candidates and response.candidates[0].grounding_metadata:
                metadata = response.candidates[0].grounding_metadata

                # 'grounding_chunks' 안에 참고한 파일 정보가 들어있음
                if metadata.grounding_chunks:
                    for chunk in metadata.grounding_chunks:
                        # 파일 이름 추출 (retrieved_context.title이 파일명)
                        if chunk.retrieved_context:
                            title = chunk.retrieved_context.title
                            # 중복 제거해서 리스트에 담기
                            if title and title not in citations:
                                citations.append(title)

            message_placeholder.markdown(full_response)

            # 출처가 있다면 답변 아래에 예쁘게 표시
            if citations:
                citation_text = "\n\n---\n**📚 참고한 문서:**\n"
                for doc in citations:
                    citation_text += f"- 📄 {doc}\n"

                # 화면에 출처 박스(Expander)로 보여주기
                with st.expander("📚 참고 문서 확인하기"):
                    for doc in citations:
                        st.write(f"📄 {doc}")

                # (선택) 대화 기록에 답변 + 출처 목록을 합쳐서 저장하고 싶다면:
                # full_response += citation_text

            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            # 오류 발생 시 사용자에게 친절한 메시지 표시
            if "NOT_FOUND" in str(e):
                error_msg = "모델을 찾을 수 없습니다. 코드에서 모델명을 'gemini-1.5-flash-002'로 변경해보세요."
            else:
                error_msg = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
            message_placeholder.error(error_msg)