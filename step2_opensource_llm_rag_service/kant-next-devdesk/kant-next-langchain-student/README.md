# KANT NEXT DevDesk LangChain 시작 안내

KANT NEXT는 기업 개발팀을 위한 업무지원 소프트웨어를 만듭니다. 신입 LLM 엔지니어 지원자 여러분은 서류 검토를 거쳐 과제전형에 참여하고 있습니다. 이번에는 개발지원팀의 DevDesk에 문서 검색과 대화 이력을 연결합니다. **필수 5문제와 선택 심화 1문제**이며 주로 수정할 파일은 `main.py`입니다. 실행 환경은 VS Code와 Python 3.12입니다.

## 먼저 읽을 자료

1. 이 안내에서 설치하고 제공 예제를 실행합니다.
2. [ASSIGNMENT](ASSIGNMENT.md)에서 문제별 요구를 읽습니다.
3. `main.py`의 `todo(...)`를 표현이나 조건으로 바꾸고 그 단계의 검사를 실행합니다.
4. [AI 사용 기록](AI_USAGE.md)을 작성합니다.

## uv로 환경 준비

ZIP을 풀고 `main.py`와 `pyproject.toml`이 있는 폴더를 VS Code로 엽니다. VS Code 터미널도 이 폴더에서 시작합니다.

Windows에서는 `C:\dev\kant-next-langchain`처럼 짧은 경로에 압축을 풀어주세요. 폴더 경로가 너무 길면 일부 패키지를 불러오지 못할 수 있습니다.

uv가 없다면 [공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)를 따라 설치한 뒤 새 터미널을 여세요. Windows, macOS, Linux에서 같은 명령을 순서대로 실행합니다.

```text
uv --version
uv sync --frozen
uv run --frozen python --version
uv run --frozen python main.py demo
```

`uv sync --frozen`은 제공된 `pyproject.toml`과 `uv.lock`을 사용해 `.venv`에 필요한 패키지를 설치합니다. `.python-version`이 Python 3.12를 선택합니다. `uv run --frozen python --version`의 결과에 Python 3.12가 표시되는지 확인하세요.

이후 실행과 검사는 프로젝트 폴더에서 안내된 `uv run --frozen python ...` 명령을 사용합니다. 가상환경을 별도로 활성화할 필요는 없습니다.

`demo`의 `[준비 확인]`은 제공 예제가 실행됐다는 뜻입니다. 직접 작성한 함수의 완료나 실제 모델 호출을 뜻하지 않습니다.

## 파일 구성

```text
main.py             # 빈칸을 채울 함수와 TraceHandler
support.py          # 제공: 실행 명령, 입출력, 모델, 기록 저장
checks.py           # 제공: 문제별 공개 검사
pyproject.toml       # Python과 패키지 설정
uv.lock             # 사용할 패키지의 고정 목록
.python-version     # 사용할 Python 버전
.env.example
README.md
ASSIGNMENT.md
AI_USAGE.md
data/               # 정책, 테스트용 릴리스, 검색 키워드, 사례
artifacts/          # 실행하면 생성: fixture와 live 기록
```

`main.py`에서 `todo(...)` 호출만 필요한 코드로 바꿉니다. 위쪽의 `todo` 함수는 미완성 안내를 출력하는 제공 코드입니다. 자료 복사, 정렬, 반복문, 스트림 정리와 로그 저장은 그대로 사용할 수 있습니다. AI 사용 여부는 `AI_USAGE.md`에 기록하세요. `checks.py`와 예제 데이터는 제공된 상태로 검사합니다.

## 명령어를 읽는 방법

모든 명령은 ZIP을 푼 프로젝트 폴더의 터미널에서 실행합니다. `uv run --frozen python main.py`는 제공된 잠금 파일을 갱신하지 않고 과제 환경의 Python으로 `main.py`를 실행한다는 뜻입니다. 뒤에 붙는 명령으로 실행할 기능을 고릅니다.

| 명령 부분 | 의미와 실행 시점 |
|---|---|
| `demo` | 설치 직후 제공 예시가 실행되는지 확인합니다. 작성한 코드의 완성을 검사하는 명령은 아닙니다. |
| `run search` | 해당 기능을 구현한 뒤 제공 입력으로 실행합니다. 생성된 결과를 직접 읽습니다. |
| `check search` | 정상 입력과 오류 입력을 넣어 요구사항을 검사합니다. 실패한 항목의 이름과 이유를 보고 코드를 고칩니다. |
| `check all` | 필수 기능을 모두 구현한 뒤 전체 필수 검사를 실행합니다. 선택 심화는 별도 검사입니다. |
| `--live` | 지원하는 실행 명령 뒤에 붙여 실제 외부 API를 사용합니다. 기본 실행과의 차이와 준비 사항은 아래 실제 실행 안내를 따릅니다. `check`에는 붙이지 않습니다. |

