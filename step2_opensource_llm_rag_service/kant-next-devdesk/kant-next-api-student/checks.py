"""단계별 공개 검사. 실제 외부 API와 실제 모델은 호출하지 않습니다.

이 검사의 통과는 실제 수집과 실제 모델 답변의 근거 검토를 대신하지
않습니다. 검사 자료와 정답 구현은 분리되어 있으며 직접 구현한 app 모듈을 검사합니다.
"""
import asyncio
import copy
import inspect
import json
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

import support


class CheckFailure(AssertionError):
    """검사기가 직접 작성한 안전한 피드백만 사용자에게 표시합니다."""


def expect(condition, detail):
    if not condition:
        raise CheckFailure(detail)


def rejects(call):
    try:
        call()
    except (ValueError, ValidationError):
        return
    raise CheckFailure("거부해야 할 입력을 통과시켰습니다.")


def document(doc_id="check-one", **changes):
    value = {
        "doc_id": doc_id,
        "title": "검사용 문서",
        "body": "검사용 고유 근거입니다. 담당자가 설치 상태를 확인합니다.",
        "source_url": f"https://example.invalid/docs/{doc_id}",
        "collected_at": support.FIXTURE_TIME,
        "category": "installation",
    }
    value.update(changes)
    return value


def release(row_id=701, **changes):
    value = {
        "id": row_id,
        "name": "검사용 정식 릴리스",
        "tag_name": "v-check",
        "body": "<p>한글 자료</p><p>검증 &amp; 저장</p>",
        "html_url": f"https://github.com/astral-sh/uv/releases/tag/check-{row_id}",
        "url": "https://api.github.com/internal/not-the-source",
        "published_at": "2026-09-20T12:00:00+09:00",
        "draft": False,
        "prerelease": False,
    }
    value.update(changes)
    return value


def normalized(module, rows):
    return module.normalize_releases([{"page": 1, "items": rows}], support.FIXTURE_TIME)


def verify_partition(result, total, kept, quarantined, excluded):
    expected = (total, kept, quarantined, excluded)
    report = result["quality_report"]
    actual = tuple(report[key] for key in
                   ("input_count", "kept_count", "quarantine_count", "excluded_count"))
    expect(actual == expected, "품질 검사 결과의 입력, 채택, 격리, 제외 건수를 확인하세요.")
    expect(total == kept + quarantined + excluded, "입력 건수와 세 분류의 합이 같아야 합니다.")
    expect(tuple(len(result[key]) for key in ("documents", "quarantine", "excluded")) == expected[1:],
           "저장할 목록과 품질 검사 결과의 건수가 같아야 합니다.")
    expect(len(report["records"]) == total, "모든 원천 행의 처리 결과를 기록하세요.")
    for key in ("quarantine", "excluded"):
        for row in result[key]:
            expect({"page", "row", "id", "reason"} <= set(row), "제외와 격리에 원천 위치와 사유가 필요합니다.")
            expect(row["page"] >= 1 and row["row"] >= 1 and bool(row["reason"]),
                   "페이지와 행은 1부터 시작하고 사유는 비어 있으면 안 됩니다.")


def collect_case(module, kind):
    calls = []
    first = [release(701)]
    second = [release(702)]
    if kind == "empty":
        first = []
    if kind == "wrong_json":
        first = {"message": "배열이 아닙니다"}

    def handler(request):
        calls.append(request)
        index = len(calls)
        expect(request.method == "GET", "릴리스 수집은 GET 요청입니다.")
        expect(str(request.url).startswith(support.GITHUB_URL), "제공한 수집 endpoint를 사용하세요.")
        expect(request.url.params.get("page") == str(index), "page=1부터 성공한 다음 페이지로 진행하세요.")
        expect(request.url.params.get("per_page") == "5", "페이지 크기 5를 요청에 전달하세요.")
        timeout = request.extensions.get("timeout", {})
        expect(timeout.get("read") is not None, "HTTP 수집에 명시적인 timeout을 지정하세요.")
        if index == 2 and kind in {"http503", "http429", "http403"}:
            return httpx.Response(int(kind[4:]), json={"message": "검사용 외부 실패"})
        if index == 2 and kind == "timeout":
            raise httpx.ReadTimeout("검사용 timeout", request=request)
        headers = {}
        if (index == 1 and kind not in {"last", "empty", "wrong_json"}) or kind == "limited":
            headers["Link"] = f'<{support.GITHUB_URL}?page={index + 1}&per_page=5>; rel="next"'
        elif kind == "last":
            headers["Link"] = f'<{support.GITHUB_URL}?page=1&per_page=5>; rel="prev"'
        return httpx.Response(200, json=first if index == 1 else second, headers=headers)

    with tempfile.TemporaryDirectory(prefix="devdesk-check-") as folder:
        target = Path(folder)
        # 이전 성공 파일이 남아 있어도 이번 실패 실행 결과로 교체해야 합니다.
        (target / "raw_pages.json").write_text('[{"stale": true}]', encoding="utf-8")
        (target / "collection_report.json").write_text('{"success": true}', encoding="utf-8")
        with httpx.Client(transport=httpx.MockTransport(handler), timeout=None) as client:
            report = module.collect_releases(client, target, mode="fixture",
                                             collected_at=support.FIXTURE_TIME, max_pages=2, per_page=5)
        raw = json.loads((target / "raw_pages.json").read_text(encoding="utf-8"))
        saved_report = json.loads((target / "collection_report.json").read_text(encoding="utf-8"))
    failed = kind in {"http503", "http429", "http403", "timeout", "wrong_json"}
    pages = 0 if kind == "wrong_json" else 1 if failed or kind in {"last", "empty"} else 2
    expected_raw = [] if pages == 0 else [{"page": 1, "items": first}]
    if pages == 2:
        expected_raw.append({"page": 2, "items": second})
    expect(raw == expected_raw, "성공한 페이지의 원천 객체를 수정 없이 저장하세요.")
    expect(report == saved_report, "반환한 실행 기록와 UTF-8 JSON 파일이 일치해야 합니다.")
    expect(report["mode"] == "fixture" and report["source"] == support.GITHUB_URL,
           "실행 기록에 현재 모드와 수집 출처가 필요합니다.")
    expect(report["collected_at"] == support.FIXTURE_TIME, "전달받은 수집시각을 기록하세요.")
    expect(report["successful_pages"] == pages and report["raw_count"] == sum(len(page["items"]) for page in expected_raw),
           "성공 페이지와 실제 원천 건수를 세세요.")
    expect(report["success"] is (not failed), "부분 수집 실패를 성공으로 표시하면 안 됩니다.")
    expect(report["failed_page"] == (1 if kind == "wrong_json" else 2 if failed else None),
           "실패 페이지와 정상 종료를 구분하세요.")
    expect(report["limited"] is (kind == "limited"), "다음 페이지가 남은 상한 종료만 limited=true입니다.")
    expect(bool(report["error"]) is failed, "성공과 실패의 안전한 사유를 구분하세요.")
    expect(len(calls) == (1 if kind in {"last", "empty", "wrong_json"} else 2),
           "수집 실패는 재시도하거나 건너뛰지 말고 중단하세요.")


