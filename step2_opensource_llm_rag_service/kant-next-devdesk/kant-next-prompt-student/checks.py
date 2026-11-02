"""제공 검증 자료. 전달받은 main 모듈의 구현을 확인합니다.

이 검사가 통과해도 정책 본문 품질, 실제 API 도구, 이미지, 캐시 증거는
따로 검토합니다. fixture의 모범 분류를 실제 모델 결과로 보고하지 마세요.
"""
import base64
import copy
import json

from jsonschema import Draft202012Validator, ValidationError
import support


def expect(condition, detail):
    if not condition:
        raise AssertionError(detail)


def rejects(call, exceptions=(ValueError, ValidationError)):
    try:
        call()
    except exceptions:
        return
    raise AssertionError("거부해야 할 입력을 통과시켰습니다.")


def request_fixture():
    return support.base_request("이것은 검사용 고정 지시입니다.", "원 질문을 보존하세요.", "reasoning")


def valid_answer():
    return support.sample_answer()


def policy_policy(m):
    docs, _, _ = support.load_data()
    first = m.build_instructions(docs, "baseline")
    second = m.build_instructions(docs, "reasoning")
    expect(isinstance(first, str) and "KANT NEXT" in first, "회사, 역할을 포함한 지시문을 작성하세요.")
    expect(all(doc["doc_id"] in first for doc in docs), "모든 제공 문서가 고정 prefix에 필요합니다.")
    expect(first != second, "고급 조건의 점검 지시가 기준선과 같으면 안 됩니다.")
    expect(first == m.build_instructions(list(reversed(docs)), "baseline"), "문서 순서가 바뀌어도 고정 prefix가 같아야 합니다.")
    rejects(lambda: m.build_instructions(docs, "unsupported"))


def answer_schema(m):
    fmt = m.answer_format()["format"]
    expect(fmt["type"] == "json_schema" and fmt["strict"] is True, "strict JSON Schema를 연결하세요.")
    schema = fmt["schema"]
    Draft202012Validator.check_schema(schema)
    expect(schema.get("additionalProperties") is False, "추가 필드를 금지하세요.")
    fields = {"answer", "source_ids", "needs_human", "category"}
    expect(set(schema.get("required", [])) == fields, "네 필드를 모두 필수로 지정하세요.")
    Draft202012Validator(schema).validate(valid_answer())
    for invalid in [{**valid_answer(), "needs_human": "false"},
                    {**valid_answer(), "extra": 1}, {**valid_answer(), "category": "unknown"}]:
        rejects(lambda: Draft202012Validator(schema).validate(invalid))


def validation_case(m, change):
    value = valid_answer()
    value.update(change)
    rejects(lambda: m.validate_answer(json.dumps(value), {"policy-python"}))


def answer_valid(m):
    result = m.validate_answer(json.dumps(valid_answer()), {"policy-python"})
    expect(result == valid_answer(), "유효한 답변을 변조하지 않고 반환하세요.")
    no_source = {**valid_answer(), "source_ids": [], "needs_human": True}
    expect(m.validate_answer(json.dumps(no_source), set()) == no_source, "근거 부족+담당자 확인은 유효합니다.")


def answer_missing(m):
    value = valid_answer()
    del value["category"]
    rejects(lambda: m.validate_answer(json.dumps(value), {"policy-python"}))
    rejects(lambda: m.validate_answer("not JSON", {"policy-python"}))


def answer_repair(m):
    request = request_fixture()
    original = copy.deepcopy(request)
    invalid = support.fixture_response({**valid_answer(), "source_ids": ["unknown-document"]})
    fixed = {**valid_answer(), "answer": "두 번째 모델 출력입니다."}
    replay = support.Replay([support.fixture_response(fixed)])
    events = []
    result = m.finish_answer(replay, request, invalid, {"policy-python"}, events)
    expect(result["answer"] == fixed and result["repair_used"] and result["fallback_reason"] is None,
           "고정 답으로 덮지 말고 두 번째 출력 자체를 재검증해 채택하세요.")
    expect(len(replay.requests) == 1, "수정 요청은 한 번입니다.")
    expect(replay.requests[0]["input"][:len(original["input"])] == original["input"], "원 질문을 보존하세요.")
    expect(request == original, "입력 요청을 밖에서 변경하지 마세요.")
    expect(any(event.get("error_kind") and "error_field" in event for event in events), "오류 유형과 필드 위치를 기록하세요.")


