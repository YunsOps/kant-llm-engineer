"""제공 도우미: 전송, 데이터, 직렬화, 실행. 직접 구현할 함수는 main.py에 있습니다."""
import argparse
import ast
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MODEL = "gpt-5.6-luna"
STAGE_NAMES = {
    "policy": "정책 프롬프트",
    "answer": "답변 검증과 수정",
    "tools": "티켓 조회",
    "image": "오류 화면 입력",
    "retry": "호출 재시도",
    "usage": "사용량과 비용",
    "pipeline": "전체 기능 연결",
    "challenge": "선택 심화",
}
STAGES = [name for name in STAGE_NAMES if name != "challenge"]
STAGE_ALIASES = dict(zip((f"p{index}" for index in range(1, 8)), STAGES))


def normalize_stage(value):
    """기존 실행 명령도 같은 기능으로 연결합니다."""
    return STAGE_ALIASES.get(value, value)


def case_name(case):
    return case.get("case_name", case["question"])


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_data():
    return read_json(DATA / "documents.json"), read_json(DATA / "tickets.json"), read_json(DATA / "evaluation_cases.json")


def load_prices():
    return read_json(DATA / "prices.json")


def image_url(path):
    data = Path(path).read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("제공 이미지 형식은 PNG여야 합니다.")
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def base_request(instructions, question, variant):
    """제공 SDK 인자 틀. schema/tool/image/cache 값은 지원자가 추가합니다."""
    if variant not in {"baseline", "reasoning"}:
        raise ValueError("알 수 없는 비교 조건입니다.")
    return {"model": MODEL, "instructions": instructions,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": question}]}],
            "reasoning": {"effort": "none" if variant == "baseline" else "low"},
            "max_output_tokens": 1800, "store": False,
             "include": ["reasoning.encrypted_content"]}


def has_refusal(response):
    return any(part.get("type") == "refusal" for item in response.get("output", [])
               for part in item.get("content", []))


def validation_detail(error):
    """예외 원문을 복사하지 않고 안전한 종류와 필드 위치만 읽습니다."""
    from jsonschema import ValidationError
    if isinstance(error, json.JSONDecodeError):
        return "invalid_json", None
    if isinstance(error, ValidationError):
        path = [str(value) for value in error.absolute_path
                if isinstance(value, int) or value in {"answer", "source_ids", "needs_human", "category"}]
        return "schema_error", ".".join(path) or "$"
    kind = {"blank answer": "blank_answer", "unknown source_id": "unknown_source",
            "duplicate source_id": "duplicate_source",
            "unsupported answer requires human": "unsupported_answer"}.get(str(error), "business_rule")
    return kind, "answer" if kind == "blank_answer" else "source_ids"


def append_repair_input(request, response, hint):
    """지원자가 만든 수정 지시를 같은 대화에 넣습니다. 전송은 하지 않습니다."""
    request["input"].extend(copy.deepcopy(response.get("output", [])))
    request["input"].append({"role": "user", "content": hint})
    if request.get("tools"):
        request["tool_choice"] = "none"


def append_attempt(events, attempt, started, response=None, error=None, retryable=False, wait_s=0):
    """이미 결정한 시도 결과를 기록합니다. 재시도 여부를 대신 결정하지 않습니다."""
    events.append({"event": "api_attempt", "attempt": attempt, "response": response,
                   "latency_ms": (time.perf_counter() - started) * 1000,
                   "error_kind": error.kind if error else None,
                   "status_code": error.status_code if error else None,
                   "request_id": error.request_id if error else response.get("request_id"),
                   "retryable": retryable, "wait_s": wait_s})


def validate_usage_counters(it, ot, cached, written, reasoning):
    """계량의 기본 자료형과 이미 관측된 값 사이의 모순을 검사합니다."""
    counters = (it, ot, cached, written, reasoning)
    if any(type(value) is not int or value < 0 for value in counters if value is not None):
        raise ValueError("invalid usage counter")
    if it is not None and sum(value for value in (cached, written) if value is not None) > it:
        raise ValueError("inconsistent input counters")
    if ot is not None and reasoning is not None and reasoning > ot:
        raise ValueError("inconsistent output counters")