**현재 기능 구현 → 기본 실행 → 결과 파일 확인 → 기능 검사 → 필요한 실제 연결 확인** 순서로 진행하세요. 검사가 실패하면 해당 함수만 고치고 같은 명령으로 다시 확인합니다. `support.py`는 실행, 데이터 읽기와 결과 저장을 돕고 `checks.py`는 작성한 코드를 검사합니다. 두 파일의 내부 구현을 모두 이해할 필요는 없으며 제공된 상태로 사용합니다.

## 문제별 실행

| 문제 | 실행 | 검사 | 실제 모델 |
|---|---|---|---|
| 문서 검색 | `uv run --frozen python main.py run search` | `uv run --frozen python main.py check search` | 사용하지 않음 |
| 기본 체인 | `uv run --frozen python main.py run chain` | `uv run --frozen python main.py check chain` | `uv run --frozen python main.py run chain --live` |
| 대화 이력 | `uv run --frozen python main.py run history` | `uv run --frozen python main.py check history` | `uv run --frozen python main.py run history --live` |
| 실패 복구 | `uv run --frozen python main.py run recovery` | `uv run --frozen python main.py check recovery` | 고정 실패 사례로 확인 |
| 스트리밍과 관측 | `uv run --frozen python main.py run stream` | `uv run --frozen python main.py check stream` | `uv run --frozen python main.py run stream --live` |
| 선택 심화 | `uv run --frozen python main.py challenge` | `uv run --frozen python main.py check challenge` | 사용하지 않음 |

기본은 외부 호출이 없는 `fixture`입니다. `check`도 fixture 검사입니다. `--live`를 붙여야 실제 API를 호출하며 호출에 실패했다고 fixture로 바꾸지 않습니다. 대화 이력 실행은 같은 프로세스에서 A 두 번과 B 한 번의 질문을 실행합니다. 명령을 새로 실행하면 이력은 초기화됩니다.

```powershell
Copy-Item .env.example .env
```

생성된 `.env`에 개인 `OPENAI_API_KEY`를 입력합니다. 기본 `OPENAI_MODEL`은 `gpt-5.6-luna`입니다. 키를 소스 코드나 제출 자료에 쓰지 않습니다. macOS/Linux 복사는 `cp .env.example .env`입니다.

검사 결과의 `passed`는 통과한 검사 항목 수, `failed`는 실패한 검사 항목 수입니다. 문제 개수나 점수가 아닙니다. 각 항목의 `name`과 `detail`에서 확인한 동작과 실패 이유를 읽으세요. 처음에는 빈칸 때문에 실패합니다. 기본 체인 검사는 준비 입력으로 실행하므로 다른 문제를 끝내지 않아도 됩니다. 대화 이력 이후의 통합 실행은 앞선 구현도 사용합니다.

```powershell
uv run --frozen python main.py check all
```

위 명령은 필수만 검사합니다. 선택 문제를 하지 않아도 필수 전체 검사는 통과할 수 있습니다. 검사 통과 후 실제 답변 내용도 근거와 대조하세요.

스트리밍은 청크 전달, 실패 처리, 기록 계산 순서로 작성합니다. 중간 실패를 관찰할 때는 아래 명령을 사용하세요. 외부 API를 호출하지 않습니다.

```powershell
uv run --frozen python main.py run stream --scenario midstream
```

`--scenario temporary`는 첫 호출 실패 뒤 성공, `--scenario invalid_json`은 마지막 파싱 실패를 재현합니다. 기본은 정상 사례입니다. `trace.jsonl`은 실행할 때마다 뒤에 기록을 추가하므로 가장 최근 `devdesk_stream`과 같은 run의 기록을 확인하세요.

실행 결과는 `artifacts/fixture/search.json`, `chain.json`, `history.json`, `recovery.json`, `stream.json`에 저장됩니다. 실제 모델 결과는 `artifacts/live/`에, 검사는 `checks-search.json`처럼 기능명 앞에 `checks-`를 붙인 파일에 저장됩니다. 선택 심화 결과는 `challenge.json`입니다.

## 실행 후 무엇을 확인하나요?

`data/`에는 정책 문서 6개, 테스트용 릴리스 3개, 검색 키워드, 질문 사례와 선택 심화용 초안이 있습니다. 이전 API 과제의 결과가 없어도 이 자료로 시작할 수 있습니다. 상세 내용은 [예제 자료 안내](data/DATA_CARD.md)를 참고하세요.

아래 명령 부분 앞에는 `uv run --frozen python main.py`를 붙입니다. 기본 실행은 외부 호출이 없으며 결과 파일은 `artifacts/fixture/`에 생깁니다. VS Code 탐색기에서 해당 파일을 열어 확인합니다.