def answer_repair_exhausted(m):
    invalid = support.fixture_response(raw="broken JSON")
    replay = support.Replay([invalid])
    result = m.finish_answer(replay, request_fixture(), invalid, {"policy-python"}, [])
    expect(result["fallback_reason"] == "validation_failed" and result["repair_used"], "두 번째 실패는 종료하세요.")
    expect(result["answer"]["needs_human"] is True and result["answer"]["source_ids"] == [], "안전한 담당자 확인 응답이 필요합니다.")
    m.validate_answer(json.dumps(result["answer"]), {"policy-python"})


def answer_repair_strategies(m):
    hints = []
    invalid_responses = [support.fixture_response(raw="not JSON"),
                         support.fixture_response({**valid_answer(), "needs_human": "false"}),
                         support.fixture_response({**valid_answer(), "source_ids": ["missing"]})]
    for invalid in invalid_responses:
        replay = support.Replay([support.fixture_response(valid_answer())])
        result = m.finish_answer(replay, request_fixture(), invalid, {"policy-python"}, [])
        expect(result["fallback_reason"] is None and result["repair_used"], "수정한 출력도 검증하세요.")
        hint = replay.requests[0]["input"][-1]["content"]
        expect(isinstance(hint, str) and hint.strip(), "수정할 문제를 안내하세요.")
        hints.append(hint)
    expect(len(set(hints)) == 3, "JSON 문법, 스키마, 없는 출처 오류에 맞춰 안내를 구분하세요.")


def terminal_response(m, response, reason):
    replay = support.Replay([])
    result = m.finish_answer(replay, request_fixture(), response, {"policy-python"}, [])
    expect(result["fallback_reason"] == reason and not result["repair_used"], "실패 유형을 구분하고 수정 요청 없이 종료하세요.")
    expect(not replay.requests and result["answer"]["needs_human"] is True, "추가 호출 없이 담당자 확인으로 종료하세요.")


def tools_schema(m):
    tool = m.tool_schema()
    expect(tool["type"] == "function" and tool["name"] == "lookup_ticket" and tool["strict"] is True,
           "lookup_ticket strict function 정의가 필요합니다.")
    schema = tool["parameters"]
    checker = Draft202012Validator(schema)
    checker.validate({"ticket_id": "IT-1042"})
    for invalid in [{}, {"ticket_id": 1042}, {"ticket_id": "X"}, {"ticket_id": "IT-1042", "write": True}]:
        rejects(lambda: checker.validate(invalid))


def tools_lookup(m):
    _, tickets, _ = support.load_data()
    original = copy.deepcopy(tickets)
    result = m.execute_tool("lookup_ticket", '{"ticket_id":"IT-1043"}', tickets)
    expect(result["ok"] is True and result["ticket"]["status"] == "resolved", "제공 데이터에서 실제 조회하세요.")
    result["ticket"]["status"] = "changed"
    expect(tickets == original, "조회 결과 수정으로 원천이 바뀌면 안 됩니다.")
    for name, arguments, error in [
        ("delete_ticket", '{"ticket_id":"IT-1043"}', "unknown_tool"),
        ("lookup_ticket", '{"ticket_id":"IT-9999"}', "not_found"),
        ("lookup_ticket", '{"ticket_id":1043}', "invalid_arguments"),
        ("lookup_ticket", '{"ticket_id":"IT-1043","extra":1}', "invalid_arguments"),
        ("lookup_ticket", '["IT-1043"]', "invalid_arguments"),
        ("lookup_ticket", '{"ticket_id":"IT-1043\\n"}', "invalid_arguments"),
        ("lookup_ticket", 'not json', "invalid_arguments"),
    ]:
        value = m.execute_tool(name, arguments, tickets)
        expect(value.get("ok") is False and value.get("error") == error, f"도구 오류 {error}를 구분하세요.")