def a2_fixture(module):
    pages = support.read_json(support.DATA / "release_pages.json")
    original = copy.deepcopy(pages)
    result = module.normalize_releases(pages, support.FIXTURE_TIME)
    verify_partition(result, 10, 3, 5, 2)
    expect({doc["doc_id"] for doc in result["documents"]} == {"release-uv-101", "release-uv-102", "release-uv-109"},
           "제공 자료의 채택 ID는 101, 102, 109입니다.")
    expect(pages == original, "정제하면서 원천 객체를 변경하면 안 됩니다.")
    expect(result == module.normalize_releases(pages, support.FIXTURE_TIME), "같은 원천과 시각은 같은 결과여야 합니다.")


def a2_clean_and_trace(module):
    row = release(body="<p>alpha</p><b>beta</b> <T> &amp; gamma")
    result = normalized(module, [row])
    verify_partition(result, 1, 1, 0, 0)
    doc = result["documents"][0]
    expect(set(doc) == {"doc_id", "title", "body", "source_url", "collected_at", "category"},
           "문서는 공통 여섯 필드로 구성하세요.")
    expect(doc["body"] == "alpha beta <T> & gamma", "단순 태그 사이를 띄우고 entity를 정리하되 <T> 같은 일반 문자열은 보존하세요.")
    expect(doc["source_url"] == row["html_url"] and doc["collected_at"] == support.FIXTURE_TIME,
           "원문 html_url과 수집시각을 각각의 메타데이터로 보존하세요.")
    expect(doc["category"] == "release", "수집 문서의 범주는 release입니다.")
    expect(result["quality_report"]["records"][0]["published_at"] == row["published_at"],
           "원천 게시시각은 품질 기록에서 추적하고 수집시각으로 덮어쓰지 마세요.")


def a2_fallback(module):
    rows = [release(711, name=None), release(712, name=""), release(713, name="  "), release(714)]
    del rows[-1]["name"]
    result = normalized(module, rows)
    verify_partition(result, 4, 4, 0, 0)
    expect(all(doc["title"] == "v-check" for doc in result["documents"]), "비어 있는 name에는 유효한 tag_name을 사용하세요.")


def a2_invalid(module, change):
    result = normalized(module, [release(**change)])
    verify_partition(result, 1, 0, 1, 0)


def a2_priority(module):
    bad = release(720, body=" ")
    good = release(720)
    rows = [bad, good, copy.deepcopy(good), release(721, draft=True, body=None),
            release(722, prerelease=True), release(723, draft="true", body=None)]
    original = copy.deepcopy(rows)
    result = normalized(module, rows)
    verify_partition(result, 6, 1, 3, 2)
    expect(result["documents"][0]["doc_id"] == "release-uv-720", "첫 번째 유효한 같은 ID의 행을 채택하세요.")
    expect([row["row"] for row in result["quarantine"]] == [1, 3, 6], "형식, 범위, 내용, 중복 순서로 분류하세요.")
    expect(rows == original, "분류하면서 원천을 변경하면 안 됩니다.")


def a2_lengths(module):
    for field in ("title", "body"):
        raw_field = "name" if field == "title" else "body"
        maximum = support.LIMITS[field]
        valid = normalized(module, [release(**{raw_field: "가" * maximum})])
        verify_partition(valid, 1, 1, 0, 0)
        invalid = normalized(module, [release(**{raw_field: "가" * (maximum + 1)})])
        verify_partition(invalid, 1, 0, 1, 0)


