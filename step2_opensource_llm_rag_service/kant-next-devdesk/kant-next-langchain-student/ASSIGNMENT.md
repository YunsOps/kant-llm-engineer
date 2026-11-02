# 문서와 대화를 연결하는 DevDesk

KANT NEXT 개발지원팀은 문서를 찾아 답하고 후속 질문도 이어서 처리하는 DevDesk를 만들고 있습니다. 검색, 답변 생성, 대화 이력과 실패 처리를 연결해 주세요.

**필수 5문제와 선택 심화 1문제**입니다. [실행 안내](README.md)에 따라 설치한 뒤 `main.py`의 `todo(...)`를 채웁니다. 각 빈칸에는 사용할 입력과 필요한 결과가 적혀 있습니다. 함수 이름과 인자는 유지하고, 필요한 경우 빈칸 앞에 코드를 더 작성해도 됩니다.

## 작업 범위

| 문제 | 직접 작성할 내용 | 제공하는 부분 |
|---|---|---|
| 문서 검색 | Document 생성, 후보와 검색 점수, 병렬 연결 | 자료 복사, 정렬, 문서 표시, 결과 병합 |
| 기본 체인 | parser, 이전 대화 자리, 출처 검사, 순차 연결과 분기 조건 | 프롬프트 틀, 답변 자료형, 안전 안내 |
| 대화 이력 | 세션 이력 생성, 저장 조건과 메시지 | 이전 이력 읽기, 요청 단위 실행 |
| 실패 복구 | retry와 fallback 연결 | 허용 예외 목록, 안전 안내 |
| 스트리밍 | 스트림 이벤트, 복구 조건, 경과 시간과 청크 수 | 반복문, iterator 정리, callback 잠금과 기록 틀 |
| 선택 심화 | 초안 검토, 한 번 수정, 재검토 흐름 | 검토/수정 함수와 고정 사례 |

주로 수정할 파일은 `main.py` 하나입니다. HTTP 서버, 벡터 DB, 임베딩과 영구 메모리는 이번 범위에 없습니다. 함수의 전체 구조를 새로 설계할 필요는 없습니다.

기본 실행은 외부 호출이 없는 `fixture`입니다. `--live`는 실제 모델을 호출합니다. 정책 6개와 테스트용 릴리스 3개를 제공하므로 이전 과제를 완료하지 않아도 시작할 수 있습니다.

현재 문제의 작성할 함수를 구현한 뒤 기본 실행, 결과 확인, 기능 검사 순서로 진행합니다. 명령의 의미와 생성되는 파일은 [시작 안내](README.md)의 `명령어를 읽는 방법`과 `실행 후 무엇을 확인하나요?`에서 확인하세요. `data/`는 제공 입력, `artifacts/`는 본인이 실행한 결과이며 결과 파일은 제출하지 않습니다.

## 필수 1: 관련 문서를 찾아 실행 입력 준비하기

질문에 맞는 문서를 선택하고 답변 생성에 사용할 입력을 만드세요.

작성할 함수는 `to_documents`, `search_documents`, `build_context_chain`입니다. 다음 조건을 순서대로 적용하세요.

1. `to_documents`에서 본문은 `Document.page_content`, 나머지 필드는 제공된 metadata에 담습니다.
2. `search_documents`에서 허용 후보 밖의 문서를 제외하고, 질문에 포함된 키워드 수를 점수로 계산합니다. 대소문자 처리, 중복 키워드 제거, 점수순 정렬과 동점 처리는 제공합니다.
3. `build_context_chain`에서 `support.search_query(question, history)`로 검색 문자열을 준비합니다. 원입력 보존과 검색을 `RunnableParallel`로 묶으세요. 두 결과를 합치는 함수는 제공합니다.

예를 들어 질문이 Python 버전이고 후보가 `policy-python`, `policy-uv`, `policy-support`라면 `policy-python`이 먼저 나와야 합니다. 일치하는 키워드가 없으면 빈 목록을 반환합니다. 최대 검색 수는 3개입니다.

`build_context_chain`의 작성 이유 주석에 입력 보존과 검색을 나눈 이유를 한두 줄로 적으세요. 두 작업은 서로의 결과가 필요한지, 검색 함수를 교체해도 나머지 연결을 유지할 수 있는지 생각하면 됩니다.

