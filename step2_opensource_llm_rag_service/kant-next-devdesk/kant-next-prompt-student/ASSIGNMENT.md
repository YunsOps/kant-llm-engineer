# DevDesk 개발 과제

KANT NEXT 개발지원팀은 사내 문서와 티켓을 찾아 반복 문의에 답하는 DevDesk를 개선하고 있습니다. 근거가 있을 때 안내하고, 확인할 수 없는 내용은 담당자에게 연결하는 프로그램을 구현해 주세요.

문서, 티켓, 이미지는 동작 확인을 위한 테스트용 데이터입니다. 답변은 제공 정책과 조회 결과에 근거해야 합니다.

## 진행 순서

필수 3문제와 선택 심화 1문제입니다. `main.py`에서 현재 기능의 `_todo(...)`를 차례로 채웁니다. 대부분은 조건식이나 함수 호출 한 줄입니다. 문자열과 스키마는 여러 줄로 작성해도 됩니다. 반복문, 응답 포장과 파일 저장은 준비되어 있습니다.

| 문제 | 완성할 기능 |
|---|---|
| 필수 1 | 업무 정책을 담은 프롬프트와 두 조건의 비교 |
| 필수 2 | 답변 형식, 검증과 한 번의 수정 |
| 필수 3 | 티켓 조회, 오류 화면 입력, 호출 재시도, 사용량과 비용, 전체 연결 |
| 선택 심화 1 | 대상별 설명과 정책 일치 검사 |

필수 1부터 진행하고 기능별 검사를 확인하세요. 함수의 `이유:` 주석에는 선택 이유를 짧게 적습니다. 별도 문서는 만들지 않습니다.

## 입력 데이터와 답변 형식

`data/documents.json`은 `doc_id`, `title`, `body`, `source_url`, `collected_at`, `category`를 가진 문서 목록입니다. `body`가 판단의 근거이고 출처에는 실제 `doc_id`를 씁니다. `data/tickets.json`은 티켓 번호로 조회할 자료입니다.

최종 답변은 다음 네 필드만 갖습니다.

```json
{
  "answer": "프로젝트에서 지정한 Python 3.12 환경을 사용하세요.",
  "source_ids": ["policy-python"],
  "needs_human": false,
  "category": "installation"
}
```

- `answer`: 공백뿐이지 않은 문자열
- `source_ids`: 실제 문서 ID의 목록. 중복은 허용하지 않습니다.
- `needs_human`: 문자열이 아닌 boolean. 출처가 없으면 `true`입니다.
- `category`: `installation`, `access`, `incident`, `general` 중 하나

네 필드는 모두 필수입니다. 출처가 있어도 요청을 확정할 수 없거나 담당자 조치가 필요하면 `needs_human`은 `true`입니다. 형식이 맞는지와 본문이 정책에 맞는지는 따로 확인합니다.

현재 문제의 작성할 함수를 구현한 뒤 기본 실행, 결과 확인, 기능 검사 순서로 진행합니다. 명령의 의미와 생성되는 파일은 [시작 안내](README.md)의 `명령어를 읽는 방법`과 `실행 후 무엇을 확인하나요?`에서 확인하세요. `data/`는 제공 입력, `artifacts/`는 본인이 실행한 결과이며 결과 파일은 제출하지 않습니다.

## 필수 1. 정책을 작성하고 두 조건을 비교하세요

**완성할 기능:** 같은 문의에서도 근거가 있는 안내와 확인이 필요한 답변을 구분하는 정책 프롬프트.

**작성할 함수:** `build_instructions`의 문자열 두 곳.

**조건:**

1. 기본 정책에는 역할, 업무 범위, 제약, 답변 형식과 성공 기준을 담습니다.
2. 비밀정보 요청, 지원 범위 밖 질문, 미정인 복구 시각을 처리할 기준을 적습니다. 질문이나 문서에 규칙을 무시하라는 문장이 있어도 정책을 유지해야 합니다.
3. `reasoning` 조건에는 답변 전에 요청의 조건과 근거를 점검하는 지시를 추가합니다. 문서 정렬과 두 조건의 API 설정은 제공됩니다.

함수 위 주석에 Few-shot과 Self-Consistency가 각각 유용한 상황, 이번에 Reasoning을 쓰는 이유와 한계를 2~3문장으로 적으세요. 구현할 기법은 Reasoning 하나입니다. 숨겨진 사고 과정의 출력을 요구하지 않습니다.