def tools_roundtrip(m):
    _, tickets, _ = support.load_data()
    call = support.tool_fixture()
    final = support.fixture_response(valid_answer())
    replay = support.Replay([call, final])
    events = []
    original = request_fixture()
    _, response = m.tool_roundtrip(replay, original, tickets, events)
    expect(response == final and len(replay.requests) == 2, "도구 결과 뒤 최종 모델 응답을 받아야 합니다.")
    forwarded = replay.requests[1]["input"]
    expect(all(item in forwarded for item in call["output"]), "reasoning을 포함한 output 전체를 보존하세요.")
    outputs = [item for item in forwarded if item.get("type") == "function_call_output"]
    expect(len(outputs) == 1 and outputs[0]["call_id"] == "call_fixture_1", "같은 call_id로 연결하세요.")
    expect(json.loads(outputs[0]["output"])["ticket"] == tickets["IT-1043"], "직접 조회한 결과를 모델에 전달하세요.")
    expect(original == request_fixture(), "입력 request를 변경하지 마세요.")
    expect(any(event["event"] == "tool_result" for event in events), "도구 실행 로그가 필요합니다.")


def tools_limit(m):
    _, tickets, _ = support.load_data()
    replay = support.Replay([support.tool_fixture() for _ in range(4)])
    _, response = m.tool_roundtrip(replay, request_fixture(), tickets, [])
    expect(len(replay.requests) == 4 and response["status"] == "round_limit", "왕복 상한 4에서 종료하세요.")


def tools_multiple(m):
    _, tickets, _ = support.load_data()
    call = support.tool_fixture()
    another = copy.deepcopy(call["output"][1])
    another.update(call_id="call_2", name="unapproved_tool")
    call["output"].append(another)
    replay = support.Replay([call, support.fixture_response(valid_answer())])
    m.tool_roundtrip(replay, request_fixture(), tickets, [])
    outputs = [item for item in replay.requests[1]["input"] if item.get("type") == "function_call_output"]
    expect({item["call_id"] for item in outputs} == {"call_fixture_1", "call_2"}, "각 호출 ID별로 결과를 연결하세요.")
    expect(json.loads(outputs[1]["output"])["error"] == "unknown_tool", "실패 결과도 원 call_id로 전달하세요.")


def image_content(m):
    path = support.DATA / "error_screenshot.png"
    content = m.image_content("이 화면을 확인하세요.", path)
    text = [item for item in content if item.get("type") == "input_text"]
    images = [item for item in content if item.get("type") == "input_image"]
    expect(len(text) == 1 and text[0]["text"] == "이 화면을 확인하세요.", "텍스트도 유지하세요.")
    expect(len(images) == 1 and images[0]["detail"] == "high", "실제 이미지 항목을 추가하세요.")
    expect(base64.b64decode(images[0]["image_url"].split(",", 1)[1]) == path.read_bytes(), "파일명 대신 PNG 바이트를 전달하세요.")
    expect(m.image_content("텍스트만", None) == [{"type": "input_text", "text": "텍스트만"}], "이미지가 없는 경로도 유지하세요.")
    rejects(lambda: m.image_content("  ", None))


def retry_case(m, failures, success, expected_attempts, expected_waits):
    final = support.fixture_response(valid_answer())
    replay = support.Replay(failures + ([final] if success else []))
    events, waits = [], []
    response = m.call_with_retry(replay, request_fixture(), events, sleep=waits.append)
    expect((response == final) if success else response is None, "성공 응답과 실패 None을 구분하세요.")
    expect(len(replay.requests) == expected_attempts and len(events) == expected_attempts, "시도 횟수와 로그 수를 확인하세요.")
    expect(len(waits) == expected_waits and all(value > 0 for value in waits), "다음 시도가 있을 때만 대기하세요.")
    expect([event["attempt"] for event in events] == list(range(1, expected_attempts + 1)), "시도 번호는 1부터입니다.")
    expect(events[-1]["wait_s"] == 0, "마지막 시도 뒤에는 대기하지 않습니다.")
    expect(all(event["event"] == "api_attempt" and event["latency_ms"] >= 0 for event in events), "시도별 지연을 기록하세요.")


def retry_programming_error(m):
    replay = support.Replay([ValueError("student bug")])
    rejects(lambda: m.call_with_retry(replay, {}, [], sleep=lambda _: None), (ValueError,))
    expect(len(replay.requests) == 1, "코드 오류를 API 재시도로 숨기지 마세요.")


def attempt_fixture(response):
    return {"event": "api_attempt", "attempt": 2, "response": response, "latency_ms": 12.5,
            "error_kind": None if response else "http", "status_code": None if response else 503,
            "request_id": "test-request", "retryable": False, "wait_s": 0}


