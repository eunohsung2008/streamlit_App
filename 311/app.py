from __future__ import annotations

import hashlib
import hmac
import io
import logging
import os
import re
import secrets
import string
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st
from PIL import Image, UnidentifiedImageError

# Streamlit Community Cloud executes from the repository root even when the
# entrypoint is inside a subdirectory. Add that root explicitly so this app can
# reliably import shared modules and locate shared assets in both Cloud and
# local runs: streamlit run 311/app.py
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_store import LocalStore, SupabaseStore


APP_DIR = REPO_ROOT
KST = ZoneInfo("Asia/Seoul")
SUBJECTS = [
    "국어",
    "수학",
    "영어",
    "물리학",
    "화학",
    "생명과학",
    "지구과학",
    "사회탐구",
    "한국사",
    "제2외국어/한문",
    "기타",
]
DIFFICULTIES = ["가볍게", "보통", "도전"]
SUGGESTION_STATUSES = ["접수", "확인 중", "논의 중", "반영 완료", "답변 완료", "보류"]
MAX_IMAGE_BYTES = 4 * 1024 * 1024


st.set_page_config(
    page_title="3학년 11반",
    page_icon="🌼",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": "3학년 11반을 위한 학급 소통·학습 공간입니다.",
    },
)


def load_css() -> None:
    css_path = APP_DIR / "assets" / "style.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def secret_value(name: str, default: str = "") -> str:
    environment_value = os.environ.get(name)
    if environment_value is not None:
        return environment_value
    try:
        value = st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default
    return str(value) if value is not None else default


@st.cache_resource
def build_store(supabase_url: str, supabase_key: str):
    if supabase_url and supabase_key:
        return SupabaseStore(supabase_url, supabase_key)
    return LocalStore(APP_DIR / "data" / "classroom.db")


def data_error() -> None:
    logging.exception("Classroom data operation failed")
    st.error("자료를 처리하지 못했어요. 잠시 뒤 다시 시도하거나 운영진에게 알려주세요.")


def format_datetime(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KST)
        return parsed.astimezone(KST).strftime("%Y.%m.%d %H:%M")
    except ValueError:
        return str(value)