**확인:** `uv run --frozen python main.py check search`

검사에서 후보 제한, 점수와 동점, 원본 보존과 병렬 실행을 확인합니다. `uv run --frozen python main.py run search`는 제공 사례별 검색 결과와 기대 문서를 함께 저장합니다. `artifacts/fixture/search.json`에서 Python 버전 안내, API 키 보관, 근거 없는 질문, 릴리스 검색 사례를 질문과 대조하세요.

## 필수 2: 기본 체인과 문서 없음 분기 만들기

검색 문서와 질문을 모델에 전달하고, 검증된 네 필드 답변을 반환하세요.

작성할 함수는 `build_prompt_and_parser`, `validate_sources`, `build_primary_chain`, `build_answer_chain`입니다.

1. `build_prompt_and_parser`에 `support.Answer`용 `PydanticOutputParser`와 history용 `MessagesPlaceholder`를 넣습니다. 고정 지침, 현재 문서와 질문의 자리는 제공합니다.
2. `validate_sources`에서 중복 출처, 검색하지 않은 출처, 출처 없는 해결 답변을 거부합니다. 출처가 없으면 `needs_human`은 true여야 합니다.
3. `build_primary_chain`에서 `prompt | model | parser`를 연결하고, 파싱 결과에 출처 검사를 적용합니다.
4. `build_answer_chain`의 문서 없음 조건을 채웁니다. 문서가 없으면 모델 호출 없이 담당자 확인 안내를 반환합니다.

**확인:** `uv run --frozen python main.py check chain`

검사는 준비된 입력을 사용하므로 문서 검색을 끝내지 않아도 실행할 수 있습니다. 같은 체인을 질문 두 개에 재사용하고 `uv run --frozen python main.py run chain --live`로 실제 답변도 확인하세요. 형식 검사를 통과한 답변도 문서 내용과 맞는지 확인해야 합니다.

## 필수 3: 세션별 후속 질문 이어가기

같은 직원의 후속 질문은 이어서 처리하고 다른 직원의 대화는 분리하세요.

작성할 함수는 `get_history`, `commit_history`입니다. 검색 입력 연결은 앞서 작성한 `build_context_chain`을 사용합니다.

1. `get_history`에서 새 세션에 `InMemoryChatMessageHistory`를 만듭니다. 기존 객체를 찾아 돌려주는 부분은 제공합니다.
2. `commit_history`에서 `primary` 결과만 저장하도록 조건을 채웁니다. 현재 질문의 HumanMessage와 확정된 답변의 AIMessage를 차례로 넣으세요.
3. 문서 검색에서 연결한 검색 보완이 후속 질문에도 적용되는지 확인합니다. `그 버전`, `그 설정`이 있으면 제공 함수가 같은 세션의 최근 질문을 함께 사용합니다.

이력은 한 프로세스에서만 유지됩니다. `run history`는 A의 질문 두 번과 B의 질문 한 번을 같은 프로세스에서 실행합니다. 정상 종료 뒤 A에는 메시지 4개, B에는 2개가 남아야 합니다. 문서 없음, fallback과 중단된 스트림은 이력에 남기지 않습니다.

`commit_history`의 작성 이유 주석에 문서와 대화 이력의 역할, 확정된 답변만 저장하는 이유를 한두 줄로 적으세요.

**확인:** `uv run --frozen python main.py check history`

`uv run --frozen python main.py run history --live`에서 후속 질문의 답변과 출처를 확인하세요. B의 답변에는 A의 대화 표식이 섞이지 않아야 합니다.

## 필수 4: 실패를 구분해 제한된 복구 적용하기

일시 오류에는 한 번 더 시도하고, 계속 실패하면 답변을 생성하지 못했음을 안내하세요.

`build_resilient_chain`의 두 빈칸에 `with_retry`와 `with_fallbacks`를 연결합니다. 대상은 생성, 파싱과 출처 검사입니다. 최초 호출을 포함해 최대 2회이며 fallback은 모델을 추가 호출하지 않습니다.

허용 오류는 제공 `support.RECOVERABLE`에 들어 있습니다. timeout, 공급자 5xx, 파싱/스키마/출처 오류를 포함합니다. 인증, 429, 설정 오류와 TypeError는 호출자에게 전달합니다. `Exception` 전체를 재시도 대상으로 넣지 마세요.