def usage_prefix(m):
    docs, _, _ = support.load_data()
    first = m.cache_settings(docs, "reasoning")
    expect(first == m.cache_settings(list(reversed(docs)), "reasoning"), "고정 prefix/키는 입력 순서에 흔들리지 않아야 합니다.")
    expect(first["instructions"] == m.build_instructions(docs, "reasoning"), "직접 작성한 고정 정책을 연결하세요.")
    expect(first["prompt_cache_key"] != m.cache_settings(docs, "baseline")["prompt_cache_key"], "비교 조건을 키에 구분하세요.")
    changed = copy.deepcopy(docs)
    changed[0]["body"] += " 정책 변경."
    expect(first["prompt_cache_key"] != m.cache_settings(changed, "reasoning")["prompt_cache_key"], "정책 변경이 캐시 버전에 반영되어야 합니다.")


def usage_cost(m):
    response = support.fixture_response(valid_answer(), cached=500, written=200)
    response["usage"]["output_tokens_details"]["reasoning_tokens"] = 20
    prices = support.load_prices()
    log = m.usage_record(attempt_fixture(response), prices)
    expected = (800 * prices["input"] + 500 * prices["cached"] + 200 * prices["cache_write"] + 70 * prices["output"]) / 1e6
    expect(abs(log["estimated_cost_usd"] - expected) < 1e-12, "일반 입력=1500-500-200. reasoning은 output에 중복 가산하지 마세요.")
    expect(log["cache_observation"] == "hit" and log["cache_write_tokens"] == 200 and log["reasoning_tokens"] == 20,
           "cached/write/reasoning 값을 각각 기록하세요.")
    expect(log["price_source"] == prices["source"] and log["price_checked_at"] == prices["checked_at"], "단가 출처와 확인일을 남기세요.")
    expect(log["latency_ms"] == 12.5 and log["attempt"] == 2, "계량과 시도, 지연을 연결하세요.")


def usage_missing(m):
    prices = support.load_prices()
    response = support.fixture_response(valid_answer())
    log = m.usage_record(attempt_fixture(response), prices)
    expect(log["cache_observation"] == "miss" and log["cached_tokens"] == 0, "관측된 0은 miss입니다.")
    del response["usage"]["input_tokens_details"]["cache_write_tokens"]
    log = m.usage_record(attempt_fixture(response), prices)
    expect(log["cache_write_tokens"] is None, "없는 write 계량을 관측된 0으로 바꾸지 마세요.")
    expect(log["estimated_cost_usd"] is None or bool(log["cost_assumption"]), "비용을 추정하면 write 누락 가정을 적으세요.")
    del response["usage"]["input_tokens_details"]["cached_tokens"]
    log = m.usage_record(attempt_fixture(response), prices)
    expect(log["cache_observation"] == "unavailable" and log["estimated_cost_usd"] is None, "계량 없음은 캐시 miss/0원과 다릅니다.")
    log = m.usage_record(attempt_fixture(None), prices)
    expect(log["event"] == "api_error" and log["estimated_cost_usd"] is None and log["input_tokens"] is None,
           "실패 요청에 없는 비용, 토큰을 0으로 만들지 마세요.")
    expect(log["status_code"] == 503 and log["request_id"] == "test-request", "실패 식별 정보도 보존하세요.")


def usage_bad_counters(m):
    response = support.fixture_response(valid_answer(), cached=1400, written=200)
    rejects(lambda: m.usage_record(attempt_fixture(response), support.load_prices()))
    response = support.fixture_response(valid_answer(), cached=-1)
    rejects(lambda: m.usage_record(attempt_fixture(response), support.load_prices()))
    response = support.fixture_response(valid_answer())
    response["usage"]["input_tokens"] = True
    rejects(lambda: m.usage_record(attempt_fixture(response), support.load_prices()))


def usage_partial_contradictions(m):
    for usage in [
        {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 0}},
        {"input_tokens": 100, "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 10}},
        {"input_tokens": 100, "output_tokens": 5, "input_tokens_details": {"cache_write_tokens": 101}},
    ]:
        response = support.fixture_response(valid_answer())
        response["usage"] = usage
        rejects(lambda: m.usage_record(attempt_fixture(response), support.load_prices()))


