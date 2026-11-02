# 제공 자료 설명

`release_pages.json`은 실제 GitHub 수집 결과가 아닌 테스트용 데이터입니다. 실제 릴리스 버전이나 배포 사실을 나타내지 않습니다. 정책의 `.invalid` 주소는 테스트용 출처 표시이며 접속 대상이 아닙니다.

## 파일과 용도

| 파일 | 용도 |
|---|---|
| documents.json | 정책 6개. 기존 ID와 여섯 필드로 구성 |
| release_pages.json | 자료 수집의 고정 HTTP 응답과 문서 정제의 분류 확인. 두 페이지에 각 5행 |
| query_example.json | policy-python 한 개를 선택하는 질의 예시 |
| snapshot_before.json, snapshot_after.json | 선택 심화에서 비교할 테스트용 전체 스냅샷. 두 파일의 비교 범위는 같음 |

## 고정 자료의 기대 분류

### 원천 필드 규칙

| 필드 | 규칙 |
|---|---|
| id | boolean을 제외한 양의 정수 |
| draft, prerelease | 둘 다 boolean. 문자열 false는 형식 오류 |
| name | 문자열을 정리해 사용. 누락, null, 공백뿐이면 tag_name 사용. 숫자 등 다른 자료형은 격리 |
| tag_name | 제목 대체에 사용할 때 비어 있지 않은 문자열 |
| body | 정리한 뒤 비어 있지 않은 문자열. 제목으로 대신하지 않음 |
| html_url | 앞뒤 공백을 정리한 HTTP(S) URL. API의 내부 url 필드와 구분 |
| published_at | 시간대가 있는 ISO8601 게시시각. 원래 값을 품질 기록에 보존 |

초안이나 프리릴리스는 내용 검사 전에 제외합니다. 내용이 유효한 행만 ID를 채택합니다.

아래는 자료의 위치와 기대 결과이며, 각각 별도의 문제가 아닙니다.

| 확인할 입력 | 분류 | 사유 코드 | 원천 위치 (페이지/행/ID) |
|---|---|---|---|
| 정상 릴리스 | 채택 | 없음 | 1/1/101 |
| 비어 있는 제목을 tag_name으로 보완 | 채택 | 없음 | 1/2/102 |
| 빈 본문 | 격리 | empty_body | 1/3/103 |
| 제목의 자료형 오류 | 격리 | invalid_name | 1/4/104 |
| 초안 | 제외 | draft | 1/5/105 |
| 앞서 채택한 ID의 중복 | 격리 | duplicate_id | 2/1/101 |
| 프리릴리스 | 제외 | prerelease | 2/2/106 |
| 본문의 자료형 오류 | 격리 | invalid_body | 2/3/109 |
| 잘못된 행 뒤에 온 같은 ID의 정상 행 | 채택 | 없음 | 2/4/109 |
| 게시시각 오류 | 격리 | invalid_published_at | 2/5/107 |

입력 10 = 채택 3 + 격리 5 + 제외 2입니다. 정책을 합친 기본 fixture 서버 문서는 9개입니다. 이 건수는 테스트용 자료에만 적용합니다. 실제 수집 건수, 릴리스 ID와 내용은 달라질 수 있습니다.

행은 각 페이지에서 1부터 셉니다. 원천 객체를 변경하지 말고 격리와 제외 기록에 page, row, id, reason을 남깁니다. quality_report의 records에 published_at 원문과 분류를 추적합니다. 문서 collected_at은 수집 시각으로 별도 기록합니다.

## 정제 규칙과 길이

제목 300자, 본문 20,000자, URL 2,048자, doc_id 100자가 상한입니다. doc_id에는 영문, 숫자, 하이픈과 밑줄만 사용합니다. 정리한 문자열에 적용하며 초과한 자료를 조용히 잘라 쓰지 않습니다. 양의 정수 ID여도 생성한 release-uv-{id}가 100자를 넘으면 invalid_id로 격리합니다. API 문서 등록도 같은 규칙을 사용합니다. URL은 앞뒤 공백을 제거하고 내부 공백은 거부합니다.

`html.unescape`로 entity를 바꾸고 p, br, div, b, strong, em, code, span, li, ul, ol의 단순 태그만 공백으로 치환합니다. 이후 연속 공백을 정리합니다. 태그 사이 단어가 붙지 않아야 합니다. `<T>` 같은 다른 텍스트를 임의로 지우는 범용 HTML 제거 규칙은 요구하지 않습니다.

사유 코드: invalid_object, invalid_id, invalid_flags, draft, prerelease, invalid_name, missing_title, invalid_body, empty_body, invalid_url, invalid_published_at, title_too_long, body_too_long, duplicate_id. 오류가 겹치면 과제의 분류 순서를 따릅니다.

## 실행 파일 형식

이 구조와 저장 순서는 제공 코드에 있습니다. 내용 확인이나 오류 추적이 필요할 때 참고하세요.

| 파일 | 내용 |
|---|---|
| raw_pages.json | `[{"page": 1, "items": [...]}, ...]`. 성공한 페이지의 원본 객체 |
| collection_report.json | mode, source, collected_at, successful_pages, raw_count, success, failed_page, limited, error |
| documents.json | 채택한 여섯 필드 문서 목록 |
| quarantine.json, excluded.json | page, row, id, reason을 가진 격리/제외 목록 |
| quality_report.json | input_count, kept_count, quarantine_count, excluded_count와 모든 행의 records |

successful_pages는 성공한 페이지 수이며 raw_count는 그 페이지의 전체 행 수입니다. 실패 페이지나 오류가 없으면 failed_page와 error는 null입니다. records에는 page, row, id, published_at, status, reason이 있습니다. 제공 실행부가 collection_sha256을 추가해 현재 원천과 정제 파일이 같은 실행에서 나온 것인지 확인합니다. 수집을 다시 실행했다면 같은 모드에서 정제도 다시 실행하세요.

## 선택 심화 비교

장애 문의와 티켓 조회(policy-incident)는 added, uv 설치와 프로젝트 동기화(policy-uv)는 changed(body), Python 버전과 실행 환경(policy-python)은 unchanged, API 키와 로그 처리(policy-secret)는 missing입니다. Python 문서는 collected_at만 바뀌었습니다. missing은 이 스냅샷에 없다는 뜻이며 실제 회사 문서의 삭제 사실이 아닙니다. 실제 GitHub의 제한된 두 페이지를 완전한 이력으로 간주하지 않습니다.