def escape_inline_markdown(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", str(text))


def normalize_lookup_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def hash_lookup_code(code: str) -> str:
    normalized = normalize_lookup_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def new_lookup_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def seconds_until_allowed(key: str, interval: int) -> int:
    last = float(st.session_state.get(key, 0.0))
    remaining = interval - (time.monotonic() - last)
    return max(0, int(remaining + 0.999))


def mark_submitted(key: str) -> None:
    st.session_state[key] = time.monotonic()


def prepare_image(uploaded_file: Any) -> tuple[bytes, str]:
    raw = uploaded_file.getvalue()
    if not raw:
        raise ValueError("빈 이미지 파일은 올릴 수 없어요.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("이미지는 한 장당 4MB 이하로 올려주세요.")

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.width * image.height > 25_000_000:
                raise ValueError("이미지 해상도가 너무 커요. 크기를 줄여 다시 올려주세요.")
            image.seek(0)
            mode = "RGBA" if "A" in image.getbands() else "RGB"
            cleaned = image.convert(mode)
            cleaned.thumbnail((1800, 1800))
            output = io.BytesIO()
            cleaned.save(output, format="WEBP", quality=86, method=6)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("PNG, JPG 또는 WEBP 이미지인지 확인해주세요.") from exc

    return output.getvalue(), "image/webp"


def render_site_header() -> None:
    st.markdown(
        """
        <section class="site-header">
          <div class="site-kicker">CLASS 3-11 · 2026</div>
          <div class="site-title-row">
            <div>
              <h1>3학년 11반</h1>
              <p>함께 듣고, 함께 배우고, 함께 나아가는 우리 반 공간</p>
            </div>
            <div class="header-bubbles" aria-hidden="true">
              <span>🌼</span><span>📚</span><span>💬</span>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_page_intro(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="page-intro">
          <div class="page-eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_notice_card(notice: dict[str, Any], compact: bool = False) -> None:
    pin = "📌 " if bool(notice.get("pinned")) else ""
    title = escape_inline_markdown(notice.get("title", "제목 없음"))
    with st.container(border=True):
        st.markdown(f"#### {pin}{title}")
        st.caption(
            f"{notice.get('author_role', '운영진')} · {format_datetime(notice.get('created_at'))}"
        )
        content = str(notice.get("content", ""))
        if compact and len(content) > 180:
            content = content[:180].rstrip() + "…"
        st.markdown(content)


def render_study_post(post: dict[str, Any]) -> None:
    title = str(post.get("title", "제목 없음"))
    subject = str(post.get("subject", "기타"))
    difficulty = str(post.get("difficulty", "보통"))
    label = f"{subject} · {difficulty}  |  {title}"
    with st.expander(label):
        st.caption(
            f"공유: {post.get('author_alias') or '익명'} · "
            f"{format_datetime(post.get('created_at'))}"
        )
        source = str(post.get("source", "")).strip()
        if source:
            st.caption(f"출처/문항 정보: {source}")

        st.markdown("##### 문제")
        st.markdown(str(post.get("problem", "")))
        if post.get("problem_image_url"):
            st.image(post["problem_image_url"], caption="문제 이미지", use_container_width=True)

        st.markdown("##### 풀이")
        st.markdown(str(post.get("solution", "")))
        if post.get("solution_image_url"):
            st.image(post["solution_image_url"], caption="풀이 이미지", use_container_width=True)


def home_page() -> None:
    st.markdown(
        """
        <section class="home-hero">
          <div class="hero-copy">
            <span class="soft-pill">우리 반 온라인 아지트</span>
            <h2>말은 편하게,<br>배움은 아낌없이.</h2>
            <p>필요한 소식은 놓치지 않고, 작은 의견도 안전하게 전하고,<br>
            좋은 문제와 풀이를 서로 나누는 공간이에요.</p>
          </div>
          <div class="hero-visual" aria-hidden="true">
            <div class="sun">☀️</div>
            <div class="book">📖</div>
            <div class="sparkle one">✦</div>
            <div class="sparkle two">✦</div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 우리 반 공간")
    col1, col2, col3 = st.columns(3)
    cards = [
        (col1, "📢", "알림장", "선생님과 회장단이 전하는 중요한 소식을 한눈에 확인해요."),
        (col2, "💌", "익명 건의함", "이름을 남기지 않고 의견을 전하고, 접수 코드로 답변을 확인해요."),
        (col3, "🧠", "문제 나눔", "과목과 상관없이 참신한 문제와 나만의 풀이를 함께 나눠요."),
    ]
    for column, icon, title, body in cards:
        with column:
            st.markdown(
                f"""
                <div class="feature-card">
                  <div class="feature-icon">{icon}</div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### 최근 소식")
    try:
        notices = store.list_notices(limit=3)
    except Exception:
        data_error()
        notices = []

    if not notices:
        st.info("아직 등록된 공지가 없어요. 첫 소식을 기다리고 있어요! 🌱")
    else:
        for notice in notices:
            render_notice_card(notice, compact=True)

    st.markdown("### 최근 문제 나눔")
    try:
        posts = store.list_study_posts(limit=3)
    except Exception:
        data_error()
        posts = []

    if not posts:
        st.info("첫 번째로 기억에 남는 문제와 풀이를 공유해보세요! ✏️")
    else:
        for post in posts:
            render_study_post(post)


def notices_page() -> None:
    render_page_intro(
        "NOTICE BOARD",
        "알림장",
        "선생님과 회장단이 전하는 학급 일정과 안내를 확인하세요.",
    )

    try:
        notices = store.list_notices(limit=100)
    except Exception:
        data_error()
        return

    if not notices:
        st.info("아직 등록된 공지가 없어요.")
        return

    for notice in notices:
        render_notice_card(notice)


def suggestions_page() -> None:
    render_page_intro(
        "ANONYMOUS VOICE",
        "익명 건의함",
        "말하기 어려웠던 작은 의견도 괜찮아요. 이름 없이 안전하게 전달해요.",
    )

    st.markdown(
        """
        <div class="privacy-note">
          <div class="privacy-icon">🫧</div>
          <div><strong>익명성 안내</strong><br>
          이름·학번·연락처 입력란을 두지 않으며, 데이터베이스에도 접속 IP를 저장하지 않아요.
          접수 후 발급되는 코드만 잘 보관해주세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    receipt = st.session_state.pop("suggestion_receipt", None)
    if receipt:
        st.success("건의가 익명으로 접수되었어요. 아래 코드는 다시 확인할 수 없으니 꼭 보관해주세요.")
        st.code(receipt, language=None)
        st.download_button(
            "접수 코드 저장하기",
            data=f"3학년 11반 익명 건의 접수 코드\n{receipt}\n",
            file_name="3-11_건의_접수코드.txt",
            mime="text/plain",
        )

    submit_tab, lookup_tab = st.tabs(["건의 남기기", "처리 상황 확인"])

    with submit_tab:
        with st.form("suggestion_form", clear_on_submit=True):
            category = st.selectbox(
                "분류",
                ["학급 생활", "수업/학습", "환경/시설", "행사/활동", "관계/분위기", "기타"],
            )
            title = st.text_input(
                "한 줄 제목",
                max_chars=80,
                placeholder="예: 자습 시간에 필요한 물품을 건의하고 싶어요",
            )
            content = st.text_area(
                "건의 내용",
                height=180,
                max_chars=2500,
                placeholder="상황과 바라는 점을 구체적으로 적어주면 더 잘 논의할 수 있어요.",
            )
            respectful = st.checkbox("서로를 존중하는 표현으로 작성했어요.")
            submitted = st.form_submit_button("익명으로 보내기", type="primary", use_container_width=True)

        if submitted:
            remaining = seconds_until_allowed("last_suggestion_submit", 20)
            if remaining:
                st.warning(f"연속 제출을 막기 위해 {remaining}초 뒤에 다시 보낼 수 있어요.")
            elif not title.strip() or not content.strip():
                st.warning("제목과 건의 내용을 모두 적어주세요.")
            elif not respectful:
                st.warning("존중하는 표현으로 작성했는지 확인해주세요.")
            else:
                code = new_lookup_code()
                try:
                    store.add_suggestion(
                        category=category,
                        title=title.strip(),
                        content=content.strip(),
                        lookup_hash=hash_lookup_code(code),
                    )
                except Exception:
                    data_error()
                else:
                    mark_submitted("last_suggestion_submit")
                    st.session_state["suggestion_receipt"] = code
                    st.rerun()

    with lookup_tab:
        st.caption("접수할 때 받은 12자리 코드를 입력하면 현재 상태와 운영진 답변을 볼 수 있어요.")
        with st.form("lookup_form"):
            lookup_code = st.text_input(
                "접수 코드",
                placeholder="ABCD-EFGH-JK23",
                max_chars=20,
            )
            lookup = st.form_submit_button("확인하기", use_container_width=True)

        if lookup:
            normalized = normalize_lookup_code(lookup_code)
            if len(normalized) != 12:
                st.warning("접수 코드 12자리를 확인해주세요.")
            else:
                try:
                    suggestion = store.get_suggestion_by_hash(hash_lookup_code(normalized))
                except Exception:
                    data_error()
                    suggestion = None

                if suggestion:
                    status = str(suggestion.get("status", "접수"))
                    st.markdown(f"#### 현재 상태: `{status}`")
                    st.caption(
                        f"{suggestion.get('category', '기타')} · "
                        f"{format_datetime(suggestion.get('created_at'))}"
                    )
                    st.markdown(f"**제목**  \n{escape_inline_markdown(suggestion.get('title', ''))}")
                    st.markdown("**내가 남긴 내용**")
                    st.markdown(str(suggestion.get("content", "")))
                    reply = str(suggestion.get("reply", "")).strip()
                    if reply:
                        st.markdown("**운영진 답변**")
                        st.info(reply)
                    else:
                        st.info("아직 등록된 답변은 없어요. 조금만 기다려주세요.")
                elif len(normalized) == 12:
                    st.warning("일치하는 건의를 찾지 못했어요. 코드를 다시 확인해주세요.")


def study_page() -> None:
    render_page_intro(
        "STUDY TOGETHER",
        "문제 나눔",
        "참신했던 문제, 친구에게도 권하고 싶은 문제와 자신만의 풀이를 공유해요.",
    )

    flash = st.session_state.pop("study_flash", None)
    if flash:
        st.success(flash)

    with st.expander("➕ 새로운 문제와 풀이 공유하기", expanded=False):
        st.caption("수식은 `$x^2+1$`처럼 달러 기호 사이에 적으면 보기 좋게 표시돼요.")
        with st.form("study_post_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                subject_choice = st.selectbox("과목", SUBJECTS)
                difficulty = st.selectbox("느낀 난이도", DIFFICULTIES, index=1)
            with col2:
                custom_subject = st.text_input(
                    "기타 과목명",
                    max_chars=20,
                    placeholder="과목에서 '기타'를 골랐을 때만 입력",
                )
                author_alias = st.text_input(
                    "작성자 표시 (선택)",
                    max_chars=20,
                    placeholder="비워두면 '익명'으로 표시",
                )

            title = st.text_input(
                "문제 제목",
                max_chars=80,
                placeholder="예: 조건을 거꾸로 해석해야 풀리는 미적분 문제",
            )
            source = st.text_input(
                "출처 또는 문항 정보 (선택)",
                max_chars=120,
                placeholder="예: 2026년 6월 모의평가 수학 22번 / 직접 만든 문제",
            )
            problem = st.text_area(
                "문제",
                height=170,
                max_chars=4000,
                placeholder="문제의 핵심 조건을 적어주세요. 이미지로 올린다면 간단한 설명만 적어도 좋아요.",
            )
            problem_image = st.file_uploader(
                "문제 이미지 (선택 · PNG/JPG/WEBP · 4MB 이하)",
                type=["png", "jpg", "jpeg", "webp"],
                key="problem_image",
            )
            solution = st.text_area(
                "풀이",
                height=220,
                max_chars=6000,
                placeholder="핵심 아이디어와 풀이 과정을 친구가 이해할 수 있게 적어주세요.",
            )
            solution_image = st.file_uploader(
                "풀이 이미지 (선택 · PNG/JPG/WEBP · 4MB 이하)",
                type=["png", "jpg", "jpeg", "webp"],
                key="solution_image",
            )
            copyright_ok = st.checkbox(
                "직접 정리한 풀이이며, 교재 전체 등 저작권 자료를 과도하게 올리지 않았어요."
            )
            submitted = st.form_submit_button("문제와 풀이 공유하기", type="primary", use_container_width=True)

        if submitted:
            subject = (
                custom_subject.strip()
                if subject_choice == "기타" and custom_subject.strip()
                else subject_choice
            )
            remaining = seconds_until_allowed("last_study_submit", 30)
            if remaining:
                st.warning(f"연속 제출을 막기 위해 {remaining}초 뒤에 다시 올릴 수 있어요.")
            elif not title.strip() or not problem.strip() or not solution.strip():
                st.warning("문제 제목, 문제 내용, 풀이를 모두 적어주세요.")
            elif subject_choice == "기타" and not custom_subject.strip():
                st.warning("기타 과목명을 입력해주세요.")
            elif not copyright_ok:
                st.warning("저작권과 직접 작성한 풀이 여부를 확인해주세요.")
            else:
                try:
                    post: dict[str, Any] = {
                        "subject": subject,
                        "title": title.strip(),
                        "difficulty": difficulty,
                        "problem": problem.strip(),
                        "solution": solution.strip(),
                        "source": source.strip(),
                        "author_alias": author_alias.strip() or "익명",
                    }

                    if problem_image is not None:
                        image_bytes, mime = prepare_image(problem_image)
                        image_url, image_path = store.save_image(image_bytes, mime, "problems")
                        post["problem_image_url"] = image_url
                        post["problem_image_path"] = image_path

                    if solution_image is not None:
                        image_bytes, mime = prepare_image(solution_image)
                        image_url, image_path = store.save_image(image_bytes, mime, "solutions")
                        post["solution_image_url"] = image_url
                        post["solution_image_path"] = image_path

                    store.add_study_post(post)
                except ValueError as exc:
                    st.warning(str(exc))
                except Exception:
                    data_error()
                else:
                    mark_submitted("last_study_submit")
                    st.session_state["study_flash"] = "문제와 풀이가 공유되었어요. 고마워요! 🌟"
                    st.rerun()

    try:
        posts = store.list_study_posts(limit=150)
    except Exception:
        data_error()
        return

    st.markdown("### 함께 보는 문제")
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])
    with filter_col1:
        query = st.text_input("검색", placeholder="제목·문제·풀이·출처에서 검색")
    with filter_col2:
        subject_filter = st.selectbox("과목 필터", ["전체"] + SUBJECTS[:-1])
    with filter_col3:
        difficulty_filter = st.selectbox("난이도 필터", ["전체"] + DIFFICULTIES)

    query_lower = query.strip().lower()
    filtered: list[dict[str, Any]] = []
    for post in posts:
        haystack = " ".join(
            str(post.get(field, ""))
            for field in ("title", "problem", "solution", "source", "subject")
        ).lower()
        if query_lower and query_lower not in haystack:
            continue
        if subject_filter != "전체" and post.get("subject") != subject_filter:
            continue
        if difficulty_filter != "전체" and post.get("difficulty") != difficulty_filter:
            continue
        filtered.append(post)

    st.caption(f"{len(filtered)}개의 문제가 보여요.")
    if not filtered:
        st.info("조건에 맞는 문제가 아직 없어요.")
    else:
        for post in filtered:
            render_study_post(post)


def admin_login() -> bool:
    if st.session_state.get("admin_authenticated"):
        return True

    configured_password = secret_value("ADMIN_PASSWORD")
    if not configured_password:
        st.info("관리자 비밀번호 설정이 필요해요. README의 배포 3단계를 따라 설정해주세요.")
        return False

    locked_until = float(st.session_state.get("admin_locked_until", 0.0))
    if time.monotonic() < locked_until:
        remaining = int(locked_until - time.monotonic()) + 1
        st.warning(f"로그인 시도가 잠시 제한되었어요. {remaining}초 뒤에 다시 시도해주세요.")
        return False

    with st.form("admin_login_form"):
        password = st.text_input("운영진 비밀번호", type="password")
        login = st.form_submit_button("로그인", type="primary", use_container_width=True)

    if login:
        if hmac.compare_digest(password, configured_password):
            st.session_state["admin_authenticated"] = True
            st.session_state["admin_failed_attempts"] = 0
            st.rerun()
        else:
            attempts = int(st.session_state.get("admin_failed_attempts", 0)) + 1
            st.session_state["admin_failed_attempts"] = attempts
            if attempts >= 5:
                st.session_state["admin_locked_until"] = time.monotonic() + 60
                st.session_state["admin_failed_attempts"] = 0
                st.warning("로그인 시도가 여러 번 실패해 1분 동안 잠겼어요.")
            else:
                st.error("비밀번호가 맞지 않아요.")
    return False


def admin_notices_tab() -> None:
    flash = st.session_state.pop("admin_notice_flash", None)
    if flash:
        st.success(flash)

    st.markdown("#### 새 공지 작성")
    with st.form("notice_create_form", clear_on_submit=True):
        role = st.selectbox("작성자", ["담임 선생님", "회장", "부회장"])
        title = st.text_input("제목", max_chars=80)
        content = st.text_area(
            "내용",
            height=200,
            max_chars=5000,
            help="목록, 굵은 글씨, 링크 등의 Markdown을 사용할 수 있어요.",
        )
        pinned = st.checkbox("상단에 고정하기")
        create = st.form_submit_button("공지 게시하기", type="primary", use_container_width=True)

    if create:
        if not title.strip() or not content.strip():
            st.warning("제목과 내용을 모두 적어주세요.")
        else:
            try:
                store.add_notice(title.strip(), content.strip(), role, pinned)
            except Exception:
                data_error()
            else:
                st.session_state["admin_notice_flash"] = "공지가 게시되었어요."
                st.rerun()

    st.markdown("#### 게시된 공지 관리")
    try:
        notices = store.list_notices(limit=100)
    except Exception:
        data_error()
        return

    if not notices:
        st.info("게시된 공지가 없어요.")
    for notice in notices:
        with st.container(border=True):
            col1, col2 = st.columns([6, 1])
            with col1:
                pin = "📌 " if notice.get("pinned") else ""
                st.markdown(f"**{pin}{escape_inline_markdown(notice.get('title', ''))}**")
                st.caption(
                    f"{notice.get('author_role')} · {format_datetime(notice.get('created_at'))}"
                )
            with col2:
                if st.button("삭제", key=f"delete_notice_{notice['id']}", use_container_width=True):
                    try:
                        store.delete_notice(int(notice["id"]))
                    except Exception:
                        data_error()
                    else:
                        st.rerun()


def admin_suggestions_tab() -> None:
    flash = st.session_state.pop("admin_suggestion_flash", None)
    if flash:
        st.success(flash)

    try:
        suggestions = store.list_suggestions(limit=300)
    except Exception:
        data_error()
        return

    status_filter = st.selectbox("상태별 보기", ["전체"] + SUGGESTION_STATUSES)
    if status_filter != "전체":
        suggestions = [item for item in suggestions if item.get("status") == status_filter]

    st.caption(f"{len(suggestions)}건의 건의가 보여요. 건의 내용은 운영진만 볼 수 있어요.")
    if not suggestions:
        st.info("조건에 맞는 건의가 없어요.")
        return

    for item in suggestions:
        title = str(item.get("title", "제목 없음"))
        status = str(item.get("status", "접수"))
        with st.expander(f"[{status}] {item.get('category', '기타')} · {title}"):
            st.caption(format_datetime(item.get("created_at")))
            st.markdown(str(item.get("content", "")))
            with st.form(f"suggestion_manage_{item['id']}"):
                selected_status = st.selectbox(
                    "처리 상태",
                    SUGGESTION_STATUSES,
                    index=SUGGESTION_STATUSES.index(status)
                    if status in SUGGESTION_STATUSES
                    else 0,
                )
                reply = st.text_area(
                    "익명 답변",
                    value=str(item.get("reply", "")),
                    max_chars=2000,
                    height=120,
                )
                save_col, delete_col = st.columns(2)
                save = save_col.form_submit_button("상태·답변 저장", type="primary", use_container_width=True)
                delete = delete_col.form_submit_button("건의 삭제", use_container_width=True)

            if save:
                try:
                    store.update_suggestion(int(item["id"]), selected_status, reply.strip())
                except Exception:
                    data_error()
                else:
                    st.session_state["admin_suggestion_flash"] = "처리 상태와 답변을 저장했어요."
                    st.rerun()
            if delete:
                try:
                    store.delete_suggestion(int(item["id"]))
                except Exception:
                    data_error()
                else:
                    st.session_state["admin_suggestion_flash"] = "건의를 삭제했어요."
                    st.rerun()


def admin_study_tab() -> None:
    flash = st.session_state.pop("admin_study_flash", None)
    if flash:
        st.success(flash)

    try:
        posts = store.list_study_posts(limit=300)
    except Exception:
        data_error()
        return

    st.caption(f"공유된 문제 {len(posts)}개 · 부적절하거나 중복된 글만 신중하게 삭제해주세요.")
    if not posts:
        st.info("공유된 문제가 없어요.")
        return

    for post in posts:
        with st.container(border=True):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(
                    f"**[{escape_inline_markdown(post.get('subject', '기타'))}] "
                    f"{escape_inline_markdown(post.get('title', ''))}**"
                )
                st.caption(
                    f"{post.get('author_alias') or '익명'} · {format_datetime(post.get('created_at'))}"
                )
            with col2:
                if st.button("삭제", key=f"delete_study_{post['id']}", use_container_width=True):
                    try:
                        store.delete_study_post(int(post["id"]))
                    except Exception:
                        data_error()
                    else:
                        st.session_state["admin_study_flash"] = "문제 게시글을 삭제했어요."
                        st.rerun()


def admin_page() -> None:
    render_page_intro(
        "CLASS ADMIN",
        "운영진 공간",
        "선생님과 회장단이 공지를 게시하고, 익명 건의와 문제 나눔을 관리해요.",
    )

    if not admin_login():
        return

    top_col1, top_col2 = st.columns([5, 1])
    with top_col1:
        st.success("운영진으로 로그인했어요.")
    with top_col2:
        if st.button("로그아웃", use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.rerun()

    notice_tab, suggestion_tab, study_tab = st.tabs(["공지 관리", "건의함 관리", "문제 관리"])
    with notice_tab:
        admin_notices_tab()
    with suggestion_tab:
        admin_suggestions_tab()
    with study_tab:
        admin_study_tab()


def render_footer() -> None:
    mode_text = "안정적 저장 연결됨" if store.backend_name == "supabase" else "로컬 체험 모드"
    st.markdown(
        f"""
        <footer class="site-footer">
          <span>3학년 11반 · 서로를 존중하는 우리 반</span>
          <span>{mode_text}</span>
        </footer>
        """,
        unsafe_allow_html=True,
    )


load_css()
store = build_store(secret_value("SUPABASE_URL"), secret_value("SUPABASE_SERVICE_KEY"))

home = st.Page(home_page, title="홈", icon="🏠", default=True, url_path="home")
notices = st.Page(notices_page, title="알림장", icon="📢", url_path="notices")
suggestions = st.Page(
    suggestions_page,
    title="익명 건의함",
    icon="💌",
    url_path="suggestions",
)
study = st.Page(study_page, title="문제 나눔", icon="🧠", url_path="study")
admin = st.Page(admin_page, title="운영진", icon="🔐", url_path="admin")

navigation = st.navigation([home, notices, suggestions, study, admin], position="top")
render_site_header()

try:
    store.healthcheck()
except Exception:
    logging.exception("Classroom data store healthcheck failed")
    st.error("데이터 저장소 연결을 확인해주세요. 처음 배포했다면 README의 Supabase 설정을 완료해주세요.")
    st.stop()

navigation.run()
render_footer()