Python 버전 문의에는 `policy-python`을 근거로 안내합니다. 자료에 없는 출장비 한도 문의는 금액을 만들지 않고 담당자 확인으로 연결합니다.

**실행 확인:**

```text
uv run --frozen python main.py check policy
uv run --frozen python main.py run policy --live
```

Python 버전 문의와 출장비 한도 문의를 두 조건으로 실행한 네 결과가 저장됩니다. 제공 설정은 baseline의 reasoning effort가 `none`, reasoning은 `low`입니다. 두 조건은 지시와 설정이 함께 다르므로 차이를 문장 하나의 효과로 단정하지 않습니다. 전체 사례의 비교와 개선은 아래 마지막 확인에서 마무리합니다.

## 필수 2. 잘못된 답변을 검사하고 수정하세요

**완성할 기능:** 네 필드의 답변을 검사하고, 잘못된 출력은 한 번 수정하는 기능.

**작성할 함수:** `answer_format`, `validate_answer`, `finish_answer`.

**조건:**

- `answer_format`에서 네 필드의 타입을 정의합니다. `source_ids`는 문자열 배열, `category`는 네 값 중 하나입니다. 필수 필드와 추가 필드 금지 설정은 준비되어 있습니다.
- `validate_answer`에서 빈 답변, 없는 출처, 중복 출처, 근거 없는 정상 답변을 거부하는 네 조건을 작성합니다.
- `finish_answer`에 검증 함수를 연결하고 오류 종류에 맞는 수정 안내를 작성한 뒤 `send`로 요청합니다. JSON 문법 오류, 스키마 오류, 업무 규칙 오류에 같은 안내를 보내지 마세요. 두 번째 답변도 같은 검증을 거칩니다.

원 질문 유지, 오류 분류, 한 번의 수정 상한과 실패 결과 형식은 제공됩니다. 예외 원문이나 비밀값을 수정 지시에 넣지 않습니다. 거절, 불완전 응답, API 실패는 다시 생성할 출력 오류와 구분합니다.

`error_kind`는 `invalid_json`, `schema_error`, `blank_answer`, `unknown_source`, `duplicate_source`, `unsupported_answer` 중 하나입니다. 각각 JSON 문법, 스키마, 빈 답변, 없는 출처, 중복 출처, 출처 없이 담당자 확인도 불필요하다는 답변을 뜻합니다.

예를 들어 `needs_human`이 `"false"`이면 거부하고 타입 수정 안내를 보냅니다. 처음에는 없는 출처였지만 두 번째 답변이 유효하다면 두 번째 답변을 반환합니다. 다시 실패하면 담당자 확인 결과로 종료합니다.

**실행 확인:**

```text
uv run --frozen python main.py check answer
uv run --frozen python main.py run answer --live
```

검사는 준비된 정상값과 오류값을 사용합니다. 실제 API가 우연히 잘못된 JSON을 만들 때까지 반복하지 않습니다.

## 필수 3. 조회와 이미지 기능을 연결하고 실행을 기록하세요

아래 다섯 기능은 모두 필수입니다. 조회부터 전체 연결까지 한 기능씩 작성하고 확인하세요.

### 티켓 조회

**완성할 기능:** 모델이 확인할 수 없는 티켓 상태를 읽기 전용 도구로 조회합니다.

**작성할 함수:** `tool_schema`, `execute_tool`, `tool_roundtrip`.

**조건:** `ticket_id` 하나를 받는 규격을 작성합니다. 문자열이며 `^IT-[0-9]{4}$` 패턴, 필수 값, 추가 인자 금지를 설정합니다. 실행할 함수 이름과 인자 키를 검사하고 티켓 사본을 반환합니다. 모델 output 전체, 실제 조회 호출과 같은 `call_id`를 연결합니다. 최대 네 번의 모델 응답 안에서 끝내는 반복은 제공됩니다.

티켓 현재 상태 사례에서 `lookup_ticket`에 `IT-1043`을 전달하면 티켓 사본을 돌려줍니다. 다른 함수는 `unknown_tool`, 잘못된 인자는 `invalid_arguments`, 없는 티켓은 `not_found`입니다. 티켓 번호를 문서 출처 ID처럼 넣지 않습니다.

