# 3학년 11반 학급 웹사이트

밝은 파스텔톤으로 만든 Streamlit 학급 웹사이트입니다. GitHub에 코드를 올리고 Streamlit Community Cloud로 배포할 수 있습니다.

## 들어 있는 기능

- **홈**: ‘3학년 11반’ 상단 배너, 공간 소개, 최근 공지·문제
- **알림장**: 선생님·회장단이 작성한 공지 열람, 중요 공지 상단 고정
- **익명 건의함**: 이름·학번 입력 없이 제출, 접수 코드로 처리 상태와 답변 확인
- **문제 나눔**: 과목·난이도별 문제와 풀이 공유, 검색·필터, 수식과 이미지 지원
- **운영진 공간**: 비밀번호 로그인 후 공지 작성, 건의 답변·상태 변경, 게시물 관리
- **안전한 설정**: 데이터베이스 키와 운영진 비밀번호를 GitHub 코드 밖의 Streamlit Secrets에 보관

## 배포 전 꼭 알아둘 점

Streamlit Community Cloud의 로컬 파일은 앱이 재시작되면 유지되지 않을 수 있습니다. 그래서 실제 학급 운영 때는 아래 순서대로 **무료 Supabase 데이터베이스**를 연결해야 합니다. Supabase 설정 없이 실행하면 기능 확인용 SQLite 로컬 체험 모드로 동작합니다.

## 1. GitHub에 올리기

1. 이 프로젝트 압축을 풀어 파일 구조를 그대로 둡니다.
2. GitHub에서 `streamlit_App` 저장소(repository)를 만듭니다.
3. `Add file` → `Upload files`를 눌러 압축을 푼 **폴더 안의 모든 항목**을 업로드합니다. ZIP 파일 자체나 바깥쪽 `streamlit_App` 폴더를 통째로 넣지 않습니다.
4. `.streamlit/secrets.toml.example`은 올려도 되지만, 실제 비밀값이 든 `.streamlit/secrets.toml`은 절대 올리지 않습니다. `.gitignore`가 이를 차단하도록 준비되어 있습니다.

GitHub 저장소의 첫 화면에 `311`, `assets`, `data_store.py`, `requirements.txt`, `schema.sql`이 바로 보여야 합니다. 자세한 화면별 방법은 `GITHUB_UPLOAD_GUIDE.md`를 확인하세요.

핵심 파일 구조는 다음과 같습니다.

```text
streamlit_App/
├── 311/
│   └── app.py
├── data_store.py
├── schema.sql
├── requirements.txt
├── README.md
├── assets/
│   └── style.css
├── tests/
│   └── test_data_store.py
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

## 2. Supabase 저장소 만들기

1. [Supabase](https://supabase.com/)에서 새 프로젝트를 만듭니다.
2. 왼쪽 메뉴의 **SQL Editor** → **New query**를 엽니다.
3. 이 프로젝트의 `schema.sql` 내용을 전부 복사해 붙여넣고 **Run**을 누릅니다.
4. 프로젝트 설정의 API 메뉴에서 다음 두 값을 확인합니다.
   - Project URL
   - `service_role` key 또는 새 형식의 server-side secret key

`service_role` 키는 데이터베이스 관리 권한이 있으므로 친구에게 보내거나 GitHub에 적지 마세요. 오직 다음 단계의 Streamlit Secrets에만 저장합니다.

## 3. Streamlit에 배포하기

1. [Streamlit Community Cloud](https://share.streamlit.io/)에 GitHub 계정으로 로그인합니다.
2. **Create app**에서 방금 만든 저장소와 브랜치를 선택합니다.
3. Main file path를 정확히 `311/app.py`로 설정합니다. 저장소 이름인 `streamlit_App`은 경로에 다시 적지 않습니다.
4. **Advanced settings**의 Secrets 칸에 아래 내용을 실제 값으로 바꾸어 붙여넣습니다.

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_KEY = "YOUR_SERVER_SIDE_SECRET_KEY"
ADMIN_PASSWORD = "길고_추측하기_어려운_운영진_비밀번호"
```

5. Deploy를 누릅니다. 이후 GitHub의 코드를 수정해 커밋하면 배포된 사이트에도 자동 반영됩니다.

## 4. 운영진 사용법

1. 사이트 상단의 **운영진** 페이지를 엽니다.
2. Streamlit Secrets에 설정한 `ADMIN_PASSWORD`로 로그인합니다.
3. 공지 작성, 익명 건의 확인·답변, 문제 게시글 관리를 할 수 있습니다.

비밀번호는 담임 선생님과 필요한 회장단에게만 전달하고, 외부에 알려졌다면 Streamlit 앱 설정에서 즉시 바꾸세요.

## 로컬에서 먼저 실행하기

Python이 설치된 컴퓨터에서 프로젝트 폴더를 연 뒤 다음 명령을 실행합니다.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run 311/app.py
```

macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run 311/app.py
```

Supabase 없이도 SQLite 체험 모드로 열립니다. 운영진 화면도 확인하려면 `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사한 후 `ADMIN_PASSWORD`만 원하는 값으로 바꾸고, Supabase 두 줄은 삭제하세요.

## 테스트

프로젝트 폴더에서 다음 명령을 실행하면 로컬 데이터 저장 기능을 검사합니다.

```bash
python -m unittest discover -s tests -v
```

## 개인정보·운영 안내

- 앱의 건의 양식은 이름, 학번, 연락처, 접속 IP를 데이터베이스에 저장하지 않습니다. 다만 인터넷 서비스 제공자나 호스팅 플랫폼은 일반적인 보안 로그를 별도로 처리할 수 있습니다.
- 접수 코드는 원문이 아닌 SHA-256 해시로 저장합니다. 코드를 잃어버리면 운영진도 같은 코드를 복구할 수 없습니다.
- 업로드 이미지는 WEBP로 다시 저장해 위치 정보 등 사진 메타데이터를 제거하고, 한 장당 4MB 및 최대 해상도를 제한합니다.
- 운영진 비밀번호는 브라우저 세션마다 확인되며, 5회 연속 실패하면 잠시 로그인이 제한됩니다.
- 문제를 올릴 때 교재 전체 페이지나 유료 자료를 그대로 공유하지 말고, 출처·문항 번호와 풀이에 필요한 범위만 사용하세요.

## 디자인 바꾸기

- 상단 문구와 페이지 내용: `311/app.py`
- 파스텔 색상과 카드 모양: `assets/style.css`
- Streamlit 기본 테마: `.streamlit/config.toml`
