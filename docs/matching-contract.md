# Find you 매칭 모듈 계약 초안

서비스는 동네 목록, 등록, 공개 조회, 비공개 저장 및 반환 상태를 관리합니다. 팀 모듈은 원본 자료 정제, 특징 추출, 검색 인덱스, 후보 순위 및 품질 평가를 담당합니다. 아래 형식과 점수 정책은 팀 합의 대상입니다.

## 팀원 데이터 전달 형식

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
- 가져오기는 데이터셋별 명시적 매핑 `(dataset_id, location_code) → location_id`를 사용합니다. 가상 예시는 `MAPO-SEONGSAN → mapo-seongsan`, `MAPO-YEONNAM → mapo-yeonnam`, `MAPO-SANGAM → mapo-sangam`입니다. 미등록 코드는 검토 대기 상태로 두고 담당자가 동네 목록과 매핑을 확인합니다.
- 최초 가져오기에서 서비스가 `item_id`를 발급하고 `(dataset_id, record_id) → item_id`를 내부 매핑에 저장합니다. 같은 데이터셋·원본 ID를 다시 받으면 기존 행을 갱신합니다. 평가 때도 이 매핑으로 정답 ID를 변환합니다. 검색 인덱스와 내부 호출에는 서비스 `item_id`를 사용합니다.

## 내부 검색 호출

웹에서 받은 `location_id`, `category`, `features`를 서비스가 검증합니다. 실제 모듈 연동 시 서비스는 같은 동네·종류의 보관 중 습득물로 검색 범위 `eligible_found_item_ids`를 계산해 전달합니다. 빈 범위는 빈 후보로 처리합니다. 날짜 범위와 `top_k` 기본값은 평가 후 합의합니다.

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

서비스는 대상 ID와 현재 보관 상태를 다시 확인하고 팀과 합의한 임계값을 적용합니다. 웹에는 `{ "has_candidate": true }` 또는 `{ "has_candidate": false }`만 반환합니다. 모듈 오류나 타임아웃은 API 오류로 처리합니다. 후보 ID, 점수, 사진, 식별 특징은 내부 데이터입니다. MVP 호출 지점은 `backend/matching.py`의 `has_candidate`입니다.

## 인덱스 갱신 시점

습득물 신규 등록, 위치·종류·특징·사진 변경, 반환·삭제가 DB에 커밋된 뒤 해당 `item_id`의 인덱스를 갱신합니다. 보관 중인 행은 추가·수정하고 반환·삭제된 행은 제거합니다. 같은 ID의 작업은 재시도할 수 있게 하고 최신 데이터 버전을 확인해 역순 갱신을 방지합니다. 대량 가져오기와 모델 변경 뒤에는 전체 인덱스를 다시 구성합니다. MVP는 SQLite에서 가상 후보를 바로 확인합니다.