**확인:** `uv run --frozen python main.py check recovery`

제공 검사와 `run recovery`는 고정 오류를 사용합니다. 실제 API를 고의로 실패시킬 필요는 없습니다. 첫 실패 후 성공은 2회 호출, 두 번 실패는 fallback, 허용하지 않은 오류는 즉시 실패하는지 확인하세요.

## 필수 5: 생성 중 청크 전달과 실행 관측

답변이 만들어지는 동안 받은 내용을 전달하고, 실패한 단계를 기록으로 확인하세요.

작성할 함수는 `stream_answer`와 `TraceHandler`의 `_start`, `_finish`, `on_llm_new_token`입니다. 청크 전달, 실패 처리, 실행 기록 순서로 작성하세요.

### 청크와 최종 답변 전달

`stream_answer`에서 `stream_chain.stream(prepared, config=config)`로 받은 청크를 전달합니다. 각 청크는 `delta` 이벤트입니다. 모두 받은 뒤 parser와 출처 검사를 통과하면 `final`로 확정하세요. 반복문, 텍스트 누적과 스트림을 닫는 코드는 제공합니다.

| 이벤트 | 담을 값 | 의미 |
|---|---|---|
| delta | `type: "delta"`, `text: text` | 아직 검증하지 않은 모델 출력 |
| reset | `type: "reset"`, `reason: "unverified_output"` | 앞서 보낸 임시 출력을 폐기 |
| final | `type: "final"`, `reply: answer.model_dump()`, `route` | 검증된 최종 답변과 처리 경로 |

청크를 각각 JSON으로 파싱하지 않습니다. 최종 답변만 한 번 검증합니다. `invoke()`가 끝난 문자열을 나누는 대신 실제 `stream()`을 사용하세요.

### 오류에 따른 처리

| 상황 | 처리 |
|---|---|
| 첫 delta 이전의 허용 오류, 첫 시도 | 한 번 재시도 |
| delta를 보낸 뒤 오류 또는 최종 검증 실패 | reset 뒤 final fallback |
| 재시도까지 실패하고 delta 없음 | final fallback |
| 인증/설정/코드 오류 | 제공 코드가 오류를 전달하며, delta가 있었다면 먼저 reset |
| 소비자가 중간에 종료 | 제공 코드가 iterator를 닫음. 이력 저장 없음 |

재시도 조건과 reset/fallback 이벤트를 채우세요. `sent_delta`는 텍스트 전달 여부, `attempt`는 0부터 시작하는 시도 번호입니다. 재시도한 두 응답을 이어 붙이지 않습니다.

### 실행 기록에 담을 값

`TraceHandler`의 상태 사전, 잠금과 기록 형식은 제공합니다. 다음 네 값만 계산하세요.

- `_start`: `self.clock()`으로 읽은 시작 시각
- `_finish`: 시작부터 지난 밀리초, 오류가 있다면 예외 클래스 이름
- `on_llm_new_token`: 비어 있지 않은 텍스트 청크의 누적 개수

모델과 parser에 `config`를 전달해야 callback이 실행됩니다. 단계명과 부모 run, 모델 시도 수, usage와 JSONL 저장은 제공 코드가 연결합니다. 청크 개수와 토큰 사용량은 다릅니다. usage가 없으면 제공 코드는 null을 기록합니다. 질문, 문서, 답변 원문과 키는 기록하지 않습니다.

**확인:** `uv run --frozen python main.py check stream`

`uv run --frozen python main.py run stream --scenario midstream`으로 중간 실패를 확인하세요. `artifacts/fixture/trace.jsonl`에서 `model_error`의 부모 run과 `request_summary`의 route/시도 수를 대조합니다. `stream_answer`의 관측 메모에 확인한 실패 단계와 처리 결과를 한두 줄로 적으세요.

`uv run --frozen python main.py run stream --live`에서는 실제 청크와 usage를 확인합니다. 정상 primary만 이력에 저장하고, reset이나 중단을 성공으로 기록하지 않습니다.

## 선택 심화 1: 답변 초안을 검토하고 한 번 개선하기

`review_draft`는 전체 흐름을 직접 설계하는 문제입니다. 필수에서 만든 답변 검증을 재사용해 초안 검토, 필요한 경우 한 번 수정, 수정 결과 재검토를 연결하세요.

