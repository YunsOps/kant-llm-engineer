"""KANT NEXT DevDesk. todo(...)를 필요한 표현이나 코드로 바꿉니다."""
import copy
import json
import sys
import time

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnableParallel, RunnablePassthrough

import support

# 앞 과제의 B2를 가져온다면 정책 지침만 사용합니다. 문서는 context로 전달합니다.
POLICY_INSTRUCTIONS = support.B1_POLICY + """
category는 현재 질문의 업무 종류에 따라 정합니다.
Pythonㆍuv 버전, 설치, 가상환경과 CPU/GPU 실행 환경 문의는 installation입니다.
API 키 보관, 인증과 접근 권한 문의는 access, 서비스 장애와 복구ㆍ티켓 문의는 incident입니다.
나머지 일반 안내와 지원 범위 밖 문의는 general입니다.
짧은 버전 확인이나 후속 질문도 대상이 개발환경이면 installation을 유지하세요.
"""
POLICY_SOURCE = "B1+category"
# 관측(2026-10-22): 기본 지침에서 짧은 Python 버전 문의가 general로 분류되어 범주 지침을 보완했다.
# 보완 후 실제 기본 답변ㆍ후속 대화ㆍ스트림ㆍ체인 재사용 7건은 모두 installation과 올바른 출처를 반환했다.


def todo(description):
    """제공: 빈칸을 실행하면 작성할 내용을 알려 줍니다. 이 함수는 수정하지 않습니다."""
    raise NotImplementedError(description)


# 필수 1: 문서 검색
def to_documents(rows, keywords):
    """문서 변환: 본문과 metadata를 나눈 Document를 만듭니다."""
    documents = []
    for row in rows:
        metadata = {key: copy.deepcopy(value) for key, value in row.items() if key != "body"}
        defaults = ["uv", "릴리스", "release"] if row["category"] == "release" else []
        metadata["keywords"] = list(keywords.get(row["doc_id"], defaults))
        document = Document(page_content=row["body"], metadata=metadata)
        documents.append(document)
    return documents


def search_documents(query, documents, allowed_ids, top_k=3):
    """키워드 검색: 후보를 제한하고 일치한 키워드 수로 검색합니다."""
    if type(top_k) is not int or not 1 <= top_k <= 3:
        raise ValueError("top_k는 1~3의 정수입니다.")
    normalized = query.casefold()
    allowed = set(allowed_ids)
    scored = []
    for index, document in enumerate(documents):
        if document.metadata["doc_id"] not in allowed:
            continue
        words = {word.casefold() for word in document.metadata.get("keywords", []) if word.strip()}
        score = sum(word in normalized for word in words)
        if score > 0:
            scored.append((score, index, document))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:top_k]]


def format_context(documents):
    """제공: 검색 문서를 제목, 출처, 본문으로 표시합니다."""
    if not documents:
        return "검색된 문서가 없습니다."
    return "\n\n".join(
        f'<document id="{doc.metadata["doc_id"]}">\n'
        f'제목: {doc.metadata["title"]}\n출처: {doc.metadata["source_url"]}\n'
        f'{doc.page_content}\n</document>' for doc in documents)


def build_context_chain(documents):
    """검색 입력 연결: 입력 보존과 검색을 병렬로 연결합니다."""
    # 작성 이유: 원입력 보존과 검색은 서로의 결과가 필요 없어 같은 입력에서 독립적으로 실행합니다.
    # 검색을 별도 Runnable로 두면 검색 방식만 교체해도 요청ㆍ이력을 보존하는 나머지 연결을 유지할 수 있습니다.
    def retrieve(value):
        query = support.search_query(value["question"], value["history"])
        return search_documents(query, documents, value["document_ids"])

    def merge(value):
        return {**value["original"], "documents": value["documents"],
                "context": format_context(value["documents"])}

    preserve = RunnablePassthrough().with_config(run_name="preserve_input")
    retrieve_chain = RunnableLambda(retrieve).with_config(run_name="retrieve")
    parallel = RunnableParallel(original=preserve, documents=retrieve_chain)
    return parallel.with_config(run_name="parallel_prepare") | RunnableLambda(merge).with_config(run_name="merge_context")


# 필수 2: 기본 체인
def build_prompt_and_parser():
    """프롬프트와 파서: 답변 형식과 이전 대화 자리를 연결합니다."""
    parser = PydanticOutputParser(pydantic_object=support.Answer)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{policy}\n\n출력 형식:\n{format_instructions}\n\n이번 검색 문서:\n{context}"),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ]).partial(policy=POLICY_INSTRUCTIONS, format_instructions=parser.get_format_instructions())
    return prompt.with_config(run_name="prompt"), parser.with_config(run_name="parser")


