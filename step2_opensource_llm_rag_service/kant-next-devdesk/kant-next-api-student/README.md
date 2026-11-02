# DevDesk API 과제 시작하기

KANT NEXT는 기업 개발팀을 위한 업무지원 소프트웨어를 만듭니다. 신입 LLM 엔지니어 지원자 여러분은 서류 검토를 거쳐 과제전형에 참여하고 있습니다. 이번에는 개발지원팀의 DevDesk에 공개 릴리스 수집과 질문 API를 연결합니다. **필수 4문제와 선택 심화 1문제**이며, Python 수정은 `app.py`에서 진행합니다.

처음에는 [과제 본문](ASSIGNMENT.md)의 전체 흐름을 읽고 현재 문제의 함수를 구현하세요.

## ZIP을 열고 환경 준비하기

Python 3.12와 VS Code를 사용합니다. ZIP을 풀고 VS Code의 `파일 > 폴더 열기`에서 `app.py`와 `pyproject.toml`이 있는 폴더를 엽니다. `터미널 > 새 터미널`도 이 폴더에서 시작합니다.

uv가 없다면 [공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)를 따라 설치한 뒤 새 터미널을 여세요. Windows, macOS, Linux에서 같은 명령을 순서대로 실행합니다.

```text
uv --version
uv sync --frozen
uv run --frozen python --version
uv run --frozen python app.py demo
```

`uv sync --frozen`은 제공된 `pyproject.toml`과 `uv.lock`을 사용해 `.venv`에 필요한 패키지를 설치합니다. `.python-version`이 Python 3.12를 선택합니다. `uv run --frozen python --version`의 결과에 Python 3.12가 표시되는지 확인하세요.

이후 실행과 검사는 프로젝트 폴더에서 안내된 `uv run --frozen python ...` 명령을 사용합니다. 가상환경을 별도로 활성화할 필요는 없습니다.

`demo`는 키 없이 제공 예시를 보여 줍니다. 아직 구현하지 않은 부분은 실행하지 않습니다. 이 명령은 환경 확인용입니다. `support.todo("수집: 페이지와 크기")` 같은 부분을 주석에 맞는 값이나 코드로 바꾸세요. 예를 들어 조건이 필요한 빈칸에는 `항목 in 목록` 같은 판단식을 넣습니다. 단순히 `None`으로 바꾸거나 지우면 구현이 되지 않습니다.

## 파일은 이렇게 사용합니다

```text
app.py            직접 구현하는 코드
support.py        실행 명령, 서버 연결, 문법 처리와 테스트 응답
checks.py         기능별 검사와 실패 입력
pyproject.toml    Python과 패키지 설정
uv.lock           사용할 패키지의 고정 목록
.python-version   사용할 Python 버전
.env.example      실제 모델 설정 양식
README.md         실행 안내
ASSIGNMENT.md     업무 요청과 구현 요구사항
AI_USAGE.md       직접 작성할 AI 사용 기록
data/             회사 정책과 테스트용 예제
artifacts/        실행 후 생기는 결과
```

주로 `app.py`를 수정하고 AI 사용 여부는 `AI_USAGE.md`에 기록합니다. 검사에 맞추려고 `checks.py`의 기대값이나 제공 데이터를 바꾸지 않습니다.

## 명령어를 읽는 방법

모든 명령은 ZIP을 푼 프로젝트 폴더의 터미널에서 실행합니다. `uv run --frozen python app.py`는 제공된 잠금 파일을 갱신하지 않고 과제 환경의 Python으로 `app.py`를 실행한다는 뜻입니다. 뒤에 붙는 명령으로 실행할 기능을 고릅니다.

| 명령 부분 | 의미와 실행 시점 |
|---|---|
| `demo` | 설치 직후 제공 예시가 실행되는지 확인합니다. 작성한 코드의 완성을 검사하는 명령은 아닙니다. |
| `run collect` | 해당 기능을 구현한 뒤 제공 입력으로 실행합니다. 생성된 결과를 직접 읽습니다. |
| `check collect` | 정상 입력과 오류 입력을 넣어 요구사항을 검사합니다. 실패한 항목의 이름과 이유를 보고 코드를 고칩니다. |
| `check all` | 필수 기능을 모두 구현한 뒤 전체 필수 검사를 실행합니다. 선택 심화는 별도 검사입니다. |
| `--live` | 지원하는 실행 명령 뒤에 붙여 실제 외부 API를 사용합니다. 기본 실행과의 차이와 준비 사항은 아래 실제 실행 안내를 따릅니다. `check`에는 붙이지 않습니다. |