def usage_long_context(m):
    response = support.fixture_response(valid_answer())
    response["usage"]["input_tokens"] = 272001
    log = m.usage_record(attempt_fixture(response), support.load_prices())
    expect(log["estimated_cost_usd"] is None and log["cost_assumption"], "제공 단가 범위를 넘으면 잘못된 단가로 계산하지 마세요.")


def pipeline(m, replay, image=False):
    docs, tickets, _ = support.load_data()
    return m.run_pipeline(replay, "질문과 화면을 확인하세요.", docs, tickets,
                          image_path=support.DATA / "error_screenshot.png" if image else None,
                          prices=support.load_prices(), sleep=lambda _: None)


def pipeline_integration(m):
    replay = support.Replay([support.TransportError("http", 429), support.tool_fixture(),
                             support.fixture_response({**valid_answer(), "needs_human": "false"}),
                             support.fixture_response(valid_answer(), cached=1024)])
    result = pipeline(m, replay, image=True)
    expect(result["answer"] == valid_answer() and result["fallback_reason"] is None, "최종 답을 검증하세요.")
    expect(result["tool_calls"] == 1 and result["repair_used"], "도구, 복구 경로를 연결하세요.")
    expect(len(replay.requests) == 4, "재시도, 도구, 복구의 실제 호출 흐름을 확인하세요.")
    request = replay.requests[0]
    expect(request.get("prompt_cache_key") and request.get("text") and request.get("tools"), "schema/tool/cache 모두 연결하세요.")
    expect(any(item.get("type") == "input_image" for item in request["input"][0]["content"]), "통합 경로에도 이미지를 연결하세요.")
    logs = result["logs"]
    expect(any(log["event"] == "api_error" for log in logs) and any(log.get("cache_observation") == "hit" for log in logs),
           "성공, 실패, 캐시 로그를 남기세요.")
    expect(result["elapsed_ms"] >= 0 and all("response" not in log for log in logs), "정리한 계량 로그와 전체 지연이 필요합니다.")


def pipeline_fallback(m):
    replay = support.Replay([support.TransportError("http", 503) for _ in range(3)])
    result = pipeline(m, replay)
    expect(result["fallback_reason"] == "api_failure" and result["answer"]["needs_human"], "소진된 API 장애는 안전한 fallback입니다.")
    expect(len(result["logs"]) == 3 and all(log["estimated_cost_usd"] is None for log in result["logs"]), "모든 실패의 비용은 미관측입니다.")


def pipeline_limit(m):
    replay = support.Replay([support.tool_fixture() for _ in range(4)])
    result = pipeline(m, replay)
    expect(result["fallback_reason"] == "round_limit" and len(replay.requests) == 4, "무한 도구 호출을 종료하세요.")


def challenge_policy(m):
    docs, _, _ = support.load_data()
    base = m.build_instructions(docs, "reasoning")
    new = m.build_audience_instructions(docs, "reasoning", "newcomer")
    operator = m.build_audience_instructions(docs, "reasoning", "operator")
    expect(new != operator and new != base and operator != base, "두 독자에게 다른 설명 지시를 설계하세요.")
    expect(all(doc["doc_id"] in new and doc["doc_id"] in operator for doc in docs), "공통 근거 문서를 유지하세요.")
    rejects(lambda: m.build_audience_instructions(docs, "reasoning", "administrator"))


def challenge_audit(m):
    first = {**valid_answer(), "answer": "설치 순서를 안내합니다.",
             "source_ids": ["policy-python", "policy-uv"]}
    second = {**first, "answer": "승인 환경과 처리 항목을 확인합니다.",
              "source_ids": list(reversed(first["source_ids"]))}
    original = copy.deepcopy((first, second))
    result = m.audit_audience_pair(first, second)
    expect(result == {"same_policy": True, "different_explanation": True, "issues": []},
           "출처 순서 차이는 정책 차이가 아닙니다.")
    expect((first, second) == original, "비교 함수는 원래 답변을 바꾸지 않습니다.")
    for field, value in [("category", "incident"), ("needs_human", True), ("source_ids", [])]:
        result = m.audit_audience_pair(first, {**second, field: value})
        expect(result["same_policy"] is False and field in result["issues"], "다른 정책 필드를 표시하세요.")
    result = m.audit_audience_pair(first, {**first, "answer": "  " + first["answer"] + "  "})
    expect(result["same_policy"] is True and result["different_explanation"] is False
           and "same_explanation" in result["issues"], "같은 설명은 앞뒤 공백을 빼고 비교하세요.")