def a2_missing_types(module):
    missing_flag = release(731)
    del missing_flag["draft"]
    missing_id = release(732)
    del missing_id["id"]
    result = normalized(module, [None, [], "객체 아님", missing_flag, missing_id])
    verify_partition(result, 5, 0, 5, 0)
    rejects(lambda: module.normalize_releases([], "2026-09-21T00:00:00"))


def a2_url_whitespace(module):
    url = "https://github.com/astral-sh/uv/releases/tag/check-701"
    result = normalized(module, [release(html_url="  " + url + "  ")])
    verify_partition(result, 1, 1, 0, 0)
    expect(result["documents"][0]["source_url"] == url,
           "URL 앞뒤 공백을 정리한 뒤 검사하고 정리한 값을 문서에 넣으세요.")
    rejected = normalized(module, [release(html_url="https://github.com/bad path")])
    verify_partition(rejected, 1, 0, 1, 0)


def a3_document_schema(module):
    value = document()
    expect(module.Document.model_validate(value).model_dump() == value, "유효한 여섯 문서 필드를 보존하세요.")
    for change in ({"doc_id": " "}, {"doc_id": 1}, {"title": " "}, {"body": ""},
                   {"body": 7}, {"source_url": "file:///local"}, {"source_url": "https://"},
                   {"collected_at": "yesterday"}, {"collected_at": "2026-09-21T09:00:00+09:00"},
                   {"category": "other"}, {"extra": True}):
        rejects(lambda change=change: module.Document.model_validate({**value, **change}))
    for field in ("doc_id", "title", "body"):
        maximum = support.LIMITS[field]
        character = "a" if field == "doc_id" else "가"
        module.Document.model_validate({**value, field: character * maximum})
        rejects(lambda field=field, maximum=maximum:
                module.Document.model_validate({**value, field: character * (maximum + 1)}))
    module.Document.model_validate({**value, "category": "release"})


async def a3_document_id_paths(module):
    app = module.create_app(mode="fixture", stage="a3", documents=[])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
        for index, identifier in enumerate(("manual/a", "manual%2Fa", "manual a", "한글", "manual?x", "manual#x")):
            value = document(identifier, source_url=f"https://example.invalid/invalid/{index}")
            response = await client.post("/documents", json=value)
            expect(response.status_code == 422,
                   "문서 ID는 영문, 숫자, 하이픈, 밑줄만 허용하세요. 조회할 수 없는 ID를 등록하면 안 됩니다.")
            rejects(lambda identifier=identifier: module.QueryRequest.model_validate(
                {"question": "문서 확인", "document_ids": [identifier]}))
            rejects(lambda identifier=identifier: module.QueryReply.model_validate(
                {"answer": "확인", "source_ids": [identifier], "needs_human": False, "category": "general"}))
        value = document("manual_API-12", source_url=" https://example.invalid/manual/API-12 ")
        posted = await client.post("/documents", json=value)
        expect(posted.status_code == 201, "허용된 ID와 앞뒤 공백이 있는 URL을 등록할 수 있어야 합니다.")
        loaded = await client.get("/documents/manual_API-12")
        expect(loaded.status_code == 200 and loaded.json() == posted.json(),
               "등록 성공한 문서를 동일한 ID로 조회할 수 있어야 합니다.")
        expect(loaded.json()["source_url"] == value["source_url"].strip(), "API 등록도 URL 앞뒤 공백을 정리하세요.")


def a3_query_schema(module):
    valid = {"question": "  설치 상태를 확인해 주세요.  ", "document_ids": ["check-one"]}
    value = module.QueryRequest.model_validate(valid).model_dump()
    expect(value["question"] == valid["question"].strip() and value["session_id"] == "demo",
           "질문을 정리하고 session_id의 기본값 demo를 적용하세요.")
    for change in ({"question": "aa"}, {"question": " " * 5}, {"question": "가" * 1001},
                   {"question": 123}, {"document_ids": []}, {"document_ids": ["a"] * 2},
                   {"document_ids": ["a", " a "]}, {"document_ids": ["a", "b", "c", "d"]},
                   {"document_ids": [" "]}, {"document_ids": [1]}, {"session_id": " "},
                   {"session_id": "a" * 65}, {"session_id": 1}, {"extra": True}):
        rejects(lambda change=change: module.QueryRequest.model_validate({**valid, **change}))
    rejects(lambda: module.QueryRequest.model_validate({"question": "문서를 확인하세요."}))
    module.QueryRequest.model_validate({"question": "가" * 1000, "document_ids": ["a", "b", "c"], "session_id": "a" * 64})


def a3_reply_schema(module):
    value = {"answer": "확인했습니다.", "source_ids": ["check-one"], "needs_human": False, "category": "installation"}
    module.QueryReply.model_validate(value)
    for change in ({"answer": " "}, {"answer": 1}, {"source_ids": ["check-one", "check-one"]},
                   {"source_ids": [""]}, {"source_ids": [1]}, {"needs_human": "false"},
                   {"needs_human": 0}, {"category": "release"}, {"extra": True}, {"source_ids": []}):
        rejects(lambda change=change: module.QueryReply.model_validate({**value, **change}))
    module.QueryReply.model_validate({**value, "source_ids": [], "needs_human": True})
    for field in value:
        missing = {key: item for key, item in value.items() if key != field}
        rejects(lambda missing=missing: module.QueryReply.model_validate(missing))


