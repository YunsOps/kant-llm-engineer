"""KANT NEXT DevDesk: 수집부터 요청 제한까지 빈칸을 순서대로 작성하세요.

support.todo("수집: 페이지와 크기") 같은 부분을 아래 설명에 맞는 값이나 코드로 바꿉니다.
모델 필드를 작성한 뒤에는 해당 검증 함수의 support.todo 한 줄을 지웁니다.
반복문, 오류 처리 순서와 비동기 실행 코드는 제공합니다. 현재 단계만 읽어도 됩니다.
"""

import asyncio
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Annotated, Literal

from fastapi import HTTPException
import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

import support


POLICY_INSTRUCTIONS = support.B1_POLICY
POLICY_SOURCE = "B1"


# 자료 수집. 원천 수집: 성공한 페이지만 보존하고 실패하면 중단합니다.
def collect_releases(client, output_dir, *, mode, collected_at, max_pages=2, per_page=5):
    # 작성 메모: 공개 API는 릴리스 IDㆍ게시시각과 페이지 링크를 구조화해 주어 화면 HTML 변화에 덜 의존합니다.
    # 공개 호출에도 제한이 있으므로 두 페이지만 요청하고, HTTP 오류는 부분 성공과 구분해 중단합니다.
    # 관측(2026-10-22): 실제 수집은 2페이지ㆍ10건, limited=True였다. 다음 페이지가 남아 있어 전체 이력을 뜻하지 않는다.
    # 수집: 페이지와 크기: 현재 page와 per_page를 담은 dict. 예: {"키": 변수}.
    # 수집: HTTP 상태 검사: 응답의 HTTP 오류를 확인하는 메서드를 호출하세요.
    # 수집: 다음 페이지 확인: response.links 안에 다음 페이지를 뜻하는 "next"가 있는지 판단하세요.
    # 수집: 저장할 데이터: 반복문에서 받은 value를 JSON 파일에 저장하세요.
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("max_pages는 양의 정수여야 합니다.")
    if type(per_page) is not int or not 1 <= per_page <= 100:
        raise ValueError("per_page는 1~100의 정수여야 합니다.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    report = {
        "mode": mode,
        "source": support.GITHUB_URL,
        "collected_at": collected_at,
        "successful_pages": 0,
        "raw_count": 0,
        "success": False,
        "failed_page": None,
        "limited": False,
        "error": None,
    }

    def save_current_run():
        # 새 실행은 예전 성공 파일을 재사용하지 않습니다. 한글도 그대로 저장합니다.
        for name, value in (("raw_pages.json", pages), ("collection_report.json", report)):
            with (output_dir / name).open("w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")

    save_current_run()
    for page in range(1, max_pages + 1):
        try:
            response = client.get(
                support.GITHUB_URL,
                params={"page": page, "per_page": per_page},
                headers=support.GITHUB_HEADERS,
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
            response.raise_for_status()
            items = response.json()
            if not isinstance(items, list):
                raise ValueError("JSON 응답이 배열이 아닙니다.")
        except httpx.HTTPStatusError as exc:
            report["failed_page"] = page
            report["error"] = f"http_{exc.response.status_code}"
            break
        except httpx.TimeoutException:
            report["failed_page"] = page
            report["error"] = "timeout"
            break
        except httpx.RequestError:
            report["failed_page"] = page
            report["error"] = "connection_error"
            break
        except ValueError:
            report["failed_page"] = page
            report["error"] = "invalid_json_array"
            break

        # API에서 받은 객체를 수정하지 않습니다. 정제는 문서 정제에서 따로 진행합니다.
        pages.append({"page": page, "items": items})
        report["successful_pages"] += 1
        report["raw_count"] += len(items)
        has_next = "next" in response.links
        if not has_next:
            report["success"] = True
            break
        if page == max_pages:
            report["success"] = True
            report["limited"] = True
    save_current_run()
    return report


# 문서 정제. 입력을 바꾸지 않고 새 문서와 품질 기록을 만듭니다.
def clean_text(value):
    return support.clean_text(value)


def validate_url(value):
    return support.validate_url(value)


def validate_timestamp(value, *, utc=False):
    return support.validate_timestamp(value, utc=utc)


def normalize_releases(raw_pages, collected_at):
    # 작성 메모: body는 답변 근거이고 출처 URLㆍID는 원문을 추적하는 메타데이터입니다.
    # 게시시각은 원천의 이력, 수집시각은 이번 관측 시점이므로 따로 보존하고 유효한 행만 중복 집합에 넣습니다.
    # 관측: 제공 10행은 채택 3ㆍ격리 5ㆍ제외 2, 이번 실제 수집 10행은 모두 채택됐다. 건수는 구현 조건으로 사용하지 않는다.
    # 정제: 플래그 자료형: draft나 prerelease 중 boolean이 아닌 값이 있는지 판단합니다.
    # 정제: 제목 대체: 유효한 name을 쓰고, 비었으면 tag_name을 고릅니다.
    # 정제: 빈 본문: 정리한 body가 빈 문자열인지 판단합니다.
    # 정제: 중복 ID: raw_id가 이미 채택한 accepted_ids에 있는지 확인합니다.
    # 문서에 넣을 값: 앞에서 정리한 본문, URL, 이번 수집시각을 문서에 넣습니다.
    validate_timestamp(collected_at, utc=True)
    documents, quarantine, excluded, records = [], [], [], []
    accepted_ids = set()

    for page in raw_pages:
        for row, item in enumerate(page["items"], start=1):
            raw_id = item.get("id") if isinstance(item, dict) else None
            published_at = item.get("published_at") if isinstance(item, dict) else None
            location = {"page": page["page"], "row": row, "id": raw_id}
            reason = None
            status = "quarantine"
            title, body = None, None

            if not isinstance(item, dict):
                reason = "invalid_object"
            elif type(raw_id) is not int or raw_id <= 0 or len(f"release-uv-{raw_id}") > support.LIMITS["doc_id"]:
                reason = "invalid_id"
            elif any(type(item.get(flag)) is not bool for flag in ("draft", "prerelease")):
                reason = "invalid_flags"
            elif item["draft"] or item["prerelease"]:
                status = "excluded"
                reason = "draft" if item["draft"] else "prerelease"
            else:
                name = item.get("name")
                if name is not None and not isinstance(name, str):
                    reason = "invalid_name"
                else:
                    source_title = name if isinstance(name, str) and name.strip() else item.get("tag_name")
                    if not isinstance(source_title, str) or not source_title.strip():
                        reason = "missing_title"
                    else:
                        title = clean_text(source_title)
                        if not title:
                            reason = "missing_title"
                        elif len(title) > support.LIMITS["title"]:
                            reason = "title_too_long"
                if reason is None:
                    if not isinstance(item.get("body"), str):
                        reason = "invalid_body"
                    else:
                        body = clean_text(item["body"])
                        if not body:
                            reason = "empty_body"
                        elif len(body) > support.LIMITS["body"]:
                            reason = "body_too_long"
                if reason is None:
                    try:
                        source_url = validate_url(item.get("html_url"))
                    except ValueError:
                        reason = "invalid_url"
                if reason is None:
                    try:
                        validate_timestamp(published_at)
                    except ValueError:
                        reason = "invalid_published_at"
                if reason is None and raw_id in accepted_ids:
                    reason = "duplicate_id"
                if reason is None:
                    status = "kept"
                    accepted_ids.add(raw_id)
                    documents.append({
                        "doc_id": f"release-uv-{raw_id}",
                        "title": title,
                        "body": body,
                        "source_url": source_url,
                        "collected_at": collected_at,
                        "category": "release",
                    })

            if status == "quarantine":
                quarantine.append({**location, "reason": reason})
            elif status == "excluded":
                excluded.append({**location, "reason": reason})
            records.append({**location, "published_at": published_at, "status": status, "reason": reason})

    quality_report = {
        "input_count": len(records),
        "kept_count": len(documents),
        "quarantine_count": len(quarantine),
        "excluded_count": len(excluded),
        "records": records,
    }
    return {"documents": documents, "quarantine": quarantine, "excluded": excluded, "quality_report": quality_report}


# 문서 API. 문자열 정리와 타입 검증은 모든 모델에 공통으로 적용합니다.
class CourseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    # Literal 범주도 일반 str 필드와 동일하게 앞뒤 공백을 정리하되 자료형은 바꾸지 않습니다.
    @field_validator("*", mode="before")
    @classmethod
    def strip_string(cls, value):
        return value.strip() if isinstance(value, str) else value


DocumentId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=support.LIMITS["doc_id"], pattern=r"^[A-Za-z0-9_-]+$")]