입력은 Answer 객체인 `draft`, 검색 문서 `documents`, 함수 `reviewer`, `rewriter`입니다. 두 함수에는 `{"draft": 현재 Answer, "documents": 검색 문서}`를 전달합니다. reviewer는 `keep`, `revise`, `human`을 반환하고 rewriter는 수정된 Answer를 반환합니다.

- keep이면 검증된 초안을 유지합니다.
- revise이면 최대 한 번 수정한 뒤 형식과 출처를 검사하고 다시 검토합니다.
- 재검토 결과가 keep이 아니거나 처음부터 human이면 fallback으로 끝냅니다.

반환값은 `{"reply": Answer 객체, "route": "primary" 또는 "fallback"}` 형태의 dict입니다. 검증된 답변은 primary, 담당자 확인 안내는 fallback으로 구분하세요.

**확인:** `uv run --frozen python main.py check challenge`

`uv run --frozen python main.py challenge`는 제공된 고정 사례를 실행하고 초안, 최종 답변과 검토/수정 함수 호출 수를 저장합니다. 잘못된 Python 버전을 수정하는 사례에서 답변이 문서와 맞게 바뀌었는지 확인하세요. 이 비교는 테스트용 함수의 동작 확인이며 실제 모델 품질 측정은 아닙니다. 선택 심화에 실제 API 호출은 필요하지 않습니다.

## 입력과 반환값 참고

함수 이름과 다음 필드 이름은 제공 실행 코드가 사용합니다. Prepared와 Outcome은 새 클래스가 아니라 dict를 가리키는 이름입니다.

| 입력 | 필드 |
|---|---|
| 원천 문서 | `doc_id`, `title`, `body`, `source_url`, `collected_at`, `category` |
| 요청 | `question`, `document_ids`, `session_id` |
| Prepared | 요청 세 필드 + `history`, 실제 검색 `documents`, 표시한 `context` |
| Outcome | `reply`: Answer 객체, `route`: primary/no_documents/fallback |

요청은 제공 코드가 검사합니다. question은 3~1,000자, document_ids는 서로 다른 ID 1~3개, session_id는 1~64자이며 기본값은 demo입니다. 없는 ID는 검색 전에 거부합니다. 후보 전체가 아닌 실제 검색 결과만 답변 근거로 사용하세요.

Answer는 `answer`, `source_ids`, `needs_human`, `category` 네 필드입니다. 공백 답변, 잘못된 자료형과 추가 필드는 parser가 거부합니다. category는 installation/access/incident/general입니다. 릴리스 문서도 답변에는 이 네 범주 중 하나를 사용합니다. 출처 오류는 `support.SourceValidationError`로 처리합니다.

`support.safe_answer("no_documents")`와 `support.safe_answer("fallback")`은 검증된 안내 Answer를 제공합니다. 일반 체인은 Answer 객체를, 스트림 final은 `model_dump()`한 dict를 reply에 담습니다. route와 fixture/live 모드는 답변 네 필드 밖에 둡니다.

문서 없는 기본 지침 B1을 제공합니다. 앞 과제의 B2를 가져오려면 정책 지침만 사용하세요. 전체 `system_prompt.txt`를 복사하면 이번 검색 밖의 문서까지 섞일 수 있습니다. 이전 API 자료 가져오기는 [실행 안내](README.md)를 따릅니다.

## 제출

과제 제출 시스템에는 다음 두 파일만 제출합니다.

1. `main.py`: 구현 코드와 지정된 위치의 짧은 이유 또는 관측 주석
2. `AI_USAGE.md`: AI 사용 기록. 사용하지 않았다면 `사용하지 않음`으로 기록

`data/`는 제공 입력이고 `artifacts/`는 실행 결과를 직접 확인하는 폴더입니다. 두 폴더와 `support.py`, `checks.py`, 환경 설정 파일은 제출하지 않습니다. `.env`, `.venv`, 캐시, 실제 키와 개인 정보도 포함하지 않습니다. 실행 결과를 확인하는 과정은 과제에 포함되지만, 제출 파일은 위 두 개로 충분합니다.

AI는 개념 질문과 자신이 작성한 코드의 디버깅에만 사용합니다. 사용 여부와 질문은 [AI_USAGE](AI_USAGE.md)에 기록하세요.