**현재 기능 구현 → 기본 실행 → 결과 파일 확인 → 기능 검사 → 필요한 실제 연결 확인** 순서로 진행하세요. 검사가 실패하면 해당 함수만 고치고 같은 명령으로 다시 확인합니다. `support.py`는 실행, 데이터 읽기와 결과 저장을 돕고 `checks.py`는 작성한 코드를 검사합니다. 두 파일의 내부 구현을 모두 이해할 필요는 없으며 제공된 상태로 사용합니다.

## 한 기능씩 구현하고 검사하기

`app.py`에서 과제 본문에 적힌 함수 이름을 검색하고 빈칸을 채우세요. 반복문, 오류 처리, 비동기 실행과 서버 연결은 제공됩니다. 코드 옆 `작성 메모`에는 판단 이유를 1~2줄로 남깁니다.

필수 4의 모델 연결, 실패 처리, 요청 제한과 기록은 모두 구현해야 합니다. 아래 명령은 각 기능을 따로 확인하기 위한 것이며 추가 문제가 아닙니다. 정상 입력을 먼저 확인하고 오류 입력을 검사합니다. 예시와 기대 결과는 과제 본문에 있습니다. HTML 태그 정리, URL과 날짜 문법 검사, 데코레이터나 서버 시작 코드는 새로 작성하지 않습니다.

| 문제와 기능 | 직접 구현한 기능 실행 | 기능 검사 |
|---|---|---|
| 필수 1 / 자료 수집 | `uv run --frozen python app.py run collect` | `uv run --frozen python app.py check collect` |
| 필수 2 / 문서 정제 | `uv run --frozen python app.py run documents` | `uv run --frozen python app.py check documents` |
| 필수 3 / 문서 API | `uv run --frozen python app.py serve --stage document-api` | `uv run --frozen python app.py check document-api` |
| 필수 4 / 모델 연결 | `uv run --frozen python app.py run query` | `uv run --frozen python app.py check query` |
| 필수 4 / 실패 처리 | `uv run --frozen python app.py run retry` | `uv run --frozen python app.py check retry` |
| 필수 4 / 요청 제한과 기록 | `uv run --frozen python app.py serve` | `uv run --frozen python app.py check observe` |

`check`는 검사에 필요한 자료와 테스트 서버를 직접 준비합니다. 별도의 서버나 실제 키가 필요하지 않고, 실제 외부 호출도 하지 않습니다. 결과는 `artifacts/fixture/checks-기능명.json`에 기록됩니다. 실패 메시지에서 사례와 이유를 읽고 현재 함수부터 수정하세요. 출력의 통과와 실패 수는 검사 항목 수이며 문제 수가 아닙니다.

자료 수집 실행은 문서 정제를 호출하지 않습니다. 문서 API 서버에서는 문서 API를 먼저 확인하며 `/query`는 아직 501입니다. `run query`는 모델 1회 호출만 확인합니다. 뒤 단계가 미완성이라고 앞 단계를 한꺼번에 구현할 필요는 없습니다. 필수 구현을 모두 마친 뒤 `uv run --frozen python app.py check all`로 묶어서 확인합니다.

## 실행 후 무엇을 확인하나요?

`data/`에는 정책 문서 6개, 수집을 재현하는 릴리스 10행, 질문 요청 예시와 선택 심화용 스냅샷 두 개가 있습니다. 제공 입력의 내용은 [예제 자료 안내](data/DATA_CARD.md)에서 확인합니다. `artifacts/`는 실행 후 생성되는 결과 폴더입니다.

자료 수집에서는 다음 세 명령을 구분하세요.

