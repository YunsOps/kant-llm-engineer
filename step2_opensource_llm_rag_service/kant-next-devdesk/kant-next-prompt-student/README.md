# KANT NEXT DevDesk 프롬프트 엔지니어링

KANT NEXT는 기업 개발팀을 위한 업무지원 소프트웨어를 만듭니다. 서류 검토를 마친 지원자 여러분은 DevDesk 개발 과제를 수행합니다. 사내 문서와 티켓을 근거로 개발환경과 장애 문의에 답하는 프로그램입니다.

필수 3문제와 선택 심화 1문제입니다. VS Code에서 `main.py` 하나를 중심으로 작성합니다. 필수는 준비된 코드의 작은 빈칸을 채우고, 선택 심화는 두 함수를 직접 설계합니다.

## 폴더와 실행 환경

ZIP을 풀고 VS Code의 **파일 → 폴더 열기**로 `main.py`가 있는 폴더를 엽니다. Microsoft의 Python 확장을 설치한 뒤 **터미널 → 새 터미널**을 여세요.

```text
main.py          직접 수정할 코드와 짧은 이유 주석
README.md        설치와 제출 안내
ASSIGNMENT.md    문제와 기능별 확인 방법
AI_USAGE.md      AI 사용 기준과 기록
support.py       제공 실행 및 저장 도우미
checks.py        기능별 검사
pyproject.toml   패키지 설정
uv.lock          고정 패키지 목록
.python-version  Python 버전
.env.example     키 설정 양식
data/            문서, 티켓, 질문과 이미지
artifacts/       실행 후 저장되는 결과
```

`support.py`, `checks.py`와 `data/`는 수정하지 않습니다. 새 패키지나 폴더 구조를 만들 필요는 없습니다.

uv가 없다면 [공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)를 따라 설치하고 새 터미널을 여세요. Windows, macOS, Linux에서 같은 명령을 사용합니다.

```text
uv --version
uv sync --frozen
uv run --frozen python --version
uv run --frozen python main.py demo
```

`uv sync --frozen`은 제공된 `pyproject.toml`과 `uv.lock`을 사용해 `.venv`에 필요한 패키지를 설치합니다. `.python-version`이 Python 3.12를 선택합니다. `uv run --frozen python --version`의 결과에 Python 3.12가 표시되는지 확인하세요.

이후 실행과 검사는 프로젝트 폴더에서 안내된 `uv run --frozen python ...` 명령을 사용합니다. 가상환경을 별도로 활성화할 필요는 없습니다.

`demo`는 키 없이 실행하는 환경 확인 예시입니다. 실제 모델 응답이 아닙니다.

## 명령어를 읽는 방법

모든 명령은 ZIP을 푼 프로젝트 폴더의 터미널에서 실행합니다. `uv run --frozen python main.py`는 제공된 잠금 파일을 갱신하지 않고 과제 환경의 Python으로 `main.py`를 실행한다는 뜻입니다. 뒤에 붙는 명령으로 실행할 기능을 고릅니다.

| 명령 부분 | 의미와 실행 시점 |
|---|---|
| `demo` | 설치 직후 제공 예시가 실행되는지 확인합니다. 작성한 코드의 완성을 검사하는 명령은 아닙니다. |
| `run policy` | 해당 기능을 구현한 뒤 제공 입력으로 실행합니다. 생성된 결과를 직접 읽습니다. |
| `check policy` | 정상 입력과 오류 입력을 넣어 요구사항을 검사합니다. 실패한 항목의 이름과 이유를 보고 코드를 고칩니다. |
| `check all` | 필수 기능을 모두 구현한 뒤 전체 필수 검사를 실행합니다. 선택 심화는 별도 검사입니다. |
| `--live` | 지원하는 실행 명령 뒤에 붙여 실제 외부 API를 사용합니다. 기본 실행과의 차이와 준비 사항은 아래 실제 실행 안내를 따릅니다. `check`에는 붙이지 않습니다. |

**현재 기능 구현 → 기본 실행 → 결과 파일 확인 → 기능 검사 → 필요한 실제 연결 확인** 순서로 진행하세요. 검사가 실패하면 해당 함수만 고치고 같은 명령으로 다시 확인합니다. `support.py`는 실행, 데이터 읽기와 결과 저장을 돕고 `checks.py`는 작성한 코드를 검사합니다. 두 파일의 내부 구현을 모두 이해할 필요는 없으며 제공된 상태로 사용합니다.

## 기능별 구현과 확인

