# Find you 매칭 모듈 계약

서비스는 동네 목록, 등록, 공개 조회, 비공개 저장 및 반환 상태를 관리합니다. 팀 모듈은 원본 자료 정제, 특징 추출, 검색 인덱스, 후보 순위 및 품질 평가를 담당합니다.

## 팀의 2026-11-23 자료

팀 ZIP의 `data/export`에는 포털기관·경찰관서 습득물 23,255건, 개인정보를 가린 사진 6,448장과 합성 평가 509건이 있습니다. 원본 API 응답, 정제한 레코드와 텍스트·사진 벡터 인덱스는 ZIP의 별도 디렉터리에 있습니다. 가리기 전 원본 사진은 팀 ZIP에 포함되지 않습니다. 팀은 사전학습 모델인 ko-sroberta-multitask와 OpenCLIP으로 글과 사진을 벡터로 변환했습니다.

팀 자료의 `items.json`은 `items`를 포함하는 객체이고, `eval_cases.json`은 `cases`를 포함하는 객체입니다. 법정동 코드와 현재 보관 상태가 없어 서비스의 소유 확인·반환용 DB에는 직접 넣지 않습니다. 아래 명령은 답이 없는 사례의 `exclude_item_ids`를 적용해 전체 자료의 텍스트 검색을 평가합니다. 텍스트가 있는 409건을 사용하고 사진 전용 100건은 건너뜁니다. 이 결과는 동네 필터가 적용된 서비스의 정확도와 구분해 해석합니다.

```powershell
& .\.venv\Scripts\python.exe -m backend.team_evaluation --source temp/team-export
& .\.venv\Scripts\python.exe -m backend.team_evaluation --source temp/team-export --text-model temp/team-text-model
```