def pack_usage_record(attempt, response, prices, it, ot, cached, written, reasoning,
                      observation, estimate, assumption):
    """지원자가 고른 계량, 관측 상태, 계산값을 정해진 로그 형식으로 담습니다."""
    return {"event": "api_response" if response else "api_error",
            "response_id": response.get("id"), "request_id": attempt.get("request_id"),
            "model": response.get("model"), "status": response.get("status"),
            "attempt": attempt["attempt"], "latency_ms": round(attempt["latency_ms"], 3),
            "error_kind": attempt.get("error_kind"), "status_code": attempt.get("status_code"),
            "retryable": attempt.get("retryable"), "wait_s": attempt.get("wait_s", 0),
            "input_tokens": it, "output_tokens": ot, "cached_tokens": cached,
            "cache_write_tokens": written, "reasoning_tokens": reasoning,
            "cache_observation": observation, "estimated_cost_usd": estimate,
            "cost_assumption": assumption,
            "price_usd_per_million": {key: prices[key] for key in ["input", "cached", "cache_write", "output"]},
            "price_source": prices["source"], "price_checked_at": prices["checked_at"]}


class TransportError(Exception):
    """지원자가 SDK 내부 예외 대신 읽는 단순한 전송 오류."""
    def __init__(self, kind, status_code=None, request_id=None):
        super().__init__(f"{kind} (status={status_code})")
        self.kind = kind
        self.status_code = status_code
        self.request_id = request_id


def delay_for(attempt):
    """대기값 계산은 제공, 기다릴지/언제/몇 번인지는 지원자가 결정합니다."""
    return random.uniform(0.1, min(4.0, 0.5 * 2 ** (attempt - 1)))


def live_sender():
    from dotenv import load_dotenv
    from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("main.py와 같은 폴더의 .env에 OPENAI_API_KEY를 입력하세요. 키 없이 실행하려면 --live를 빼세요.")
    client = OpenAI(max_retries=0, timeout=30.0)

    def send(request):
        try:
            response = client.responses.create(**request)
        except APITimeoutError as error:
            raise TransportError("timeout") from error
        except APIConnectionError as error:
            raise TransportError("connection") from error
        except APIStatusError as error:
            raise TransportError("http", error.status_code, error.request_id) from error
        result = response.model_dump(mode="json", exclude_none=True)
        result["output_text"] = response.output_text
        result["request_id"] = response._request_id
        return result
    return send


class Replay:
    """고정 응답/오류 재생기. 실제 모델, 이미지 해석, API 캐시가 아닙니다."""
    def __init__(self, events):
        self.events = iter(events)
        self.requests = []

    def __call__(self, request):
        self.requests.append(copy.deepcopy(request))
        try:
            event = next(self.events)
        except StopIteration as error:
            raise AssertionError("준비된 fixture를 넘는 호출입니다. 종료 조건을 확인하세요.") from error
        if isinstance(event, Exception):
            raise event
        return copy.deepcopy(event)