| 전체 명령 | 하는 일 | 확인할 곳 |
|---|---|---|
| `uv run --frozen python app.py run collect` | 제공된 릴리스 자료로 작성한 수집 함수를 실행합니다. 외부에 접속하지 않습니다. | `artifacts/fixture/collection_report.json`의 `success=true`, `successful_pages=2`, `raw_count=10`과 `raw_pages.json`의 두 페이지 |
| `uv run --frozen python app.py check collect` | 정상 수집, 오류 응답과 페이지 상한 등을 준비된 입력으로 검사합니다. 별도의 서버나 키가 필요하지 않습니다. | 터미널의 PASS/FAIL과 `artifacts/fixture/checks-collect.json`의 `failed=0` |
| `uv run --frozen python app.py run collect --live` | GitHub 공개 API에서 현재 릴리스를 최대 두 페이지 수집합니다. 인터넷 연결이 필요하며 OpenAI 키는 사용하지 않습니다. | `artifacts/live/`의 같은 두 수집 파일. 성공 여부와 건수를 확인하되 fixture의 10행과 같다고 가정하지 않습니다. |

수집 구현과 fixture 검사를 마친 뒤 실제 수집도 확인합니다. `check collect`가 만든 검사 결과는 다음 정제 단계의 입력을 대신하지 않습니다. 정제 전에 반드시 같은 모드의 `run collect`를 실행하세요.

아래 명령 부분 앞에는 `uv run --frozen python app.py`를 붙입니다. 기본 실행 파일은 `artifacts/fixture/`에 생성됩니다.

| 명령 부분 | 생성되는 파일 또는 화면 | 확인할 내용 |
|---|---|---|
| `run documents` | `documents.json`, `quarantine.json`, `excluded.json`, `quality_report.json` | 원본 10행이 채택 3개, 격리 5개, 제외 2개로 나뉘는지 봅니다. `quality_report.json`의 건수와 사유를 대조합니다. |
| `run query` | `model_response.json` | `response`의 답변과 출처가 선택 문서에 맞는지 확인합니다. `--live` 실행은 같은 파일을 `artifacts/live/`에 저장합니다. |
| `run retry` | `checks-retry.json` | 고정 실패 검사입니다. `check retry`와 같은 검사를 실행하며 `failed=0`인지 확인합니다. |
| `check all` | `checks-all.json` | 필수 검사 전체의 `failed=0`을 확인합니다. 실패하면 `results`의 `name`과 `detail`을 읽고 해당 기능을 다시 검사합니다. |
| `serve --stage document-api` / `serve` | 브라우저 `/docs`의 응답과 서버 터미널 | 상태 코드와 응답 본문, 요청 제한과 안전한 로그를 확인합니다. 응답이나 서버 로그 파일은 자동 생성되지 않으며 캡처 제출도 필요하지 않습니다. |
| `challenge` | `document_changes.json` | 선택 심화의 added, changed, unchanged, missing 분류를 확인합니다. |

`run documents --live`는 외부에 접속하지 않고 직전에 수집한 live 파일을 정제합니다. 수집을 다시 하면 같은 모드로 정제도 다시 해야 합니다. 같은 이름의 결과 파일은 재실행하면 바뀌므로 비교가 필요할 때만 따로 복사해 둡니다. 결과 파일은 확인용이며 제출하지 않습니다.

## 서버를 시작하고 요청 보내기

1. 터미널 1에서 `uv run --frozen python app.py serve --stage document-api`를 실행합니다. 요청 제한과 기록까지 완성했다면 `uv run --frozen python app.py serve`를 실행합니다.
2. 브라우저에서 `http://127.0.0.1:8000/docs`를 엽니다. `GET /health`를 펼치고 `Try it out > Execute`로 모드와 문서 수를 확인합니다.
3. `GET /documents`에서 문서를 확인합니다. 필요한 ID를 복사해 단건 조회 또는 `/query`의 `document_ids`에 사용합니다. 질문 요청에는 [제공 요청 예시](data/query_example.json)를 복사해 넣어도 됩니다.
4. `POST /documents`에는 [과제 본문](ASSIGNMENT.md)의 여섯 필드 예시를 넣습니다. 등록 후 조회하고, 같은 ID 또는 URL을 다시 등록했을 때의 응답도 확인합니다.
5. 터미널 1은 서버가 사용 중입니다. 검사나 다른 명령은 VS Code에서 터미널 2를 열고 같은 프로젝트 폴더에서 실행합니다.
6. 종료할 때 터미널 1에서 `Ctrl+C`를 누릅니다. 코드를 고치거나 정제 파일을 갱신했다면 서버를 종료한 뒤 같은 명령으로 다시 시작합니다.