async def a3_routes(module):
    app = module.create_app(mode="fixture", stage="a3", documents=[])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
        health = await client.get("/health")
        expect(health.status_code == 200 and health.json() == {"status": "ok", "mode": "fixture", "document_count": 0},
               "빈 저장소의 상태와 문서 개수를 반환하세요.")
        response = await client.get("/documents")
        expect(response.status_code == 200 and response.json() == [], "빈 목록도 200과 빈 배열로 반환하세요.")
        value = document()
        response = await client.post("/documents", json=value)
        expect(response.status_code == 201 and response.json() == value, "문서 등록은 여섯 필드를 보존하고 201로 반환하세요.")
        response = await client.get("/documents/check-one")
        expect(response.status_code == 200 and response.json() == value, "등록한 문서를 ID로 조회할 수 있어야 합니다.")
        expect((await client.get("/health")).json()["document_count"] == 1, "메모리 등록 뒤 문서 수를 갱신하세요.")
        for collision in (value, {**value, "source_url": "https://example.invalid/new"}, {**value, "doc_id": "new-id"}):
            expect((await client.post("/documents", json=collision)).status_code == 409, "ID 또는 출처 URL 중복은 409입니다.")
        expect((await client.get("/documents/not-found")).status_code == 404, "없는 문서는 404입니다.")
        for invalid in ({}, {**value, "body": " "}, {**value, "doc_id": 9}, {**value, "extra": 1}):
            expect((await client.post("/documents", json=invalid)).status_code == 422, "잘못된 등록 요청은 422입니다.")
        response = await client.post("/query", json={"question": "설치 상태 확인", "document_ids": ["check-one"]})
        expect(response.status_code == 501, "문서 API의 /query는 이후 TODO를 호출하지 않고 501로 안내하세요.")
    restarted = module.create_app(mode="fixture", stage="a3", documents=[])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://check") as client:
        expect((await client.get("/documents")).json() == [], "새 앱의 메모리 저장소에 이전 POST가 남으면 안 됩니다.")


