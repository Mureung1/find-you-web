# Find you

동네를 기준으로 분실물과 습득물을 연결하는 웹서비스입니다. 첫 MVP에서는 가상 데이터로 공개 분실글 검색, 분실·습득 등록, 비공개 습득물의 후보 확인을 검증합니다.

## Windows PowerShell에서 실행

Node.js 24와 Windows용 CPython 3.12가 필요합니다. `py -3.12`가 없으면 설치한 Python 3.12 실행 파일 경로로 바꿔 주세요. PATH의 `python`을 쓸 때는 Windows용 CPython 3.12인지 확인하세요.

```powershell
node --version
py -3.12 --version
npm.cmd ci
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

터미널 두 개에서 다음 명령을 각각 실행합니다.

```powershell
# 터미널 1 · FastAPI
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
# 터미널 2 · Next.js
npm.cmd run dev -- --hostname 127.0.0.1
```

- 웹은 [http://127.0.0.1:3000](http://127.0.0.1:3000)에서 열립니다.
- API 상태는 [헬스 체크](http://127.0.0.1:8000/api/health), API 명세는 [FastAPI 문서](http://127.0.0.1:8000/docs)에서 확인할 수 있습니다.
- Next.js의 `/api/*` 요청은 기본적으로 `http://127.0.0.1:8000`에 전달됩니다. 포트를 바꾸면 Next.js를 실행하기 전에 `FIND_YOU_API_ORIGIN`을 지정하세요.
- SQLite는 기본적으로 `backend/data/find-you.sqlite3`에 저장됩니다. 독립 검증용 DB를 사용하려면 API 시작 전에 `$env:FIND_YOU_DB_PATH = 'temp/demo.sqlite3'`처럼 지정하세요.
- 프론트엔드 린트, 타입 검사, 빌드를 한 번에 실행하려면 `npm.cmd run check`를 사용합니다.

## Google 로그인 설정

Google Auth Platform에서 웹 애플리케이션용 OAuth Client ID를 만듭니다. 승인된 JavaScript 원본에 `http://localhost`와 `http://localhost:3000`을, 승인된 리디렉션 URI에 `http://localhost:3000/api/auth/google`을 추가합니다.

FastAPI를 시작하는 PowerShell에서 Client ID를 지정합니다. 기존 환경이라면 `pip install -r backend/requirements.txt`를 먼저 다시 실행합니다.

```powershell
$env:FIND_YOU_GOOGLE_CLIENT_ID = '발급받은 웹용 Client ID'
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

[로컬 로그인 페이지](http://localhost:3000/login)에서 확인합니다. 배포할 때는 `FIND_YOU_AUTH_ORIGIN`에 Google Cloud에 등록한 HTTPS 사이트 원본을 지정하고 해당 사이트의 `/api/auth/google` 리디렉션 URI를 등록합니다. Client ID를 설정하면 분실물과 습득물 등록에는 로그인이 필요하며, 서버는 작성자 ID를 내부에 저장합니다. Client ID를 생략하면 기존 가상 데이터 데모 방식으로 실행됩니다.

## 가상 데이터로 확인

동네 입력란에서는 `마포구 성산동`, `제주시 애월읍`처럼 시·군·구와 읍·면·동을 함께 검색하고 결과를 선택합니다. 모바일 분실물 등록에서 위치 권한을 허용하면, 포함된 경계에서 동네를 찾아 자동 선택합니다. **현재 위치로 동네 설정** 버튼으로 다시 시도할 수 있습니다. 휴대폰 Wi-Fi의 HTTP 데모에서는 직접 검색할 수 있으며, 모바일 GPS를 사용하려면 HTTPS 사이트가 필요합니다.

1. 홈에서 공개 분실글 전체를 확인합니다. 동네 필터에서 `서울 마포구 전체` 또는 `성산동`, `연남동` 같은 동네를 선택합니다. `이어폰`을 검색하고 물건 종류를 추가하면 검색어와 필터가 함께 적용됩니다. `망원동`에서는 결과가 비어 있으며 `검색·필터 초기화`로 전체 목록을 다시 열 수 있습니다.
2. 분실물을 각각 공개 동의와 비동의로 등록합니다. 공개에 동의한 글은 홈에서 검색할 수 있습니다.
3. 습득물 등록에서 물건 이름과 식별 특징을 입력합니다. 저장된 습득물과 사진용 가상 이미지 데이터는 서버 내부에서 관리합니다.
4. `특징으로 찾기`에서 `서울 마포구 성산동`, `생활용품`, `손잡이에 별 스티커`를 입력하면 **후보 있음**이 표시됩니다. 처음 생성한 DB에서 동네만 `연남동`으로 바꾸면 **후보 없음**이 표시됩니다. 결과는 데모이며, 가상 어댑터는 동네·종류·정규화한 특징이 일치하는 보관 중 습득물을 확인합니다.

이전 가상 장소로 등록한 글은 API를 재시작하면 해당 동네로 옮겨집니다. 기존 글과 비공개 사진은 SQLite에 보존됩니다.

전국 검색에는 [행정안전부 행정표준코드관리시스템](https://www.code.go.kr/stdcode/regCodeL.do)에서 2026-11-26 내려받은 현행 법정 읍·면·동 5,067곳을 사용합니다. GPS 경계는 [국토교통부·브이월드 전국 법정구역](https://www.data.go.kr/data/15029173/standard.do)의 2023-07-29 배포본을 가공한 [kr-admin-geojson](https://github.com/KnellBalm/kr-admin-geojson)을 현행 코드와 대조해 5,063곳에 연결했습니다. 화성시 새솔동·여울동과 병점구·동탄구 능동은 최신 경계 확인이 필요해 검색으로 선택할 수 있습니다. GPS 좌표는 동네 확인에만 사용하고 저장하지 않습니다. 데이터 갱신 시 코드 ZIP과 읍면동 GeoJSON을 `scripts/import-neighborhoods.py`에 전달해 두 서버 데이터를 다시 생성합니다.

`src/`에는 Next.js App Router·TypeScript·Tailwind 화면이, `backend/`에는 FastAPI·SQLite와 가상 매칭 어댑터가 있습니다. 팀원과 합의할 데이터와 검색 인터페이스는 [매칭 모듈 계약 초안](docs/matching-contract.md)에 정리했습니다.

## 다음 단계

- 사진 업로드와 비공개 저장·조회 권한
- 게시글 작성자·관리자 권한
- 소유권 확인, 반환 처리와 상태 갱신
- 실제 AI 매칭 모듈, 검색 인덱스 및 성능 평가 연결

현재 사진 저장 구조에는 가상 습득물 이미지 한 장을 시드로 넣었습니다. 반환 완료 카드는 가상 상태 예시입니다.

## 템플릿 출처

[JCodesMore/ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)에서 시작했습니다. 기준 커밋은 [`5426e0e2ec35dbc173a7a18f47a3dfe2a765313e`](https://github.com/JCodesMore/ai-website-cloner-template/commit/5426e0e2ec35dbc173a7a18f47a3dfe2a765313e)입니다. 원본 MIT 라이선스는 [LICENSE](LICENSE)에 포함되어 있습니다.