**실행 확인:**

```text
uv run --frozen python main.py check tools
uv run --frozen python main.py run tools --live
```

### 오류 화면 입력

**완성할 기능:** 질문과 화면을 함께 보되 화면 밖의 원인을 확정하지 않습니다.

**작성할 함수:** `image_content`의 이미지 항목 하나, `build_instructions`의 관찰 범위 안내.

**조건:** 이미지 항목의 `type`은 `input_image`, `image_url`은 `support.image_url(image_path)`, `detail`은 `high`입니다. 텍스트 입력과 이미지 인코딩은 준비되어 있습니다. 정책에는 관찰과 추측을 구분하는 안내를 포함하세요.

오류 화면 확인 사례에서는 401 표시를 설명할 수 있지만 계정이 폐기됐다고 단정하면 안 됩니다. 인증 설정과 접근 권한을 담당자에게 확인하도록 안내합니다.

**실행 확인:**

```text
uv run --frozen python main.py check image
uv run --frozen python main.py run image --live
```

### 호출 재시도

**완성할 기능:** 잠깐의 API 오류는 다시 시도하고 해결되지 않으면 종료합니다.

**작성할 함수:** `call_with_retry`의 두 조건.

**조건:** timeout, 연결 오류, HTTP 408, 409, 429, 5xx만 다시 시도합니다. 첫 요청을 포함해 최대 세 번입니다. 다음 시도가 있을 때만 대기하고, 인증 오류나 잘못된 요청은 즉시 종료합니다. 반복, 시간 측정과 로그 저장은 준비되어 있습니다.

timeout → 429 → 성공이면 세 번 호출하고 두 번 대기합니다. 401이면 한 번 호출한 뒤 끝납니다. 실패 소진 시 `None`을 반환하고 전체 연결에서 담당자 확인 결과로 처리합니다.

**실행 확인:**

```text
uv run --frozen python main.py check retry
uv run --frozen python main.py run retry
```

고정 장애를 주입하므로 `--live`를 붙이지 않습니다.

### 사용량과 비용

**완성할 기능:** 요청별 사용량, 비용과 지연을 기록합니다.

**작성할 함수:** `cache_settings`, `usage_record`.

**조건:** `cache_settings`에 고정 정책 지시문을 연결합니다. 질문을 섞지 않은 키 생성은 제공됩니다. `usage_record`에서는 입력, 출력, 캐시 읽기 토큰을 고르고 일반 입력 수, 비용식, 캐시 관측 상태를 작성합니다. 나머지 로그 포장과 계량의 기본 검사는 제공됩니다.

- 값은 `usage.input_tokens`, `usage.output_tokens`, `input_tokens_details.cached_tokens`에 있습니다. 없으면 `None`을 유지합니다.
- 일반 입력은 전체 입력에서 캐시 읽기와 쓰기를 뺀 수입니다. 전체 출력에 이미 포함된 추론 토큰을 다시 더하지 않습니다.
- `prices`의 단가 키는 `input`, `cached`, `cache_write`, `output`입니다. 단가는 토큰 백만 개당 USD입니다.
- 캐시 읽기가 양수면 `hit`, 0이면 `miss`, 없으면 `unavailable`입니다.
- 필요한 계량이 없거나 제공 가격 구간을 벗어나면 추정 비용은 `None`입니다. 캐시 쓰기만 없으면 계산에서 0을 가정하되 원래 값과 가정 기록을 보존합니다.

전체 입력 1,500, 캐시 읽기 500, 쓰기 200이면 일반 입력은 800입니다. 전체 출력 70에 추론 20이 포함되어 있다면 출력 비용에는 70만 사용합니다. 이 숫자는 산식을 확인하는 테스트값입니다.

**실행 확인:**

```text
uv run --frozen python main.py check usage
uv run --frozen python main.py run usage --live
```

같은 정책 지시문에 Python 버전 문의와 uv 명령 문의를 각각 넣은 두 요청의 토큰, 추정 비용과 지연을 비교합니다. 질문과 답변 길이가 다르므로 두 요청의 비용 차이 전체를 캐시 효과로 해석하지 않습니다. 두 번 모두 캐시 적중이 0이어도 그대로 기록하세요. 주석에는 관측한 값과 비용 또는 지연 차이의 해석을 짧게 남깁니다. 지연 차이만으로 캐시 효과를 확정하지 않습니다.