8000번 포트가 사용 중이면 문서 API에서는 `uv run --frozen python app.py serve --stage document-api --port 8001`, 요청 제한과 기록에서는 `uv run --frozen python app.py serve --port 8001`로 실행하고 브라우저 주소도 맞춥니다. 이 서버는 내 컴퓨터의 단일 프로세스로 실행합니다.

`POST /documents`는 메모리에만 등록합니다. 재시작하면 파일의 회사 정책과 정제 자료를 다시 읽고 수동 등록 문서는 사라집니다. 빈 목록 검사는 검사기가 따로 준비하므로 회사 정책 파일을 지우지 마세요. 파일의 중복이나 형식 오류로 시작이 중단되면 해당 자료를 수정하고 다시 정제합니다.

## 실제 API와 모델 확인하기

기본 `fixture`는 테스트용 데이터와 고정 모델 대역입니다. `--live`를 붙인 실행만 실제 자료나 모델을 사용합니다. 결과 폴더는 `artifacts/fixture/`와 `artifacts/live/`로 나뉩니다.

| 명령 | 실제 네트워크 사용 |
|---|---|
| `uv run --frozen python app.py run collect --live` | GitHub 공개 API에서 최대 2페이지 수집 |
| `uv run --frozen python app.py run documents --live` | 없음. 직전에 성공한 live 원천 파일 정제 |
| `uv run --frozen python app.py run query --live` | 실제 모델 1회 연결 확인 |
| `uv run --frozen python app.py serve --live` | `/query` 요청 시 실제 모델 호출 |

실제 모델 실행 전 Windows에서는 `Copy-Item .env.example .env`, macOS와 Linux에서는 `cp .env.example .env`로 복사합니다. 생성된 `.env`의 `OPENAI_API_KEY`에 받은 키를 넣습니다. 기본 모델은 `gpt-5.6-luna`이며 계정에서 이용할 수 있는 모델을 설정합니다. `.env` 값을 터미널에 출력하거나 제출하지 않습니다.

먼저 fixture 검사를 마친 뒤 정상 요청으로 실제 연결을 확인하세요. 오류와 제한은 제공 대역으로 검사합니다. 실제 모델을 일부러 실패시키거나 호출 한도까지 요청할 필요는 없습니다. 생성 요청을 재시도하면 모델 호출과 비용이 중복될 수 있습니다.

수집 실패 시 부분 원천을 정제 성공 자료로 사용하지 않습니다. 현재 실행과 정제 파일이 맞지 않는다는 안내가 나오면 성공한 자료 수집 뒤에 같은 모드의 문서 정제를 다시 실행합니다. live 설정 오류를 fixture 성공으로 대신 기록하지 않습니다.

실제 응답의 문장과 릴리스 목록은 바뀔 수 있습니다. 실행 기록에서 사용 모드, 모델, 수집 시각과 응답 상태를 확인하고 답변을 근거 문서와 대조하세요. `check all` 통과만으로 실제 모델 연결이나 답변의 사실성까지 확인한 것은 아닙니다.

## 선택 심화와 제출

선택 심화에 도전한다면 `uv run --frozen python app.py challenge`와 `uv run --frozen python app.py check challenge`를 사용합니다. 선택 심화 미구현은 필수 검사와 서버 실행을 막지 않습니다.

과제 제출 시스템에는 다음 두 파일만 제출합니다.

1. `app.py`: 구현 코드와 지정된 위치의 짧은 이유 또는 관측 주석
2. `AI_USAGE.md`: AI 사용 기록. 사용하지 않았다면 `사용하지 않음`으로 기록

`data/`는 제공 입력이고 `artifacts/`는 실행 결과를 직접 확인하는 폴더입니다. 두 폴더와 `support.py`, `checks.py`, 환경 설정 파일은 제출하지 않습니다. `.env`, `.venv`, 캐시, 실제 키와 개인 정보도 포함하지 않습니다. 실행 결과를 확인하는 과정은 과제에 포함되지만, 제출 파일은 위 두 개로 충분합니다.

AI는 개념 질문과 직접 작성한 코드의 디버깅에만 사용하며, 자세한 범위는 [AI 사용 기록](AI_USAGE.md)을 따릅니다.