def fixture_response(answer=None, *, raw=None, output=None, status="completed", cached=0, written=0):
    text = raw if raw is not None else json.dumps(answer, ensure_ascii=False) if answer else ""
    return {"id": "fixture-response", "request_id": "fixture-request",
            "model": "fixture-not-a-model", "status": status, "output_text": text,
            "output": output if output is not None else [{"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}]}],
            "usage": {"input_tokens": 1500, "output_tokens": 70,
                      "input_tokens_details": {"cached_tokens": cached, "cache_write_tokens": written},
                      "output_tokens_details": {"reasoning_tokens": 0}}}


def sample_answer():
    return {"answer": "Python 3.12 환경을 사용하세요.", "source_ids": ["policy-python"],
            "needs_human": False, "category": "installation"}


def tool_fixture(ticket_id="IT-1043"):
    return fixture_response(output=[
        {"type": "reasoning", "id": "rs_fixture", "summary": [], "encrypted_content": "fixture-only"},
        {"type": "function_call", "id": "fc_fixture", "call_id": "call_fixture_1",
         "name": "lookup_ticket", "arguments": json.dumps({"ticket_id": ticket_id})},
    ])


def case_sender(case):
    """실행 흐름 확인용 고정 답변. 내용 품질 평가에 사용하지 않습니다."""
    answer = {"answer": "고정 fixture입니다. 실제 모델이 생성한 답변이 아닙니다.",
              "source_ids": case["expected_source_ids"], "needs_human": case["expected_needs_human"],
              "category": case["expected_category"]}
    events = [fixture_response(answer)]
    if case.get("tool_ticket_id"):
        events.insert(0, tool_fixture(case["tool_ticket_id"]))
    return Replay(events)


def traced_sender(send, trace):
    """요청과 실제 응답을 기록하되 이미지 바이트는 해시/길이로 요약합니다."""
    def traced(request):
        saved = copy.deepcopy(request)
        for item in saved.get("input", []):
            if not isinstance(item.get("content"), list):
                continue
            for part in item["content"]:
                url = part.get("image_url", "")
                if isinstance(url, str) and url.startswith("data:image/"):
                    payload = base64.b64decode(url.split(",", 1)[1])
                    part["image_url"] = {"redacted_binary": True, "mime_type": "image/png",
                                         "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        started = time.perf_counter()
        try:
            response = send(request)
        except TransportError as error:
            trace.append({"request": saved, "error_kind": error.kind, "status_code": error.status_code,
                          "request_id": error.request_id, "latency_ms": (time.perf_counter() - started) * 1000})
            raise
        trace.append({"request": saved, "response": copy.deepcopy(response),
                      "latency_ms": (time.perf_counter() - started) * 1000})
        return response
    return traced


def partial_checks(answer, case):
    """구조/기대 분류의 부분 검사입니다. 본문의 사실성, 도구 사용은 별도 검토."""
    return {"source_coverage": set(case["expected_source_ids"]) <= set(answer.get("source_ids", [])),
            "category": answer.get("category") == case["expected_category"],
            "handoff": answer.get("needs_human") == case["expected_needs_human"]}


def artifact_dir(module):
    return Path(module.__file__).resolve().parent / "artifacts"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fingerprint(module):
    digest = hashlib.sha256()
    paths = [Path(module.__file__), Path(__file__), ROOT / "pyproject.toml", ROOT / "uv.lock", ROOT / ".python-version"] + sorted(DATA.glob("*"))
    for path in paths:
        if path.is_file():
            digest.update(path.name.encode("utf-8"))
            if path.resolve() == Path(module.__file__).resolve():
                # 이유 주석만 보완한 경우에는 같은 실행 결과를 다시 수집하지 않습니다.
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                digest.update(ast.dump(tree, include_attributes=False).encode("utf-8"))
            else:
                digest.update(path.read_bytes())
    return digest.hexdigest()


def export_prompts(module):
    documents, _, _ = load_data()
    prompts = {variant: module.build_instructions(documents, variant) for variant in ["baseline", "reasoning"]}
    directory = artifact_dir(module)
    directory.mkdir(parents=True, exist_ok=True)
    for variant, prompt in prompts.items():
        (directory / f"prompt-{variant}.txt").write_text(prompt, encoding="utf-8")
    (directory / "system_prompt.txt").write_text(prompts["reasoning"], encoding="utf-8")
    return ["prompt-baseline.txt", "prompt-reasoning.txt", "system_prompt.txt"]


def stage_result(module, stage, case, variant, send, documents, tickets):
    """기능별 실행 골격입니다. 뒤 기능의 미완성 함수나 정답 대체 함수를 호출하지 않습니다."""
    stage = normalize_stage(stage)
    if stage == "pipeline":
        image_path = DATA / case["image"] if case.get("image") else None
        return module.run_pipeline(send, case["question"], documents, tickets, variant, image_path,
                                   load_prices())
    instructions = module.build_instructions(documents, variant)
    request = base_request(instructions, case["question"], variant)
    if stage == "policy":
        response = send(request)
        return {"response": response, "notice": "정책 프롬프트의 답변을 먼저 확인합니다."}
    request["text"] = module.answer_format()
    events = []
    known_ids = {document["doc_id"] for document in documents}
    if stage == "answer":
        response = send(request)
    elif stage == "tools":
        request["tools"] = [module.tool_schema()]
        request["parallel_tool_calls"] = False
        request, response = module.tool_roundtrip(send, request, tickets, events)
    elif stage == "image":
        request["input"][0]["content"] = module.image_content(case["question"], DATA / case["image"])
        response = send(request)
    elif stage == "usage":
        started = time.perf_counter()
        request.update(module.cache_settings(documents, variant))
        def reliable_send(current_request):
            return module.call_with_retry(send, current_request, events)
        response = reliable_send(request)
        result = module.finish_answer(reliable_send, request, response, known_ids, events)
        result["logs"] = [module.usage_record(event, load_prices()) if event["event"] == "api_attempt"
                          else event for event in events]
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return result
    else:
        raise ValueError("지원하지 않는 기능입니다.")
    result = module.finish_answer(send, request, response, known_ids, events)
    result["events"] = events
    return result


def fault_runs(module):
    scenarios = {
        "timeout_429_success": [TransportError("timeout"), TransportError("http", 429), fixture_response(sample_answer())],
        "authentication_401": [TransportError("http", 401)],
        "server_exhausted": [TransportError("http", 503) for _ in range(3)],
    }
    results = []
    for name, values in scenarios.items():
        events, waits = [], []
        replay = Replay(values)
        response = module.call_with_retry(replay, {"fixture": True}, events, sleep=waits.append)
        results.append({"scenario": name, "mode": "fixture", "response": response, "events": events,
                        "attempts": len(replay.requests), "waits": waits})
    return results


def comparison_plan(cases):
    plan = []
    for index, case in enumerate(cases):
        variants = ["baseline", "reasoning"] if index % 2 == 0 else ["reasoning", "baseline"]
        plan.extend((case, variant, 1) for variant in variants)
    for case in cases:
        if case["case_id"] in {"Q01", "Q07", "Q10"}:
            plan.extend((case, variant, 2) for variant in ["reasoning", "baseline"])
    return plan


def run_comparison(module, args):
    documents, tickets, cases = load_data()
    mode = "live" if args.live else "fixture"
    path = artifact_dir(module) / f"compare-{mode}.json"
    current_fingerprint = fingerprint(module)
    manifest = {"mode": mode, "fingerprint": current_fingerprint,
                "expected_records": 26, "records": []}
    if path.exists() and not args.fresh:
        manifest = read_json(path)
        if manifest.get("fingerprint") != current_fingerprint or manifest.get("mode") != mode:
            raise ValueError("코드나 자료가 바뀌어 이어서 실행할 수 없습니다. --fresh로 새 비교를 시작하세요.")
    elif path.exists():
        backup = path.with_name(path.stem + f"-{time.time_ns()}.json")
        path.replace(backup)
    plan = comparison_plan(cases)
    completed = manifest["records"]
    if len(completed) > len(plan):
        raise ValueError("비교 파일의 결과 수가 계획보다 큽니다.")
    for index, record in enumerate(completed):
        case, variant, repeat = plan[index]
        if (record.get("case_id"), record.get("variant"), record.get("repeat")) != (case["case_id"], variant, repeat):
            raise ValueError("비교 파일 순서가 고정 계획과 다릅니다. --fresh를 사용하세요.")
    live = live_sender() if args.live and len(completed) < len(plan) else None
    for case, variant, repeat in plan[len(completed):]:
        trace = []
        sender = live if args.live else case_sender(case)
        result = stage_result(module, "pipeline", case, variant, traced_sender(sender, trace), documents, tickets)
        record = {"mode": mode, "case_name": case_name(case), "case_id": case["case_id"], "variant": variant, "repeat": repeat,
                  "partial_checks": partial_checks(result["answer"], case), "trace": trace, **result}
        completed.append(record)
        save(path, manifest)
        print(f"[{mode}] 자동 비교 {len(completed)}/{len(plan)}: {case_name(case)} / {variant} / 반복 {repeat}")
    export_prompts(module)
    return {"path": str(path), "mode": mode, "records": len(completed),
            "notice": "fixture는 흐름 검사만 의미합니다. live 답변은 근거 문서와 직접 대조하세요."}


def challenge_run(module, live):
    documents, _, cases = load_data()
    mode = "live" if live else "fixture"
    records, audits = [], []
    sender = live_sender() if live else None
    for case in cases:
        if case["case_id"] not in {"Q01", "Q06", "Q09"}:
            continue
        for audience in ["newcomer", "operator"]:
            instructions = module.build_audience_instructions(documents, "reasoning", audience)
            request = base_request(instructions, case["question"], "reasoning")
            request["text"] = module.answer_format()
            trace, events = [], []
            send = traced_sender(sender if live else case_sender(case), trace)
            response = send(request)
            result = module.finish_answer(send, request, response, {doc["doc_id"] for doc in documents}, events)
            records.append({"mode": mode, "case_name": case_name(case), "case_id": case["case_id"], "audience": audience,
                            "trace": trace, "events": events, **result})
            save(artifact_dir(module) / f"challenge-{mode}.json", records)
        pair = records[-2:]
        audits.append({"case_name": case_name(case), "case_id": case["case_id"], "mode": mode,
                       **module.audit_audience_pair(pair[0]["answer"], pair[1]["answer"])})
        save(artifact_dir(module) / f"challenge-audit-{mode}.json", audits)
    return {"mode": mode, "records": len(records), "path": str(artifact_dir(module) / f"challenge-{mode}.json")}


def cli(module, argv=None):
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="KANT NEXT DevDesk: VS Code 개발 과제. 실제 API는 --live만 사용합니다.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="API 키 없이 자료, 환경 준비 확인")
    checker = sub.add_parser("check", help="구현한 함수의 고정 사례 검사(실제 API 사용 안 함)")
    checker.add_argument("stage", type=normalize_stage, choices=STAGES + ["all", "challenge"],
                         help="기능별 검사. all은 필수 전체, challenge는 선택 심화 검사")
    runner = sub.add_parser("run", help="현재 기능에서 구현한 함수를 실행")
    runner.add_argument("stage", type=normalize_stage, choices=STAGES,
                        help="policy: 정책 프롬프트, answer: 답변 검증과 수정, tools: 티켓 조회, image: 오류 화면 입력, retry: 호출 재시도, usage: 사용량과 비용, pipeline: 전체 기능 연결")
    runner.add_argument("--live", action="store_true", help="실제 API 사용 및 비용 발생")
    comparison = sub.add_parser("compare", help="준비된 사례를 두 조건으로 자동 실행하고 비교 결과 저장")
    comparison.add_argument("--live", action="store_true")
    comparison.add_argument("--fresh", action="store_true", help="기존 파일을 보존하고 새로운 비교 시작")
    challenge = sub.add_parser("challenge", help="선택 심화: 대상별 설명과 정책 일치 비교")
    challenge.add_argument("--live", action="store_true")
    sub.add_parser("export", help="작성한 프롬프트 파일 내보내기")
    actual_argv = sys.argv[1:] if argv is None else argv
    if not actual_argv:
        parser.print_help()
        return 0
    args = parser.parse_args(actual_argv)
    try:
        if args.command == "demo":
            documents, tickets, cases = load_data()
            image_url(DATA / "error_screenshot.png")
            summary = {"status": "준비 확인 완료", "mode": "provided_demo",
                       "documents": len(documents), "tickets": len(tickets), "cases": len(cases),
                       "sample_response": fixture_response(sample_answer()),
                       "notice": "제공 고정 예시입니다. 실제 API 응답이 아닙니다. 다음: check policy"}
        elif args.command == "check":
            import checks
            results = checks.run(module, args.stage)
            path = artifact_dir(module) / f"checks-{args.stage}.json"
            save(path, {"mode": "fixture", "results": results})
            for result in results:
                print(f"[{result['status']}] {result['name']}: {result['detail']}")
            passed = sum(result["status"] == "통과" for result in results)
            print(f"검사 항목 {len(results)}개 중 {passed}개 통과. 실제 답변은 별도로 확인하세요. 결과: {path}")
            if passed == len(results):
                return 0
            return 2 if any(result["status"] == "미완료" for result in results) else 1
        elif args.command == "export":
            summary = {"files": export_prompts(module), "path": str(artifact_dir(module))}
        elif args.command == "compare":
            summary = run_comparison(module, args)
        elif args.command == "challenge":
            summary = challenge_run(module, args.live)
        elif args.stage == "retry":
            if args.live:
                parser.error("호출 재시도는 고정 오류를 주입합니다. --live 없이 실행하세요.")
            records = fault_runs(module)
            path = artifact_dir(module) / "run-retry-fixture.json"
            save(path, records)
            summary = {"mode": "fixture", "scenarios": len(records), "path": str(path)}
        else:
            documents, tickets, cases = load_data()
            selection = {"policy": ["Q01", "Q06"], "answer": ["Q01"], "tools": ["Q08"], "image": ["Q10"],
                         "usage": ["Q01", "Q02"], "pipeline": ["Q01", "Q07", "Q10"]}[args.stage]
            mode = "live" if args.live else "fixture"
            path = artifact_dir(module) / f"run-{args.stage}-{mode}.json"
            sender = live_sender() if args.live else None
            records = []
            for case in cases:
                if case["case_id"] not in selection:
                    continue
                for variant in (["baseline", "reasoning"] if args.stage == "policy" else ["reasoning"]):
                    trace = []
                    send = traced_sender(sender if args.live else case_sender(case), trace)
                    result = stage_result(module, args.stage, case, variant, send, documents, tickets)
                    records.append({"mode": mode, "stage": args.stage, "feature": STAGE_NAMES[args.stage],
                                    "case_name": case_name(case), "case_id": case["case_id"],
                                    "variant": variant, "trace": trace, **result})
                    save(path, records)
            summary = {"mode": mode, "records": len(records), "path": str(path),
                       "notice": "fixture는 고정 재생이며 실제 품질, 캐시 측정이 아닙니다."}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except NotImplementedError as error:
        print(f"[미완료] {error}\n현재 기능의 함수를 완성한 뒤 같은 명령을 실행하세요.")
        return 2
    except (ValueError, TransportError) as error:
        print(f"[실행 중단] {error}")
        return 1
    except KeyboardInterrupt:
        print("실행을 중단했습니다. 저장된 compare 결과는 코드와 자료를 바꾸지 않았다면 이어서 실행할 수 있습니다.")
        return 130