def validate_sources(answer, documents):
    """출처 검사: 이번에 검색한 문서만 출처로 허용합니다."""
    answer = support.Answer.model_validate(answer)
    allowed = {document.metadata["doc_id"] for document in documents}
    if len(answer.source_ids) != len(set(answer.source_ids)):
        raise support.SourceValidationError("출처가 중복됩니다.")
    if any(source_id not in allowed for source_id in answer.source_ids):
        raise support.SourceValidationError("이번 검색 결과에 없는 출처입니다.")
    if not answer.source_ids and not answer.needs_human:
        raise support.SourceValidationError("근거 없는 답변에는 담당자 확인이 필요합니다.")
    return answer


def build_primary_chain(model):
    """기본 체인 연결: prompt, model, parser와 출처 검사를 연결합니다."""
    prompt, parser = build_prompt_and_parser()
    generate = prompt | model | parser

    def finish(value):
        answer = validate_sources(value["parsed"], value["documents"])
        return {"reply": answer, "route": "primary"}

    return (RunnablePassthrough.assign(parsed=generate.with_config(run_name="generate_parse"))
            | RunnableLambda(finish).with_config(run_name="validate_sources")).with_config(run_name="primary")


def build_answer_chain(model, reliable=False):
    """문서 없음 분기: 문서가 없으면 모델을 호출하지 않습니다."""
    primary = build_primary_chain(model)
    if reliable:
        primary = build_resilient_chain(primary)
    no_documents = RunnableLambda(lambda value: {"reply": support.safe_answer("no_documents"),
                                                "route": "no_documents"})
    def has_no_documents(value):
        return not value["documents"]
    return RunnableBranch((has_no_documents, no_documents), primary).with_config(run_name="route_by_documents")


