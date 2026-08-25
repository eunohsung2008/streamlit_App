# GitHub 업로드 안내 — 3학년 11반 웹사이트

## 가장 중요한 원칙

GitHub 저장소를 열었을 때 첫 화면에 `311`, `assets`, `data_store.py`,
`requirements.txt`, `schema.sql`이 바로 보여야 합니다. 저장소 안에
`streamlit_App` 폴더를 한 번 더 만들지 마세요.

```text
저장소 최상단
├── 311/
│   └── app.py
├── assets/
│   └── style.css
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── tests/
│   └── test_data_store.py
├── data_store.py
├── requirements.txt
├── schema.sql
├── README.md
├── GITHUB_UPLOAD_GUIDE.md
└── .gitignore
```

## 압축 파일을 이용한 업로드

1. 받은 ZIP 파일을 먼저 압축 해제합니다. ZIP 자체를 GitHub에 올려도
   GitHub가 자동으로 풀어 주지 않습니다.
2. 압축을 푼 폴더를 열어 위 구조의 파일과 폴더가 보이는지 확인합니다.
3. GitHub 저장소에서 **Add file → Upload files**를 누릅니다.
4. 압축을 푼 폴더 자체가 아니라, 그 **안에 들어 있는 항목들**을 모두
   선택해 업로드합니다.
5. 아래의 초록색 **Commit changes**를 누릅니다.

## GitHub에서 파일을 직접 만드는 경우

**Add file → Create new file**을 누른 뒤 파일 이름 칸에 `/`까지 포함한
전체 경로를 입력하면 폴더가 자동으로 만들어집니다.

- `311/app.py`
- `assets/style.css`
- `.streamlit/config.toml`

코드를 붙여 넣은 뒤 **Commit changes**를 눌러야 실제로 저장됩니다.

## 지금 발생한 CSS 오류만 빠르게 고치는 방법

1. GitHub 저장소 첫 화면으로 이동합니다.
2. `assets` 폴더가 없다면 **Add file → Create new file**을 누릅니다.
3. 파일 이름에 정확히 `assets/style.css`라고 입력합니다.
4. 제공된 `style.css` 내용을 붙여 넣고 **Commit changes**를 누릅니다.
5. Streamlit 앱을 열어 잠시 기다리거나 **Manage app → Reboot app**을
   누릅니다.

대소문자도 정확해야 합니다. `Assets`, `style.CSS`, `style.css.txt`는
다른 경로 또는 파일로 취급됩니다.

## 각 파일의 역할

| 경로 | 필요도 | 역할 |
| --- | --- | --- |
| `311/app.py` | 필수 | 학급 사이트 화면과 기능 |
| `data_store.py` | 필수 | Supabase 또는 로컬 데이터 저장 처리 |
| `assets/style.css` | 필수 권장 | 파스텔 색상과 카드 디자인 |
| `requirements.txt` | 필수 | Streamlit이 설치할 Python 패키지 목록 |
| `schema.sql` | 설정 시 필수 | Supabase 표와 이미지 버킷 생성 |
| `.streamlit/config.toml` | 권장 | 기본 색상과 업로드 용량 설정 |
| `.streamlit/secrets.toml.example` | 선택 | Secrets 입력 형식 예시이며 실제 키는 넣지 않음 |
| `.gitignore` | 권장 | 비밀값과 임시 파일의 실수 업로드 방지 |
| `README.md` | 권장 | 설치·배포·운영 설명 |
| `tests/test_data_store.py` | 선택 | 개발 중 저장 기능 검사 |

## 올리면 안 되는 것

- 실제 비밀값이 들어 있는 `.streamlit/secrets.toml`
- Supabase Secret key 또는 운영진 비밀번호가 적힌 파일
- `__pycache__` 폴더와 `.pyc` 파일
- `data` 폴더와 로컬 `.db` 파일
- 압축만 된 ZIP 파일

비밀값은 Streamlit Community Cloud의 **App settings → Secrets**에만
입력합니다.

```toml
SUPABASE_URL = "https://프로젝트주소.supabase.co"
SUPABASE_SERVICE_KEY = "Supabase의_secret_key"
ADMIN_PASSWORD = "직접_정한_운영진_비밀번호"
```

## Streamlit 배포 설정

```text
Repository: GitHub아이디/streamlit_App
Branch: main
Main file path: 311/app.py
```

저장소 이름은 Main file path에 다시 적지 않습니다.