[과제 본문](ASSIGNMENT.md)의 정책 프롬프트부터 진행합니다. `_todo(...)`는 아직 작성하지 않은 자리입니다. 설명에 맞는 문자열, 조건식 또는 함수 호출로 바꾸세요. 여러 줄이 필요하면 위에 변수를 만들고 넣어도 됩니다. `_todo` 함수 자체를 바꾸지는 않습니다.

```text
uv run --frozen python main.py check policy
uv run --frozen python main.py run policy
```

`check policy`는 작성한 코드의 고정 사례 검사입니다. `run policy`는 준비된 응답을 사용하는 fixture 실행입니다. 뒤 기능의 빈칸을 다 채우지 않아도 현재 기능은 확인할 수 있습니다. 미완료가 표시되면 이름이 나온 빈칸부터 작성하세요. 통과 수는 문제 수가 아니라 검사 항목 수입니다.

각 함수의 `이유:` 주석에는 설계 이유를 짧게 적습니다. 정책 프롬프트에는 세 기법의 적용 상황과 선택 이유, 최종 비교 후에는 사례 이름과 수정 이유를 남깁니다. 사용량과 비용에는 실제 비용과 지연을 보고 해석한 내용을 적습니다. 별도 문서는 만들지 않습니다.

## API 키와 실제 실행

Windows는 `Copy-Item .env.example .env`, macOS와 Linux는 `cp .env.example .env`로 복사합니다. `.env`의 `OPENAI_API_KEY=` 뒤에 본인의 키를 넣습니다. `.env.txt`가 되지 않도록 확인하세요. 키를 코드나 출력에 넣지 않습니다. 기본 모델은 `gpt-5.6-luna`입니다.

```text
uv run --frozen python main.py run policy --live
```

`--live`가 있을 때만 실제 API를 호출합니다. 아래 기능마다 먼저 `check`를 실행하세요. 호출 재시도는 고정 장애 주입이므로 `--live`를 사용하지 않습니다.

| 기능 | 검사 | 실행 |
|---|---|---|
| 정책 프롬프트 | `check policy` | `run policy --live` |
| 답변 검증과 수정 | `check answer` | `run answer --live` |
| 티켓 조회 | `check tools` | `run tools --live` |
| 오류 화면 입력 | `check image` | `run image --live` |
| 호출 재시도 | `check retry` | `run retry` |
| 사용량과 비용 | `check usage` | `run usage --live` |
| 전체 기능 연결 | `check pipeline` | `run pipeline --live` |

표의 명령 앞에는 모두 `uv run --frozen python main.py`를 붙입니다. fixture 결과는 분기 확인용이며 실제 답변 품질이나 캐시 적중을 증명하지 않습니다.

## 실행 후 무엇을 확인하나요?

`data/`에는 정책 문서 6개, 티켓 2개, 질문 사례 10개, 오류 화면과 가격표가 있습니다. 입력으로 사용하는 자료이며, 내용은 [예제 자료 안내](data/DATA_CARD.md)에서 확인합니다. `artifacts/`는 실행하면 생기는 결과 폴더입니다. VS Code 탐색기에서 아래 파일을 열어 확인하세요.

아래 명령 부분 앞에는 `uv run --frozen python main.py`를 붙입니다. 표의 파일은 모두 `artifacts/` 안에 생성됩니다.

| 명령 부분 | 생성되는 파일 | 확인할 내용 |
|---|---|---|
| `check policy` | `checks-policy.json` | 각 항목의 `status`가 `통과`인지 확인합니다. `미완료`는 남은 빈칸, `실패`는 `name`과 `detail`에 나온 조건부터 확인합니다. 다른 기능과 `all`도 같은 이름 규칙입니다. |
| `run policy` | `run-policy-fixture.json` | 준비된 질문과 두 프롬프트 조건의 응답 구조를 확인합니다. 고정 응답이므로 프롬프트 품질을 판단하는 결과는 아닙니다. |
| `run policy --live` | `run-policy-live.json` | 실제 답변을 정책 문서와 대조합니다. `answer`, `tools`, `image`, `usage`, `pipeline`도 기능명과 모드가 들어간 파일을 저장합니다. |
| `run retry` | `run-retry-fixture.json` | 일시 오류 후 성공, 인증 오류 즉시 종료, 최대 세 번 시도 후 종료를 확인합니다. |
| `run usage --live` | `run-usage-live.json` | Python과 uv 질문의 요청별 토큰, 추정 비용, 지연과 캐시 관측 상태를 확인합니다. 질문이 달라 비용 차이 전체를 캐시 효과로 볼 수 없습니다. |
| `compare --live` | `compare-live.json`, `prompt-baseline.txt`, `prompt-reasoning.txt`, `system_prompt.txt` | `records`의 실행 기록 26개를 사례별로 읽고 두 조건의 답변, 출처와 담당자 확인 판단을 비교합니다. |
| `export` | `prompt-baseline.txt`, `prompt-reasoning.txt`, `system_prompt.txt` | 코드로 만든 최종 프롬프트 내용을 확인합니다. API를 호출하지 않습니다. |
| `challenge --live` | `challenge-live.json`, `challenge-audit-live.json` | 선택 심화의 답변 6개와 정책 비교 3개를 읽습니다. |

