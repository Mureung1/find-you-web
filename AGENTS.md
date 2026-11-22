<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Find you 개발 지침

- Find you는 동네를 기준으로 분실물과 습득물을 연결하는 한국어 웹서비스입니다.
- `src/`는 Next.js 16 App Router, React 19, TypeScript strict, Tailwind CSS v4를 사용합니다. 폼과 필터는 키보드로 조작할 수 있어야 하며 모바일에서 읽기 쉬워야 합니다.
- `backend/`는 Python 3.12, FastAPI, SQLite를 사용합니다. 게시글에는 고유 동네 키 `location_id`를 저장합니다. 상위 지역과 동 이름은 API의 동네 목록에서 불러옵니다.
- 공개 검색은 공개에 동의한 분실글만 반환합니다. 습득물 사진과 식별 특징은 서버 내부에서 관리합니다. 웹 후보 확인의 성공 응답은 `has_candidate` 하나를 반환합니다.
- 매칭 모듈 경계는 `backend/matching.py`에 두고 데이터 인터페이스를 바꿀 때 `docs/matching-contract.md`를 함께 갱신합니다.
- Windows PowerShell 실행 절차는 README를 따릅니다. 프론트엔드 변경은 `npm.cmd run check`로 확인하고, API 변경은 로컬 FastAPI와 별도 SQLite 파일에서 검증합니다.