| 명령 부분 | 생성되는 파일 | 확인할 내용 |
|---|---|---|
| `run search` | `search.json` | `search_cases`의 `actual_ids`와 `expected_ids`가 일치하고 `matches=true`인지 확인합니다. |
| `run chain` | `chain.json` | `reply`의 답변과 출처를 확인합니다. 정상 사례의 `route`는 `primary`입니다. 무문서 등 경계 입력은 `check chain`으로 검사합니다. |
| `run history` | `history.json` | A 두 번, B 한 번의 `turns`와 `history_counts`를 확인합니다. 모두 정상 응답이면 A는 메시지 4개, B는 2개입니다. 명령을 다시 실행하면 이력은 초기화됩니다. |
| `run recovery` | `recovery.json` | `cases`에서 시도 수가 최초 포함 최대 2회인지, 두 번 실패하면 `route=fallback`인지 확인합니다. |
| `run stream` | `stream.json`, `trace.jsonl` | 전달된 이벤트와 마지막 답변, 호출 시도 수를 확인합니다. 정상 완료에는 `final` 이벤트가 있어야 합니다. |
| `run stream --scenario midstream` | `stream.json`, `trace.jsonl` | 중간 실패 뒤 `reset`으로 앞선 delta를 폐기하고 최종 답변을 확정하는지 확인합니다. 고정 실패 사례라 실제 API는 호출하지 않습니다. |
| `check search` / `check all` | `checks-search.json` / `checks-all.json` | `failed=0`인지 확인합니다. 실패하면 각 항목의 `name`과 `detail`을 보고 해당 함수를 수정합니다. 다른 기능도 같은 이름 규칙입니다. |
| `challenge` | `challenge.json` | 선택 심화의 수정 전후 답변과 `review_calls`, `rewrite_calls`를 확인합니다. |

`run chain --live`, `run history --live`, `run stream --live`는 실제 모델 연결 확인에 사용하며 같은 이름의 결과를 `artifacts/live/`에 저장합니다. fixture 검사 후 실행하고 실제 답변도 문서와 대조하세요. 문서 검색, 실패 복구와 선택 심화는 제공 자료로 확인합니다.

같은 기능의 JSON은 재실행하면 덮어쓰고 `trace.jsonl`은 뒤에 기록을 추가합니다. 스트리밍의 다른 시나리오를 비교하려면 먼저 `stream.json`을 다른 이름으로 복사해 두고, trace에서는 가장 최근 `devdesk_stream`과 같은 run의 기록을 확인하세요. 결과 파일은 본인 확인용이며 제출하지 않습니다.

## 이전 과제 결과 가져오기

기본 자료에 정책 6개와 테스트용 릴리스 3개가 있어 이전 과제를 완료하지 않아도 시작할 수 있습니다. 이전 API의 `artifacts/fixture/documents.json`처럼 **릴리스 문서만 담긴 배열**을 사용하려면 다음과 같이 경로를 지정합니다.

```powershell
uv run --frozen python main.py run search --documents "../kant-next-api-student/artifacts/fixture/documents.json"
```

경로는 실제 폴더에 맞게 바꿉니다. 지정 파일은 기본 릴리스 자료를 교체하고 정책 6개와 합쳐집니다. 같은 ID나 URL, 잘못된 필드는 거부합니다. 파일에 개별 키워드가 없는 릴리스는 제공 기본 키워드를 사용합니다. 이전 API의 `/documents` 전체 응답을 그대로 가져오면 정책이 중복될 수 있으므로 사용하지 않습니다.

## 제출

과제 제출 시스템에는 다음 두 파일만 제출합니다.

1. `main.py`: 구현 코드와 지정된 위치의 짧은 이유 또는 관측 주석
2. `AI_USAGE.md`: AI 사용 기록. 사용하지 않았다면 `사용하지 않음`으로 기록

`data/`는 제공 입력이고 `artifacts/`는 실행 결과를 직접 확인하는 폴더입니다. 두 폴더와 `support.py`, `checks.py`, 환경 설정 파일은 제출하지 않습니다. `.env`, `.venv`, 캐시, 실제 키와 개인 정보도 포함하지 않습니다. 실행 결과를 확인하는 과정은 과제에 포함되지만, 제출 파일은 위 두 개로 충분합니다.


## 실행이 막혔다면

미완성 안내가 나오면 이름이 표시된 `todo(...)`부터 작성합니다. `[실행 실패] NameError`처럼 오류 종류만 나오면 현재 기능의 `check`를 실행하고 `name`과 `detail`을 확인하세요. 결과가 충분하지 않으면 VS Code에서 해당 함수에 중단점을 두고 같은 인자로 디버깅합니다. 질문할 때에는 기능명, 실행 명령, 실패한 검사 항목과 직접 작성한 코드 일부를 전달하고 API 키는 제외합니다.