검사 항목이 모두 통과해도 실제 답변의 사실성까지 보장되지는 않습니다. 실제 답변은 제공 문서와 직접 대조하고, 요구된 해석은 `main.py`의 기존 주석에 짧게 남깁니다.

기능 실행과 선택 심화는 같은 이름의 결과 파일을 다시 씁니다. 수정 전후를 비교하려면 재실행 전에 필요한 이전 파일을 다른 이름으로 복사해 두세요. 최종 비교는 아래의 `--fresh`를 사용하면 이전 파일을 자동 보존합니다. 결과 파일은 본인 확인용이며 제출하지 않습니다.

## 마지막 확인과 제출

선택 심화를 한다면 해당 코드까지 작성하고 실행한 다음 마지막 필수 비교를 진행합니다. 수행하지 않는다면 아래 두 명령은 건너뜁니다.

```text
uv run --frozen python main.py check challenge
uv run --frozen python main.py challenge --live
```

```text
uv run --frozen python main.py check all
uv run --frozen python main.py compare --live
uv run --frozen python main.py export
```

`compare --live` 한 번으로 준비된 사례와 반복 실행을 자동 처리하고 결과 26개를 저장합니다. 실행이 끝나면 사례 이름을 보며 두 조건의 답변과 개선할 부분을 검토하세요. 도구와 재시도로 실제 API 호출 수는 더 많을 수 있습니다.

중단했다면 같은 명령으로 이어서 실행합니다. 코드나 자료를 바꾸었다면 `compare --live --fresh`로 새 비교를 시작하세요. 기존 파일은 다른 이름으로 보존됩니다. 같은 비교 묶음에 서로 다른 코드의 결과를 합치지 않습니다. 주석만 고친 경우에는 비교에 영향을 주지 않으므로 재호출하지 않아도 됩니다.

과제 제출 시스템에는 다음 두 파일만 제출합니다.

1. `main.py`: 구현 코드와 지정된 위치의 짧은 이유 또는 관측 주석
2. `AI_USAGE.md`: AI 사용 기록. 사용하지 않았다면 `사용하지 않음`으로 기록

`data/`는 제공 입력이고 `artifacts/`는 실행 결과를 직접 확인하는 폴더입니다. 두 폴더와 `support.py`, `checks.py`, 환경 설정 파일은 제출하지 않습니다. `.env`, `.venv`, 캐시, 실제 키와 개인 정보도 포함하지 않습니다. 실행 결과를 확인하는 과정은 과제에 포함되지만, 제출 파일은 위 두 개로 충분합니다.

API 호출에 실패하면 코드의 관측 주석에 오류 종류와 확인한 범위를 짧게 남기세요. 실행하지 않은 결과를 만들거나 fixture를 live로 바꾸지 않습니다.

## 실행이 막혔다면

| 증상 | 먼저 확인할 내용 |
|---|---|
| uv를 찾지 못함 | 설치 뒤 새 터미널에서 `uv --version` 실행 |
| main.py를 찾지 못함 | 터미널이 ZIP을 푼 프로젝트 폴더에 있는지 확인 |
| import 오류 | 프로젝트 폴더에서 `uv sync --frozen`을 실행하고 안내된 `uv run --frozen python ...` 명령 사용 |
| 미완료 표시 | 출력에 나온 함수와 빈칸 확인 |
| 인증 오류 | `.env` 이름과 키 저장 여부 확인 |
| 429 또는 timeout | 실패 기록과 재시도 상한 확인. 무제한 재실행 금지 |

질문할 때는 기능 이름, 실행 명령, 기대한 결과와 키를 제외한 오류를 함께 전달하세요. AI에는 개념 질문과 직접 작성한 코드의 디버깅만 요청할 수 있습니다.