class Document(CourseModel):
    doc_id: DocumentId
    title: str = Field(min_length=1, max_length=support.LIMITS["title"])
    body: str = Field(min_length=1, max_length=support.LIMITS["body"])
    source_url: str = Field(min_length=1, max_length=support.LIMITS["source_url"])
    collected_at: str
    category: Literal["installation", "access", "incident", "general", "release"]

    @model_validator(mode="after")
    def validate_rules(self):
        validate_url(self.source_url)
        validate_timestamp(self.collected_at, utc=True)
        return self


class QueryRequest(CourseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[DocumentId] = Field(min_length=1, max_length=3)
    session_id: str = Field(default="demo", min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_rules(self):
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("document_ids는 중복될 수 없습니다.")
        return self


class QueryReply(CourseModel):
    answer: str = Field(min_length=1)
    source_ids: list[DocumentId]
    needs_human: bool
    category: Literal["installation", "access", "incident", "general"]

    @model_validator(mode="after")
    def validate_rules(self):
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids는 중복될 수 없습니다.")
        if not self.source_ids and not self.needs_human:
            raise ValueError("출처가 없으면 담당자 확인이 필요합니다.")
        return self


def response_models():
    # 응답 모델: 단건 문서는 Document, 질문 답변은 QueryReply 구조를 사용합니다.
    return {"documents": list[Document], "document": Document, "query": QueryReply}


def find_document(store, doc_id):
    # 작성 메모: GET은 경로의 ID를, POST는 JSON 본문을 받아 검증된 모델을 등록합니다.
    # 없는 ID는 404, 입력 형식 오류는 422, 유효한 등록의 IDㆍURL 충돌은 409로 구분합니다.
    # 경계 관측: 제목 300자는 POST 201ㆍGET 200, 301자는 422였다. 요청ㆍ응답은 artifacts/fixture/http-smoke.json에 보관했다.
    # 문서 API: 없는 문서: store에 doc_id가 없는 경우만 404로 끝냅니다.
    if doc_id not in store:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return store[doc_id]


def register_document(store, document):
    # 문서 API: 중복 ID: document.doc_id가 store에 이미 있는지 확인하세요.
    # 문서 API: 중복 URL: store.values()의 문서 중 source_url이 같은 문서가 있는지 확인하세요.
    # any(조건 for 항목 in 목록)는 조건을 만족하는 항목이 하나라도 있으면 True입니다.
    duplicate_id = document.doc_id in store
    duplicate_url = any(stored.source_url == document.source_url for stored in store.values())
    if duplicate_id or duplicate_url:
        raise HTTPException(status_code=409, detail="문서 ID 또는 출처 URL이 이미 등록되어 있습니다.")
    store[document.doc_id] = document
    return document


# 앱 생성과 라우트 선언은 제공됩니다. 위 함수를 실제 API에 연결합니다.

# 모델 연결. 현재 선택된 문서만 연결하고 실제 HTTP 요청을 비동기로 기다립니다.
def build_prompt(question, documents):
    # 실제 응답 3건을 본문과 대조해 Python 3.12 안내ㆍ출장비 담당자 연결ㆍ공개 릴리스와 사내 승인 정책 구분을 확인했다.
    # 이는 이번 정상 연결의 관측이며, 모든 질문에 대한 사실성을 보장하지는 않는다.
    # 모델 연결: 질문과 문서: question과 selected를 각각 question, documents 키에 담으세요.
    selected = [document.model_dump() if isinstance(document, BaseModel) else dict(document) for document in documents]
    input_text = json.dumps({"question": question, "documents": selected}, ensure_ascii=False)
    return POLICY_INSTRUCTIONS, input_text


async def call_model_once(client, question, documents, config):
    # HTTP 요청과 await는 제공합니다. 아래 응답 검증에서 실제 응답을 검사하세요.
    # 모델 연결: 응답 JSON: text를 json.loads로 읽습니다. 모델 검증은 다음 호출이 맡습니다.
    # 모델 연결: 출처 검사: reply.source_ids에 selected_ids에 없는 ID가 있는지 판단합니다.
    if config["mode"] == "live" and not config.get("api_key"):
        raise HTTPException(status_code=503, detail="실제 모델 연결 설정이 필요합니다.")
    instructions, input_text = build_prompt(question, documents)
    payload = support.provider_payload(instructions, input_text, config["model"])
    response = await client.post(
        config["endpoint"],
        headers={"Authorization": f"Bearer {config.get('api_key', '')}"},
        json=payload,
        timeout=httpx.Timeout(config["http_timeout"], connect=config["connect_timeout"]),
    )
    response.raise_for_status()
    text = support.extract_output(response.json())
    reply = QueryReply.model_validate(json.loads(text))
    selected_ids = {document.doc_id if isinstance(document, BaseModel) else document["doc_id"] for document in documents}
    if any(source_id not in selected_ids for source_id in reply.source_ids):
        raise ValueError("선택하지 않은 문서를 출처로 반환했습니다.")
    return reply


# 실패 처리. 시도 전체의 종료 시한도 HTTP 단계별 timeout과 같은 규칙으로 처리합니다.
async def query_with_retry(client, question, documents, config, *, sleep=asyncio.sleep):
    # 작성 메모: await는 네트워크ㆍ재시도 대기 중 다른 요청이 진행되도록 합니다.
    # 일시적인 timeoutㆍ5xx만 최초 포함 두 번으로 제한해 지연과 중복 과금을 줄이고 마지막 실패를 그대로 구분합니다.
    # attempt는 첫 시도에서 0, 두 번째 시도에서 1입니다.
    # 실패 처리: timeout 재시도: timeout이 첫 시도에서 발생했을 때만 다시 요청합니다.
    # 실패 처리: HTTP 재시도: 첫 시도의 500~599 응답만 다시 요청합니다.
    # 실패 처리: 공급자 429: 공급자의 429는 우리 서버의 호출 제한과 구분해 503으로 반환합니다.
    for attempt in range(2):
        try:
            return await support.attempt_with_deadline(
                call_model_once(client, question, documents, config), config["attempt_timeout"],
            )
        except (TimeoutError, httpx.TimeoutException):
            if attempt == 0:
                await sleep(config["retry_delay"])
                continue
            raise HTTPException(status_code=504, detail="모델 응답 제한 시간을 초과했습니다.") from None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if attempt == 0 and 500 <= status <= 599:
                await sleep(config["retry_delay"])
                continue
            if status == 429:
                raise HTTPException(status_code=503, detail="모델 공급자의 호출 한도에 도달했습니다.") from None
            raise HTTPException(status_code=502, detail="모델 공급자가 정상 응답을 반환하지 않았습니다.") from None
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="모델 공급자에 연결하지 못했습니다.") from None
        except (ValueError, TypeError, KeyError):
            raise HTTPException(status_code=502, detail="모델 응답의 형식 또는 출처가 올바르지 않습니다.") from None


# 요청 제한과 기록. await가 없는 작은 함수 안에서 구간 판단과 횟수 변경을 끝냅니다.
def admit_query(state, now, *, limit=30, window=60):
    # 처음에는 state={"start": None, "count": 0}입니다. start=0은 정상 시각입니다.
    # 요청 제한: 구간 갱신: 첫 요청이거나 현재 구간이 window초 이상 지났는지 판단합니다.
    # 요청 제한: 한도 확인: 현재 count가 limit에 도달했는지 판단합니다.
    # 요청 제한: 요청 수 증가: 허용한 사용자 요청 한 건을 셉니다. 모델 재시도는 여기로 돌아오지 않습니다.
    if state["start"] is None or now - state["start"] >= window:
        state["start"] = now
        state["count"] = 0
    if state["count"] >= limit:
        return max(1, math.ceil(window - (now - state["start"])))
    state["count"] += 1
    return 0


async def request_logging(request, call_next, *, mode, logger):
    # 기록: 로그 필드: 아래 다섯 키만 담은 dict를 작성하세요.
    # method=request.method, path=support.safe_route(request),
    # status=response.status_code, mode=mode, elapsed_ms=elapsed_ms.
    # 질문, 문서 본문, 원래 URL과 인증 헤더는 넣지 않습니다.
    started_at = time.monotonic()
    response = await call_next(request)
    elapsed_ms = round((time.monotonic() - started_at) * 1000, 3)
    fields = {"method": request.method, "path": support.safe_route(request),
              "status": response.status_code, "mode": mode, "elapsed_ms": elapsed_ms}
    logger.info(json.dumps(fields, ensure_ascii=False))
    response.headers["X-DevDesk-Mode"] = mode
    return response



def create_app(*, mode="fixture", stage="observe", documents=None, config=None, client=None, clock=time.monotonic, logger=None):
    return support.create_service(sys.modules[__name__], mode=mode, stage=stage,
        documents=documents, config=config, client=client, clock=clock, logger=logger)


# 선택 심화: 필수 실행 경로에서는 호출하지 않습니다.
def compare_snapshots(before, after):
    """ID별 added/changed/unchanged/missing과 changed_fields를 반환합니다.

    title, body, source_url, category만 비교하며 collected_at 변경은 제외합니다.
    입력을 수정하지 않고 doc_id 순서로 정렬합니다. 자세한 예시는 과제 본문에 있습니다.
    필수와 달리 함수의 순서와 자료구조부터 직접 구성하세요.
    """
    # ID별 색인으로 입력 순서와 무관하게 비교하며, missing을 실제 삭제로 해석하지 않습니다.
    previous = {document["doc_id"]: document for document in before}
    current = {document["doc_id"]: document for document in after}
    fields = ("title", "body", "source_url", "category")
    changes = []
    for doc_id in sorted(previous.keys() | current.keys()):
        changed_fields = []
        if doc_id not in previous:
            status = "added"
        elif doc_id not in current:
            status = "missing"
        else:
            changed_fields = [field for field in fields if previous[doc_id][field] != current[doc_id][field]]
            status = "changed" if changed_fields else "unchanged"
        changes.append({"doc_id": doc_id, "status": status, "changed_fields": changed_fields})
    return changes


if __name__ == "__main__":
    support.main(sys.modules[__name__])