# 필수 3: 대화 이력
def get_history(store, session_id):
    """세션 이력: 세션마다 별도의 이력 객체를 보관합니다."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id는 비어 있지 않은 문자열입니다.")
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


def commit_history(store, session_id, question, outcome):
    """이력 저장: 완료된 primary의 질문과 답변만 저장합니다."""
    # 작성 이유: 검색 문서는 현재 답변의 사실 근거이고 대화 이력은 후속 질문의 대상을 해석하는 자료입니다.
    # 검증된 primary만 저장해야 실패 안내나 폐기된 임시 출력이 다음 대화의 확정 답변으로 섞이지 않습니다.
    # 관측: 실제 A 두 턴 뒤 4개, B 한 턴 뒤 2개 메시지가 남았고 B 답변에 A의 표식이 섞이지 않았다.
    if outcome["route"] != "primary":
        return
    answer = support.Answer.model_validate(outcome["reply"])
    messages = [HumanMessage(content=question), AIMessage(content=answer.answer)]
    get_history(store, session_id).add_messages(messages)


# 필수 4: 실패 복구
def build_resilient_chain(primary):
    """실패 복구: 허용 오류에만 처음을 포함해 최대 두 번 시도합니다."""
    retry = primary.with_retry(retry_if_exception_type=support.RECOVERABLE,
                               stop_after_attempt=2, wait_exponential_jitter=False)
    fallback = RunnableLambda(lambda value: {"reply": support.safe_answer("fallback"),
                                            "route": "fallback"}).with_config(run_name="fallback")
    return retry.with_fallbacks([fallback], exceptions_to_handle=support.RECOVERABLE)


# 필수 5: 스트리밍
def stream_answer(prepared, model, config=None):
    """청크 전달: 아래 순서대로 청크 전달, 검증과 실패 분기를 채웁니다."""
    # 관측 메모: midstream의 model_error(TemporaryModelError)는 같은 요청의 부모 run으로 이어졌고, reset 뒤 final fallbackㆍ모델 1회로 종료했다.
    # 실제 정상 실행은 final primaryㆍ모델 1회ㆍ텍스트 38청크였으며 usage는 입력 750ㆍ출력 42ㆍ합계 792토큰이었다. 청크 수와 토큰 수는 다르다.
    if not prepared["documents"]:
        yield {"type": "final", "reply": support.safe_answer("no_documents").model_dump(), "route": "no_documents"}
        return
    prompt, parser = build_prompt_and_parser()
    stream_chain = prompt | model
    sent_delta = False
    for attempt in range(2):
        iterator = stream_chain.stream(prepared, config=config)
        parts = []
        try:
            for chunk in iterator:
                text = support.message_text(chunk)
                if text:
                    parts.append(text)
                    sent_delta = True
                    yield {"type": "delta", "text": text}
            parsed = parser.invoke("".join(parts), config=config)
            answer = validate_sources(parsed, prepared["documents"])
            yield {"type": "final", "reply": answer.model_dump(), "route": "primary"}
            return
        except support.RECOVERABLE:
            if not sent_delta and attempt == 0:
                continue
            if sent_delta:
                yield {"type": "reset", "reason": "unverified_output"}
            yield {"type": "final", "reply": support.safe_answer("fallback").model_dump(), "route": "fallback"}
            return
        except Exception:
            if sent_delta:
                yield {"type": "reset", "reason": "execution_error"}
            raise
        finally:
            # 제공: 정상, 실패, 소비 중단 모두에서 하위 스트림을 닫습니다.
            iterator.close()


class TraceHandler(BaseCallbackHandler):
    """실행 기록: 잠금, 상태 보관과 기록 형식은 제공됩니다. 측정할 값만 채웁니다."""
    raise_error = True

    def __init__(self, mode="fixture", path=None, clock=time.perf_counter):
        self.mode = mode
        self.clock = clock
        self.sink = support.TraceSink(path)
        self.records = self.sink.records
        self.active = {}
        self.model_attempts = 0

    def _start(self, kind, run_id, parent_run_id, name):
        with self.sink.lock:
            key = str(run_id)
            state = {"started": self.clock(),
                     "stage": support.safe_stage(name),
                     "parent_run_id": str(parent_run_id) if parent_run_id else None, "chunk_count": 0}
            self.active[key] = state
            if kind == "model":
                self.model_attempts += 1
            self.sink.write({"event": f"{kind}_start", "stage": state["stage"], "run_id": key,
                             "parent_run_id": state["parent_run_id"], "mode": self.mode,
                             "elapsed_ms": 0.0, "chunk_count": 0, "usage": None, "error_type": None})

    def _finish(self, kind, run_id, error=None, usage=None):
        with self.sink.lock:
            key = str(run_id)
            state = self.active.pop(key, None)
            if state is None:
                return
            elapsed_ms = (self.clock() - state["started"]) * 1000
            error_type = type(error).__name__ if error is not None else None
            self.sink.write({"event": f"{kind}_{'error' if error is not None else 'end'}",
                             "stage": state["stage"], "run_id": key,
                             "parent_run_id": state["parent_run_id"], "mode": self.mode,
                             "elapsed_ms": max(0.0, elapsed_ms), "chunk_count": state["chunk_count"],
                             "usage": usage, "error_type": error_type})

    def on_llm_new_token(self, token, *, run_id, parent_run_id=None, **kwargs):
        text = support.message_text(token)
        if not text:
            return
        with self.sink.lock:
            state = self.active.get(str(run_id))
            if state is None:
                return
            state["chunk_count"] += 1
            self.sink.write({"event": "model_chunk", "stage": state["stage"], "run_id": str(run_id),
                             "parent_run_id": state["parent_run_id"], "mode": self.mode,
                             "elapsed_ms": max(0.0, (self.clock() - state["started"]) * 1000),
                             "chunk_count": state["chunk_count"], "usage": None, "error_type": None})

    # 제공: LangChain 이벤트를 위 세 메서드에 연결합니다.
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self._start("chain", run_id, parent_run_id, kwargs.get("name", "chain"))

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self._finish("chain", run_id)

    def on_chain_error(self, error, *, run_id, **kwargs):
        self._finish("chain", run_id, error=error)

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        self._start("model", run_id, parent_run_id, "model")

    def on_llm_end(self, response, *, run_id, **kwargs):
        self._finish("model", run_id, usage=support.extract_usage(response))

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._finish("model", run_id, error=error)


# 선택 심화 1: 초안 검토
def review_draft(draft, documents, reviewer, rewriter):
    """선택 심화: 필수에서 만든 검증을 재사용해 검토, 한 번 수정, 재검토 흐름을 설계합니다."""
    current = validate_sources(draft, documents)
    decision = reviewer({"draft": current, "documents": documents})
    if decision == "revise":
        # 재작성은 한 번만 허용하고, 잘못된 형식ㆍ출처는 재검토 전에 거부합니다.
        current = validate_sources(rewriter({"draft": current, "documents": documents}), documents)
        decision = reviewer({"draft": current, "documents": documents})
    if decision == "keep":
        return {"reply": current, "route": "primary"}
    return {"reply": support.safe_answer("fallback"), "route": "fallback"}


if __name__ == "__main__":
    raise SystemExit(support.main(sys.modules[__name__]))