def a3_openapi(module):
    schema = module.create_app(mode="fixture", stage="a3", documents=[]).openapi()
    paths = schema["paths"]
    components = schema["components"]["schemas"]
    for name, fields in (("Document", set(document())),
                         ("QueryRequest", {"question", "document_ids", "session_id"}),
                         ("QueryReply", {"answer", "source_ids", "needs_human", "category"})):
        expect(set(components[name]["properties"]) == fields, "OpenAPI의 모델 필드가 과제의 데이터 형식과 같아야 합니다.")
        expect(components[name].get("additionalProperties") is False, "OpenAPI에도 추가 필드 금지가 보여야 합니다.")
    expect({"question", "document_ids"} <= set(components["QueryRequest"]["required"]),
           "문서 선택은 OpenAPI에도 필수로 표시하세요.")
    for path, method, status, model in (("/documents", "post", "201", "Document"),
                                       ("/documents/{doc_id}", "get", "200", "Document"),
                                       ("/query", "post", "200", "QueryReply")):
        response_schema = paths[path][method]["responses"][status]["content"]["application/json"]["schema"]
        expect(response_schema.get("$ref", "").endswith("/" + model), "라우트의 response_model을 해당 모델에 연결하세요.")
    listing = paths["/documents"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    expect(listing.get("type") == "array" and listing.get("items", {}).get("$ref", "").endswith("/Document"),
           "문서 목록의 response_model은 Document 배열입니다.")


def a3_startup_validation(module):
    for documents in ([document(), document()], [document(), document("other", source_url=document()["source_url"])],
                      [document(body=" ")]):
        rejects(lambda documents=documents: module.create_app(mode="fixture", stage="a3", documents=documents))


def a4_prompt(module):
    docs = [document("selected-marker", body="선택된 고유 본문 CHECK_SELECTED_BODY")]
    original = copy.deepcopy(docs)
    instructions, text = module.build_prompt("질문 CHECK_QUESTION", docs)
    expect(isinstance(instructions, str) and instructions.strip(), "문서와 분리한 정책 지침이 필요합니다.")
    value = json.loads(text)
    expect(value["question"] == "질문 CHECK_QUESTION" and value["documents"] == docs,
           "공급자 입력에 원 질문과 현재 선택 문서만 연결하세요.")
    expect(docs == original, "프롬프트를 만들면서 문서 원천을 수정하면 안 됩니다.")
    expect("policy-python" not in instructions and "policy-access" not in instructions,
           "기존 문서가 포함된 system_prompt.txt를 정책 지침에 붙이지 마세요.")


async def a4_model_case(module, event):
    trace = {"calls": [], "events": []}
    docs = [document()]
    config = support.make_config("fixture")
    replay = support.model_transport([event], trace=trace)

    async def checked_transport(request):
        expect(request.method == "POST" and str(request.url) == config["endpoint"],
               "지정된 모델 endpoint에 POST 요청을 보내세요.")
        timeout = request.extensions.get("timeout", {})
        expect(timeout.get("read") == config["http_timeout"] and timeout.get("connect") == config["connect_timeout"],
               "HTTP 단계별 timeout을 config 값으로 명시하세요.")
        expect(request.headers.get("Authorization") == "Bearer " + config["api_key"],
               "제공 키는 Authorization 헤더로만 전달하세요.")
        return await replay.handle_async_request(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(checked_transport), timeout=None) as client:
        if event == "success":
            result = await module.call_model_once(client, "설치 상태를 확인하세요.", docs, config)
            value = result.model_dump()
            expect(set(value) == {"answer", "source_ids", "needs_human", "category"}, "모델 응답은 네 필드로 반환하세요.")
            expect(value["source_ids"] == ["check-one"], "선택한 문서의 출처를 보존하세요.")
        else:
            try:
                await module.call_model_once(client, "설치 상태를 확인하세요.", docs, config)
            except (ValueError, ValidationError):
                pass
            else:
                raise CheckFailure("잘못된 JSON, 스키마와 선택 밖 출처를 거부하세요.")
    expect(len(trace["calls"]) == 1, "모델 연결의 1회 연결에서 재시도하면 안 됩니다.")


async def a4_missing_key(module):
    config = {**support.make_config("fixture"), "mode": "live", "api_key": ""}
    trace = {"calls": [], "events": []}
    async with httpx.AsyncClient(transport=support.model_transport(trace=trace)) as client:
        try:
            await module.call_model_once(client, "설치 상태를 확인하세요.", [document()], config)
        except HTTPException as error:
            expect(error.status_code == 503, "live 키가 없으면 설정 오류 503입니다.")
        else:
            raise CheckFailure("live 설정 오류를 fixture 성공으로 바꾸지 마세요.")
    expect(not trace["calls"], "live 키가 없으면 외부 요청을 보내지 마세요.")


async def a5_retry_case(module, events, status, expected_calls):
    trace = {"calls": [], "events": []}
    sleeps = []
    config = {**support.make_config("fixture"), "attempt_timeout": 0.025, "retry_delay": 0.001}

    async def pause(seconds):
        sleeps.append(seconds)
        await asyncio.sleep(0)

    async with httpx.AsyncClient(transport=support.model_transport(list(events), trace=trace)) as client:
        try:
            result = await module.query_with_retry(client, "설치 상태를 확인하세요.", [document()], config, sleep=pause)
        except HTTPException as error:
            expect(status != 200 and error.status_code == status, "마지막 실패 종류에 맞는 HTTP 상태를 선택하세요.")
            expect(isinstance(error.detail, str) and len(error.detail) < 300, "고정된 짧은 오류 설명을 반환하세요.")
        else:
            expect(status == 200 and result.source_ids == ["check-one"], "실패를 성공 답변으로 바꾸면 안 됩니다.")
    expect(len(trace["calls"]) == expected_calls, "timeout 또는 5xx만 최초 포함 최대 두 번 호출하세요.")
    expect(len(sleeps) == expected_calls - 1, "재시도 직전에만 한 번 비동기로 대기하세요.")
    expect(all(seconds == config["retry_delay"] for seconds in sleeps), "설정한 재시도 대기값을 사용하세요.")


async def a5_invalid_outer(module):
    for body in ({"status": "completed", "output": [None]},
                 {"status": "completed", "output": [{"type": "message", "content": [None]}]},
                 {"status": "completed", "output": "wrong"},
                 {"status": "incomplete", "output": []}):
        calls = []

        async def respond(request):
            calls.append(1)
            return httpx.Response(200, json=body)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            try:
                await module.query_with_retry(client, "설치 상태를 확인하세요.", [document()], support.make_config("fixture"))
            except HTTPException as error:
                expect(error.status_code == 502, "모델 API의 응답 형식이 잘못되어도 502로 알리세요.")
            else:
                raise CheckFailure("완료되지 않았거나 형식이 잘못된 외부 응답을 채택하면 안 됩니다.")
        expect(len(calls) == 1, "응답 형식 오류는 재시도하지 마세요.")


def a6_rate_function(module):
    state = {"start": None, "count": 0}
    for _ in range(30):
        expect(module.admit_query(state, 100.0) == 0, "새 구간의 첫 30회는 허용하세요.")
    expect(module.admit_query(state, 100.0) == 60, "31번째 요청은 남은 60초와 함께 거부하세요.")
    expect(module.admit_query(state, 159.1) == 1, "남은 초는 올림해서 반환하세요.")
    expect(module.admit_query(state, 160.0) == 0, "구간 경계에서는 횟수를 초기화하고 허용하세요.")
    expect(state["count"] == 1, "거부 요청은 횟수를 늘리지 않고 새 구간은 1회부터 시작하세요.")
    other = {"start": None, "count": 0}
    expect(module.admit_query(other, 0.0, limit=1, window=2) == 0, "시각 0도 정상 구간 시작값입니다.")
    expect(module.admit_query(other, 0.5, limit=1, window=2) == 2, "함수 인자의 limit과 window를 사용하세요.")


class MemoryLogger:
    def __init__(self):
        self.lines = []

    def info(self, message, *arguments, **kwargs):
        self.lines.append(str(message) % arguments if arguments else str(message))


async def a6_integration(module):
    now = [100.0]
    trace = {"calls": [], "events": []}
    logger = MemoryLogger()
    payload = {"question": "설치 상태를 확인하세요.", "document_ids": ["check-one"]}
    async with httpx.AsyncClient(transport=support.model_transport(trace=trace)) as model_client:
        app = module.create_app(documents=[document(), document("unselected", body="UNSELECTED_BODY_MARKER")], client=model_client,
                                config=support.make_config("fixture"), clock=lambda: now[0], logger=logger)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
            expect((await client.post("/query", json={})).status_code == 422, "요청 형식 오류는 422입니다.")
            expect((await client.post("/query", json={**payload, "document_ids": ["absent"]})).status_code == 404,
                   "선택한 문서가 없으면 모델 호출 전 404입니다.")
            expect((await client.post("/query", json={**payload, "document_ids": ["check-one", "absent"]})).status_code == 404,
                   "일부 선택 문서만 있어도 없는 ID를 조용히 빼고 진행하면 안 됩니다.")
            expect(not trace["calls"], "잘못된 요청과 없는 문서는 모델을 호출하지 마세요.")
            for _ in range(30):
                response = await client.post("/query", json=payload)
                expect(response.status_code == 200, "형식 오류와 없는 문서 요청은 30회 허용 횟수를 소비하면 안 됩니다.")
                expect(response.headers.get("X-DevDesk-Mode") == "fixture", "응답 헤더에 fixture 모드를 표시하세요.")
            first_input = json.loads(trace["calls"][0]["input"])
            expect([item["doc_id"] for item in first_input["documents"]] == ["check-one"],
                   "서버의 전체 저장소 대신 요청에서 선택한 문서만 모델에 전달하세요.")
            expect("UNSELECTED_BODY_MARKER" not in json.dumps(trace["calls"][0]), "선택하지 않은 문서 본문을 모델에 넣지 마세요.")
            calls_before = len(trace["calls"])
            response = await client.post("/query", json=payload)
            expect(response.status_code == 429 and response.headers.get("Retry-After") == "60",
                   "로컬 한도 초과는 429와 남은 초 Retry-After입니다.")
            expect(len(trace["calls"]) == calls_before == 30, "한도 초과 요청은 모델을 호출하면 안 됩니다.")
            expect((await client.get("/health")).status_code == 200, "질문 한도는 상태 조회를 막으면 안 됩니다.")
            expect((await client.get("/documents")).status_code == 200, "질문 한도는 문서 조회를 막으면 안 됩니다.")
            now[0] = 160.0
            expect((await client.post("/query", json=payload)).status_code == 200, "60초 구간이 갱신되면 요청을 다시 허용하세요.")


async def a6_retry_admission(module):
    trace = {"calls": [], "events": []}
    async with httpx.AsyncClient(transport=support.model_transport([503] + ["success"] * 30, trace=trace)) as model_client:
        app = module.create_app(documents=[document()], client=model_client,
                                config=support.make_config("fixture"), clock=lambda: 100.0, logger=MemoryLogger())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
            for _ in range(30):
                response = await client.post("/query", json={"question": "설치 상태 확인", "document_ids": ["check-one"]})
                expect(response.status_code == 200, "모델 재시도가 사용자 허용 횟수를 추가로 소비하면 안 됩니다.")
            expect(len(trace["calls"]) == 31, "사용자 30회 중 첫 요청만 모델을 두 번 호출해야 합니다.")


async def a6_concurrency(module):
    trace = {"calls": [], "events": []}
    async with httpx.AsyncClient(transport=support.model_transport(delay=0.03, trace=trace)) as model_client:
        app = module.create_app(documents=[document()], client=model_client,
                                config=support.make_config("fixture"), logger=MemoryLogger())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
            responses = await asyncio.gather(*(client.post("/query", json={
                "question": f"설치 상태 확인 {index}", "document_ids": ["check-one"]}) for index in range(3)))
    expect(all(response.status_code == 200 for response in responses), "동시 요청 세 개가 모두 성공해야 합니다.")
    kinds = [event[0] for event in trace["events"]]
    expect(kinds.count("start") == 3 and kinds.count("end") == 3, "각 모델 대기의 시작과 종료를 기록해야 합니다.")
    expect(kinds[:3] == ["start"] * 3, "첫 요청의 대기가 끝나기 전에 나머지 요청도 대기를 시작해야 합니다.")


async def a6_log_privacy(module):
    logger = MemoryLogger()
    markers = ["QUESTION_PRIVATE_MARKER", "DOCUMENT_PRIVATE_MARKER", "TOKEN_PRIVATE_MARKER", "PATH_PRIVATE_MARKER"]
    async with httpx.AsyncClient(transport=support.model_transport()) as model_client:
        app = module.create_app(documents=[document(body=markers[1])], client=model_client,
                                config=support.make_config("fixture"), logger=logger)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
            await client.post("/query", json={"question": markers[0], "document_ids": ["check-one"]},
                              headers={"Authorization": "Bearer " + markers[2]})
            await client.get("/documents/" + markers[3])
            await client.get("/unknown/" + markers[3])
    expect(len(logger.lines) >= 3, "요청이 끝난 뒤 각 요청의 처리 로그를 남기세요.")
    text = "\n".join(logger.lines)
    expect(not any(marker in text for marker in markers), "질문, 문서 본문, 인증값과 실제 경로 ID는 로그에 남기지 마세요.")
    rows = [json.loads(line) for line in logger.lines]
    for row in rows:
        expect(set(row) == {"method", "path", "status", "mode", "elapsed_ms"}, "로그는 지정된 다섯 필드만 기록하세요.")
        expect(row["mode"] == "fixture" and isinstance(row["elapsed_ms"], (int, float)) and row["elapsed_ms"] >= 0,
               "로그에 실행 모드와 음수가 아닌 처리시간을 기록하세요.")
    expect(any(row["path"] == "/documents/{doc_id}" and row["status"] == 404 for row in rows),
           "자료 경로는 실제 ID 대신 라우트 양식으로 기록하세요.")
    expect(any(row["path"] == "<unmatched>" for row in rows), "정의되지 않은 경로는 안전한 공통 양식으로 기록하세요.")


async def a6_provider_error_privacy(module):
    marker = "PROVIDER_PRIVATE_ERROR_MARKER"
    logger = MemoryLogger()
    calls = []

    async def respond(request):
        calls.append(1)
        return httpx.Response(401, json={"error": marker})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as model_client:
        app = module.create_app(documents=[document()], client=model_client,
                                config=support.make_config("fixture"), logger=logger)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
            response = await client.post("/query", json={"question": "설치 상태 확인", "document_ids": ["check-one"]})
    expect(response.status_code == 502 and len(calls) == 1, "공급자 401은 재시도 없이 HTTP 502입니다.")
    expect(marker not in response.text and marker not in "\n".join(logger.lines), "공급자의 원문 오류를 응답이나 로그에 넣지 마세요.")
    expect(response.headers.get("X-DevDesk-Mode") == "fixture", "오류 응답에도 현재 실행 모드를 표시하세요.")


def challenge_function(module):
    before = [document("same"), document("changed"), document("missing"), document("time-only")]
    after = [document("same"), document("changed", body="바뀐 본문", category="general"),
             document("added"), document("time-only", collected_at="2026-09-22T00:00:00Z")]
    original = copy.deepcopy((before, after))
    rows = module.compare_snapshots(before, after)
    expect([row["doc_id"] for row in rows] == sorted(["same", "changed", "missing", "time-only", "added"]),
           "같은 비교 결과가 재현되도록 문서 ID 순서로 반환하세요.")
    by_id = {row["doc_id"]: row for row in rows}
    expect({key: row["status"] for key, row in by_id.items()} == {
        "same": "unchanged", "changed": "changed", "missing": "missing", "time-only": "unchanged", "added": "added"},
        "추가, 변경, 동일, 현재 자료에 없음을 구분하고 시각만의 변경은 제외하세요.")
    expect(set(by_id["changed"]["changed_fields"]) == {"body", "category"}, "실제로 바뀐 내용 필드명을 반환하세요.")
    expect(not by_id["time-only"]["changed_fields"], "수집시각만 바뀌면 내용 변경 필드는 없습니다.")
    expect((before, after) == original and rows == module.compare_snapshots(before, after), "원천을 보존하고 재실행 결과를 같게 만드세요.")


async def challenge_route(module):
    app = module.create_app(mode="fixture", stage="a3", documents=[])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://check") as client:
        response = await client.get("/document-changes")
    expect(response.status_code == 200 and isinstance(response.json(), list), "선택 심화의 경로가 비교 목록을 반환해야 합니다.")
    expected = module.compare_snapshots(support.read_json(support.DATA / "snapshot_before.json"),
                                        support.read_json(support.DATA / "snapshot_after.json"))
    expect(response.json() == expected, "제공한 두 완전한 스냅샷을 비교한 결과를 반환하세요.")


def challenge_boundaries(module):
    expect(module.compare_snapshots([], []) == [], "두 스냅샷이 비었으면 빈 목록입니다.")
    before = [document("z-last"), document("a-first")]
    after = [document("a-first", title="수정된 제목", body="수정된 본문"), document("z-last")]
    saved = copy.deepcopy((before, after))
    result = module.compare_snapshots(before, after)
    expect([row["doc_id"] for row in result] == ["a-first", "z-last"], "결과는 입력 순서와 무관하게 ID 순서로 정렬하세요.")
    expect(set(result[0]["changed_fields"]) == {"title", "body"}, "한 문서에서 바뀐 여러 필드를 모두 반환하세요.")
    expect(result == module.compare_snapshots(list(reversed(before)), list(reversed(after))), "입력 순서가 바뀌어도 결과는 같아야 합니다.")
    expect((before, after) == saved, "비교하며 입력 문서를 수정하면 안 됩니다.")


def cases_for(module):
    """검사 이름은 피드백용이며 각 검사는 새 자료와 저장소에서 시작합니다."""
    groups = {name: [] for name in support.STAGES + ["challenge"]}

    def add(group, name, function, *args):
        groups[support.normalize_stage(group)].append((name, lambda: function(module, *args)))

    for kind, label in (("two", "두 페이지 저장"), ("last", "한 페이지 종료"), ("empty", "빈 마지막 페이지"), ("limited", "다음 페이지가 남은 상한"),
                        ("http503", "두 번째 페이지 503"), ("http429", "수집 429 중단"), ("http403", "수집 403 중단"),
                        ("timeout", "수집 timeout 중단"), ("wrong_json", "배열이 아닌 응답")):
        add("a1", label, collect_case, kind)
    for name, function in (("제공 자료 분류와 재실행", a2_fixture), ("정제와 원천 추적", a2_clean_and_trace),
                           ("제목 대체", a2_fallback), ("분류 순서와 유효한 중복", a2_priority), ("최대 길이 경계", a2_lengths),
                           ("객체와 필수 필드 누락", a2_missing_types)):
        add("a2", name, function)
    add("a2", "URL 앞뒤 공백과 내부 공백", a2_url_whitespace)
    for label, change in (("boolean ID", {"row_id": True}), ("0 ID", {"row_id": 0}), ("문자열 ID", {"row_id": "1"}),
                          ("변환 후 길이를 넘는 ID", {"row_id": 10 ** 100}),
                          ("숫자 제목", {"name": 3}), ("대체 제목도 없음", {"name": None, "tag_name": " "}),
                          ("빈 본문", {"body": " "}), ("숫자 본문", {"body": 3}), ("태그만 있는 본문", {"body": "<p></p>"}),
                          ("잘못된 URL", {"html_url": "file:///test"}), ("호스트 없는 URL", {"html_url": "https://"}),
                          ("잘못된 날짜", {"published_at": "2026-99-99"}), ("시간대 없는 게시시각", {"published_at": "2026-09-20T12:00:00"}),
                          ("boolean 아닌 draft", {"draft": 0}), ("boolean 아닌 prerelease", {"prerelease": "false"})):
        add("a2", label, a2_invalid, change)
    for name, function in (("문서 모델", a3_document_schema), ("질문 모델", a3_query_schema), ("답변 모델", a3_reply_schema),
                           ("문서 HTTP와 문서 API 격리", a3_routes), ("OpenAPI와 응답 모델", a3_openapi), ("시작 자료 검증", a3_startup_validation)):
        add("a3", name, function)
    add("a3", "허용 ID의 등록과 조회", a3_document_id_paths)
    add("a4", "현재 선택 문서만 연결", a4_prompt)
    for event, label in (("success", "비동기 1회 연결"), ("bad_json", "JSON 검증"), ("bad_schema", "응답 타입 검증"), ("bad_source", "선택 밖 출처 검증")):
        add("a4", label, a4_model_case, event)
    add("a4", "live 키 없음", a4_missing_key)
    for name, events, status, count in (
            ("정상 1회", ["success"], 200, 1), ("503 뒤 성공", [503, "success"], 200, 2),
            ("timeout 뒤 성공", ["timeout", "success"], 200, 2), ("반복 timeout", ["timeout", "timeout"], 504, 2),
            ("시도 전체 timeout", ["deadline", "deadline"], 504, 2), ("반복 5xx", [503, 500], 502, 2),
            ("401 재시도 금지", [401], 502, 1), ("공급자 429", [429], 503, 1),
            ("연결 실패", ["connection"], 502, 1), ("JSON 실패", ["bad_json"], 502, 1),
            ("출처 실패", ["bad_source"], 502, 1), ("스키마 실패", ["bad_schema"], 502, 1),
            ("503 뒤 429", [503, 429], 503, 2), ("timeout 뒤 401", ["timeout", 401], 502, 2),
            ("503 뒤 timeout", [503, "timeout"], 504, 2), ("timeout 뒤 503", ["timeout", 503], 502, 2)):
        add("a5", name, a5_retry_case, events, status, count)
    add("a5", "모델 API 응답 형식 검증", a5_invalid_outer)
    for name, function in (("고정 구간 계산", a6_rate_function), ("30회 제한과 복구", a6_integration),
                           ("재시도와 사용자 횟수", a6_retry_admission), ("동시 세 요청의 대기 겹침", a6_concurrency),
                           ("안전한 미들웨어 로그", a6_log_privacy), ("공급자 오류 응답과 로그", a6_provider_error_privacy)):
        add("a6", name, function)
    add("challenge", "문서 변경 비교", challenge_function)
    add("challenge", "변경 조회 API", challenge_route)
    add("challenge", "빈 입력과 순서 및 여러 변경", challenge_boundaries)
    return groups


async def _run_checks(module, stage):
    stage = support.normalize_stage(stage)
    groups = cases_for(module)
    names = support.STAGES if stage == "all" else [stage]
    if any(name not in groups for name in names):
        raise ValueError("검사 기능은 collect, documents, document-api, query, retry, observe, all, challenge 중 하나입니다.")
    results = []
    for group in names:
        for name, function in groups[group]:
            try:
                value = function()
                if inspect.isawaitable(value):
                    await asyncio.wait_for(value, timeout=8.0)
            except NotImplementedError:
                passed, detail = False, "현재 단계의 TODO를 먼저 구현하세요."
            except CheckFailure as error:
                passed, detail = False, str(error) or "예상 결과와 다릅니다."
            except Exception as error:
                passed, detail = False, f"{type(error).__name__}: 입력 형식, 반환값과 현재 단계의 구현을 확인하세요."
            else:
                passed, detail = True, "통과"
            results.append({"name": f"{support.STAGE_LABELS[group]}: {name}", "passed": passed, "detail": detail})
    passed = sum(result["passed"] for result in results)
    return {"stage": stage, "passed": passed, "failed": len(results) - passed, "results": results}


def run_checks(module, stage):
    """CLI에서 호출하는 동기 진입점. all에는 선택 심화를 포함하지 않습니다."""
    return asyncio.run(_run_checks(module, stage))