def definitions():
    cases = {
        "policy": [("정책, 고급 조건, 고정 문서 순서", policy_policy)],
        "answer": [("strict 스키마 연결", answer_schema), ("정상, 근거 부족 답변", answer_valid),
               ("필수 필드, JSON 문법", answer_missing), ("진짜 두 번째 응답으로 복구", answer_repair),
               ("복구 소진 후 종료", answer_repair_exhausted), ("오류 종류별 수정 안내", answer_repair_strategies)],
        "tools": [("도구 스키마", tools_schema), ("허용 인자, 읽기 전용 조회", tools_lookup),
               ("reasoning, call_id 왕복", tools_roundtrip), ("도구 왕복 상한", tools_limit),
               ("여러 호출과 도구 오류 연결", tools_multiple)],
        "image": [("텍스트, 실제 PNG 결합", image_content)],
        "retry": [("코드 오류는 재시도하지 않음", retry_programming_error)],
        "usage": [("고정 prefix, 정책 변경 버전", usage_prefix), ("캐시 read/write, 비용", usage_cost),
                ("관측된 0, 미관측, 실패 구분", usage_missing), ("잘못된 계량 거부", usage_bad_counters),
                ("일부 계량 누락 시에도 모순 거부", usage_partial_contradictions),
               ("제공 가격 범위 경계", usage_long_context)],
        "pipeline": [("도구, 이미지, 재시도, 복구, 로그 통합", pipeline_integration),
               ("통합 API 소진 fallback", pipeline_fallback), ("통합 도구 상한 fallback", pipeline_limit)],
        "challenge": [("독자 모드, 공통 근거, 잘못된 모드", challenge_policy),
                      ("대상별 답변의 정책과 설명 비교", challenge_audit)],
    }
    for name, change in [
        ("문자열 boolean", {"needs_human": "false"}), ("숫자 boolean", {"needs_human": 0}),
        ("빈 답변", {"answer": "   "}), ("없는 출처", {"source_ids": ["fake"]}),
        ("중복 출처", {"source_ids": ["policy-python", "policy-python"]}),
        ("근거 없이 담당자 불필요", {"source_ids": []}), ("추가 필드", {"extra": "x"}),
        ("없는 category", {"category": "salary"}), ("숫자 출처", {"source_ids": [123]}),
    ]:
        cases["answer"].append((name, lambda m, value=change: validation_case(m, value)))
    refused = support.fixture_response(output=[{"type": "message", "content": [{"type": "refusal", "refusal": "fixture"}]}])
    for name, response, reason in [("거절", refused, "refusal"),
                                   ("불완전", support.fixture_response(status="incomplete"), "incomplete"),
                                   ("API 실패", None, "api_failure")]:
        cases["answer"].append((name, lambda m, r=response, why=reason: terminal_response(m, r, why)))
    cases["retry"].append(("timeout→429→성공", lambda m: retry_case(m,
        [support.TransportError("timeout"), support.TransportError("http", 429)], True, 3, 2)))
    cases["retry"].append(("503 총 3회 소진", lambda m: retry_case(m,
        [support.TransportError("http", 503) for _ in range(3)], False, 3, 2)))
    for status in [400, 401, 403, 404]:
        cases["retry"].append((f"{status} 즉시 중단", lambda m, s=status:
                           retry_case(m, [support.TransportError("http", s)], False, 1, 0)))
    for kind, status in [("connection", None), ("http", 408), ("http", 409), ("http", 500)]:
        cases["retry"].append((f"{kind}/{status} 후 성공", lambda m, k=kind, s=status:
                           retry_case(m, [support.TransportError(k, s)], True, 2, 1)))
    return cases


def run(module, stage):
    stage = support.normalize_stage(stage)
    table = definitions()
    stages = support.STAGES if stage == "all" else [stage]
    results = []
    for current in stages:
        for name, test in table[current]:
            try:
                test(module)
            except NotImplementedError as error:
                status, detail = "미완료", str(error)
            except Exception as error:
                status, detail = "실패", f"{type(error).__name__}: {error}"
            else:
                status, detail = "통과", "fixture 검증 완료"
            results.append({"stage": current, "name": f"{support.STAGE_NAMES[current]}: {name}", "status": status, "detail": detail})
    return results