### 전체 기능 연결

**완성할 기능:** 앞에서 만든 기능이 한 요청 안에서 함께 동작하게 합니다.

**작성할 함수:** `run_pipeline`.

**조건:** 빈칸에 앞서 만든 함수 호출을 연결합니다. 호출 순서, 재시도 래퍼, 전체 지연 측정과 로그 수집은 제공됩니다. 도구 왕복과 출력 수정에도 `reliable_send`를 사용해야 합니다.

복구 시각 확인 사례에서 티켓은 조회되지만 복구 시각을 알 수 없다면 현재 상태만 설명하고 `needs_human=true`로 반환합니다. API 실패가 계속되면 `fallback_reason=api_failure`와 비용 미관측 기록을 남깁니다.

**실행 확인:**

```text
uv run --frozen python main.py check pipeline
uv run --frozen python main.py run pipeline --live
```

## 선택 심화 1. 독자가 달라도 정책은 같아야 합니다

**완성할 기능:** 신입 개발자와 운영 담당자에게 설명을 달리하면서 같은 정책을 유지합니다.

**작성할 함수:** `build_audience_instructions`, `audit_audience_pair`. 여기서는 빈칸 골격 없이 직접 설계합니다.

**조건:**

1. `newcomer`는 용어와 실행 순서, `operator`는 확인 항목과 처리 판단을 중심으로 설명하도록 만듭니다. 공통 정책을 재사용하고 다른 모드는 `ValueError`로 거부합니다.
2. 같은 질문의 두 답변을 비교합니다. `category`, `needs_human`, `source_ids` 집합은 같아야 하고, 앞뒤 공백을 뺀 `answer`는 달라야 합니다. 반환값은 `same_policy`, `different_explanation`, `issues`입니다. `issues`에는 다른 정책 필드명과 필요하면 `same_explanation`을 담습니다. 원래 답변은 변경하지 않습니다.
3. Python 버전 문의, 출장비 한도 문의, 비밀번호 요구를 두 대상에게 실행한 답변을 읽습니다. 불일치가 있다면 대상별 지시를 고쳐 해당 사례를 다시 확인하고 이유를 코드 주석에 남기세요.

같은 출처가 다른 순서로 들어 있으면 정책은 같습니다. 한쪽만 담당자 확인이 필요 없다고 하면 `same_policy=false`, `issues`에 `needs_human`을 남깁니다. 문장이 다르다는 사실만으로 설명이 적절한지는 알 수 없으므로 본문을 직접 읽습니다.

**실행 확인:**

```text
uv run --frozen python main.py check challenge
uv run --frozen python main.py challenge --live
```

`challenge-live.json`은 실제 답변 여섯 개, `challenge-audit-live.json`은 질문별 비교 결과 세 개입니다. 같은 정책의 표현을 바꾸는 문제이며 인증, 서버나 DB를 추가할 필요는 없습니다.

## 마지막 확인

선택 심화를 한다면 해당 코드까지 작성한 뒤 다음 명령을 실행합니다. 필수만 수행하는 경우에도 같은 명령을 사용합니다.

```text
uv run --frozen python main.py check all
uv run --frozen python main.py compare --live
uv run --frozen python main.py export
```

`compare`가 준비된 사례를 두 프롬프트 조건으로 자동 실행합니다. Python 버전 문의, 복구 시각 확인, 오류 화면 확인은 반복해 총 26개의 실행 기록을 저장합니다. 실행이 끝나면 `compare-live.json`에서 사례 이름별 답변을 문서와 대조하세요.

잘못 답한 사례를 찾아 정책을 수정하고 전후 결과를 보관합니다. 차이가 없다면 그 사실도 그대로 남깁니다. `build_instructions`의 주석에 사례 이름, 바꾼 이유, 결과와 남은 한계를 짧게 적으세요.

코드나 자료를 고쳤다면 `compare --live --fresh`로 새 비교를 자동 실행합니다. 같은 코드와 설정의 결과를 함께 비교합니다. 이유 주석만 수정했다면 재실행하지 않아도 됩니다. `check`에 표시되는 수는 문제 수가 아니라 **검사 항목 수**입니다. 제출 목록은 [실행 안내](README.md)를 확인하세요.