두 번째 명령에는 CPU용 PyTorch와 Sentence Transformers가 필요합니다. [한국어 모델의 고정 버전](https://huggingface.co/jhgan/ko-sroberta-multitask/tree/8fca7c9c98c26599be0e14b9916b11a756a26f19)에서 토크나이저, 모듈 설정, `model.safetensors`를 준비합니다. 같은 폴더를 FastAPI의 `FIND_YOU_TEXT_MODEL_PATH`에 지정하면 서비스 DB에서 동일 동네·종류의 습득물에 한해 텍스트 의미 비교를 시험할 수 있습니다. 모델은 서버에서 한 번 로드하고 텍스트는 로컬에서 처리합니다. 시험 임계값은 0.90입니다. 기본 실행에서는 어절 순서와 문자열 유사도를 비교합니다.

```powershell
& .\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch>=2.6,<3'
& .\.venv\Scripts\python.exe -m pip install 'sentence-transformers>=5.1,<6'
```

전체 자료의 정답 있는 300건 중 상위 5개에 정답을 포함한 건수는 키워드 96건, 의미 모델 91건이었습니다. 후보 반환 기준을 적용하면 키워드는 정답 없는 109건 중 106건에 후보를 반환했고, 의미 모델은 1건에 후보를 반환했습니다. 의미 모델은 정답이 있는 경우에도 300건 중 1건에만 후보를 반환해 미리보기의 기본 설정은 유지했습니다.

## 서비스에 가져올 데이터 형식

내부 보관 상태와 정확한 동네를 확인한 데이터를 다음 형식으로 준비합니다. `temp` 아래 별도 DB를 쓰면 기존 서비스 DB와 분리할 수 있습니다.

```powershell
& .\.venv\Scripts\python.exe -m backend.team_data import --db temp/match-qa.sqlite3 --dataset qa --source temp/service-data
& .\.venv\Scripts\python.exe -m backend.team_data evaluate --db temp/match-qa.sqlite3 --dataset qa --source temp/service-data
```

### items.json

UTF-8 JSON 배열입니다. 원본 레코드마다 한 객체를 전달합니다. `record_id`는 데이터셋 안에서 고유하고 재전달할 때 유지합니다. `image_paths`는 상대 경로 배열이며 사진이 없으면 빈 배열입니다. `event_date`는 한국 기준 `YYYY-MM-DD`입니다.

```json
[
  {
    "record_id": "source-found-001",
    "kind": "found",
    "location_code": "MAPO-SEONGSAN",
    "category": "accessory",
    "title": "접이식 우산",
    "event_date": "2026-11-21",
    "features": "손잡이에 별 스티커",
    "image_paths": ["images/source-found-001/01.jpg"]
  }
]
```

`kind`는 `lost` 또는 `found`입니다. `category`는 `electronics`, `wallet`, `card`, `accessory`, `clothing`, `bag`, `other` 중 하나입니다. 서비스 가져오기 시 원본 분실글의 공개 동의는 별도로 확인합니다. 습득글은 항상 비공개입니다.

### images/

`items.json`과 같은 루트에 둡니다. 레코드별 하위 폴더를 권장하며, `image_paths`의 순서를 사진 순서로 사용합니다. JPEG·PNG·WebP를 전달하고 실제 파일 형식과 확장자를 일치시킵니다. 서비스는 루트 내부의 참조만 허용하고 습득물 사진은 접근 제한 저장소에서 관리합니다.

### eval_cases.json

UTF-8 JSON 배열입니다. 테스트 질의는 원본 공간의 `location_code`를, 정답은 원본 습득물 `record_id`를 사용합니다. 빈 정답 배열은 후보가 없는 사례입니다. 학습·튜닝에 사용한 데이터와 평가 케이스를 구분합니다.

```json
[
  {
    "case_id": "umbrella-seongsan-hit",
    "query": { "location_code": "MAPO-SEONGSAN", "category": "accessory", "features": "손잡이에 별 스티커" },
    "expected_found_record_ids": ["source-found-001"]
  },
  {
    "case_id": "umbrella-yeonnam-miss",
    "query": { "location_code": "MAPO-YEONNAM", "category": "accessory", "features": "손잡이에 별 스티커" },
    "expected_found_record_ids": []
  }
]
```

## 동네와 물건 ID 연결

- 서비스 동네의 기준 키는 `location_id`입니다. 모든 동네는 상위 지역명 `region`과 동 이름 `dong`을 가집니다. 같은 동 이름이라도 상위 지역이 다르면 별도의 ID를 부여합니다.
- 전국 법정 읍·면·동은 행정표준코드의 10자리 문자열을 키로 사용합니다. 기존 서울 데모 동네 5곳은 저장된 게시글과의 호환성을 위해 기존 키를 유지합니다. `POST /api/locations/nearby`는 브라우저가 허용한 위도·경도로 일치하는 동네를 찾고 `location_id`, `region`, `dong`을 반환합니다. GPS 좌표는 매칭 모듈에 전달하거나 저장하지 않습니다.
- 가져오기는 법정동 코드와 기존 가상 예시 코드 `MAPO-SEONGSAN`, `MAPO-YEONNAM`, `MAPO-SANGAM`을 인식합니다. 팀에서 별도 코드를 쓰면 `--location-map`으로 코드와 서비스 `location_id`를 연결하는 JSON 객체를 지정합니다. 알 수 없는 코드가 있으면 가져오기 전체가 취소됩니다.
- 최초 가져오기에서 서비스가 `item_id`를 발급하고 `(dataset_id, record_id) → item_id`를 내부 매핑에 저장합니다. 같은 데이터셋·원본 ID를 다시 받으면 기존 행을 갱신합니다. 평가 때도 이 매핑으로 정답 ID를 변환합니다. 검색 인덱스와 내부 호출에는 서비스 `item_id`를 사용합니다.

## 내부 검색 호출

웹에서 받은 `location_id`, `category`, `features`를 서비스가 검증합니다. 검색 범위는 같은 동네·종류의 보관 중 습득물입니다. 소유 확인 승인으로 반환을 기다리는 물건은 제외합니다. 내부 상위 후보는 최대 5건입니다. 아래 형식은 별도 매칭 서버를 연결할 때 사용할 내부 호출 예시입니다.

```json
{
  "location_id": "mapo-seongsan",
  "category": "accessory",
  "features": "손잡이에 별 스티커",
  "eligible_found_item_ids": ["demo-found-01"],
  "top_k": 5
}
```

팀 모듈은 범위 안의 서비스 습득물 ID와 점수를 높은 점수순으로 반환합니다. 점수는 유한한 0~1 값이며, 동률은 `item_id` 오름차순으로 정렬하는 초안입니다.

```json
{
  "candidates": [{ "found_item_id": "demo-found-01", "score": 0.92 }]
}
```

서비스는 현재 보관 상태를 확인하고 임계값을 적용합니다. 웹의 후보 조회는 `{ "has_candidate": true }` 또는 `{ "has_candidate": false }`만 반환합니다. 후보 ID, 점수, 사진, 식별 특징은 내부 데이터입니다. 로그인한 사용자가 제출한 소유 확인 설명과 실제 후보는 담당자가 검토합니다. 매칭 진입점은 `backend/matching.py`의 `has_candidate`입니다.

## 인덱스 갱신 시점

현재 사이트는 조회 시 SQLite에서 대상과 상태를 읽습니다. 별도 인덱스를 연결할 때는 습득물 신규 등록, 위치·종류·특징·사진 변경, 반환·삭제가 커밋된 뒤 해당 `item_id`를 갱신합니다. 보관 중인 행은 추가·수정하고 반환·삭제된 행은 제거합니다. 최신 데이터 버전을 확인하고 대량 가져오기나 모델 변경 뒤에는 전체 인덱스를 다시 구성합니다.
