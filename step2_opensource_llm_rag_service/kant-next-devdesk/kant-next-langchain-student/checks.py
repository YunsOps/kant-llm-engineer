"""현재 단계만 확인하는 공개 검사. 외부 API나 실제 모델은 호출하지 않습니다.

통과 여부는 실제 모델 답변의 근거 확인을 대신하지 않습니다.
검사에서 사용하는 문서와 모델은 과제 정답 코드와 별도의 고정 자료입니다.
"""
import copy
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import Generation, LLMResult
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableLambda, RunnableParallel, RunnableSequence
from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langchain_core.runnables.retry import RunnableRetry

import support


class CheckFailure(AssertionError):
    """검사기가 작성한 안내만 사용자에게 보여 주기 위한 오류입니다."""


def expect(condition, message):
    if not condition:
        raise CheckFailure(message)


def expect_raises(operation, classes=(Exception,)):
    try:
        operation()
    except NotImplementedError:
        raise
    except classes:
        return
    raise CheckFailure("거부해야 하는 입력이나 실패를 정상 결과로 처리했습니다.")


@contextmanager
def patched(module, **changes):
    original = {name: getattr(module, name) for name in changes}
    for name, value in changes.items():
        setattr(module, name, value)
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(module, name, value)


def source_row(doc_id="check-alpha", **changes):
    row = {"doc_id": doc_id, "title": f"검사 문서 {doc_id}",
           "body": f"{doc_id} 전용 근거. Python 3.12 설치는 담당자 승인 뒤 진행합니다.",
           "source_url": f"https://example.invalid/{doc_id}",
           "collected_at": "2026-09-21T00:00:00+00:00", "category": "installation"}
    row.update(changes)
    return row


def fixture_document(doc_id="check-alpha", keywords=None):
    row = source_row(doc_id)
    return Document(page_content=row["body"], metadata={
        **{key: value for key, value in row.items() if key != "body"},
        "keywords": keywords if keywords is not None else ["python", "설치"],
    })


def good_reply(**changes):
    data = {"answer": "문서에 따라 담당자 승인 뒤 설치를 진행해 주세요.",
            "source_ids": ["check-alpha"], "needs_human": False, "category": "installation"}
    data.update(changes)
    return data


def prepared(**changes):
    doc = fixture_document()
    data = {"question": "Python 설치 방법을 알려주세요", "session_id": "check-session",
            "document_ids": ["check-alpha"], "history": [], "documents": [doc],
            "context": f"[doc_id: {doc.metadata['doc_id']}]\n제목: {doc.metadata['title']}\n출처: {doc.metadata['source_url']}\n본문: {doc.page_content}"}
    data.update(changes)
    return data


def primary_outcome(**changes):
    return {"reply": support.Answer.model_validate(good_reply(**changes)), "route": "primary"}


def assert_outcome(value, route="primary"):
    expect(isinstance(value, dict) and value.get("route") == route, "Outcome의 route와 반환 형식을 확인하세요.")
    expect(isinstance(value.get("reply"), support.Answer), "reply는 검증된 Answer 객체여야 합니다.")
    expect(set(value["reply"].model_dump()) == {"answer", "source_ids", "needs_human", "category"},
           "답변은 약속한 네 필드를 유지해야 합니다.")
    if route != "primary":
        expect(value["reply"].source_ids == [] and value["reply"].needs_human is True,
               "안전 안내는 출처를 비우고 담당자 확인을 표시하세요.")


def runnable_nodes(root):
    """Runnable이 실제로 조합되어 있는지 확인하며 제출 코드의 문자열은 검사하지 않습니다."""
    found, pending, seen = [], [root], set()
    while pending:
        item = pending.pop()
        if not isinstance(item, Runnable) or id(item) in seen:
            continue
        seen.add(id(item))
        found.append(item)
        for name in ("steps", "steps__", "bound", "runnable", "mapper", "fallbacks", "branches", "default"):
            value = getattr(item, name, None)
            if isinstance(value, dict):
                pending.extend(value.values())
            elif isinstance(value, (list, tuple)):
                for child in value:
                    pending.extend(child if isinstance(child, tuple) else [child])
            else:
                pending.append(value)
    return found


class EventRecorder(BaseCallbackHandler):
    def __init__(self):
        self.starts = []

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self.starts.append((run_id, parent_run_id, kwargs.get("name")))


def search_documents(module):
    rows = [source_row(), source_row("check-beta", category="release")]
    keywords = {"check-alpha": ["Python", "설치"], "check-beta": ["uv", "release"]}
    old_rows, old_keywords = copy.deepcopy(rows), copy.deepcopy(keywords)
    result = module.to_documents(rows, keywords)
    expect(len(result) == 2 and all(isinstance(item, Document) for item in result),
           "각 원천 문서를 LangChain Document로 변환하세요.")
    for row, doc in zip(rows, result):
        expect(doc.page_content == row["body"], "body를 Document.page_content에 넣으세요.")
        expect(all(doc.metadata.get(key) == value for key, value in row.items() if key != "body"),
               "ID, 제목, 출처, 수집 시각과 범주를 metadata에 보존하세요.")
        expect(doc.metadata.get("keywords") == keywords[row["doc_id"]], "제공한 문서별 keywords를 연결하세요.")
    expect(rows == old_rows and keywords == old_keywords, "변환하면서 원본 자료를 바꾸지 마세요.")
    result[0].metadata["keywords"].append("검사용 변경")
    expect(keywords == old_keywords, "keywords 목록도 원본과 분리해 복사하세요.")


def search_search(module, kind):
    docs = [fixture_document("check-alpha", ["python", "Python", "설치"]),
            fixture_document("check-beta", ["python", "승인"]),
            fixture_document("check-gamma", ["python", "설치", "승인"]),
            fixture_document("check-zero", ["계정"])]
    original = copy.deepcopy(docs)
    if kind == "filter":
        result = module.search_documents("PYTHON 설치 승인", docs, ["check-alpha", "check-beta"], top_k=3)
        wanted = ["check-alpha", "check-beta"]
    elif kind == "score":
        result = module.search_documents("PYTHON 설치 승인", docs, [doc.metadata["doc_id"] for doc in docs], top_k=3)
        wanted = ["check-gamma", "check-alpha", "check-beta"]
    elif kind == "limit":
        result = module.search_documents("PYTHON 설치 승인", docs, [doc.metadata["doc_id"] for doc in docs], top_k=1)
        wanted = ["check-gamma"]
    else:
        result = module.search_documents("검색되지 않는 질문", docs, ["check-alpha"], top_k=3)
        wanted = []
    expect([doc.metadata["doc_id"] for doc in result] == wanted,
           "후보 선필터, 중복 없는 키워드 점수, 대소문자, 동점 순서와 0점 제외를 확인하세요.")
    expect(docs == original, "검색 중 문서 목록이나 metadata를 수정하지 마세요.")


def search_context(module):
    docs = [fixture_document(), fixture_document("check-beta")]
    value = module.format_context(docs)
    expect(isinstance(value, str), "context는 문자열이어야 합니다.")
    for doc in docs:
        expect(all(piece in value for piece in [doc.metadata["doc_id"], doc.metadata["title"],
                   doc.metadata["source_url"], doc.page_content]), "context에서 ID, 제목, 출처와 본문을 구분해 보존하세요.")
    expect(isinstance(module.format_context([]), str) and bool(module.format_context([]).strip()),
           "검색 결과가 없을 때의 안내 문자열이 필요합니다.")


def search_parallel(module):
    docs = [fixture_document(), fixture_document("check-beta", ["계정"])]
    # Search uses its own documents without invoking the remaining features.
    chain = module.build_context_chain(docs)
    nodes = runnable_nodes(chain)
    expect(any(isinstance(item, RunnableParallel) for item in nodes),
           "원입력과 검색 경로를 실제 RunnableParallel로 조합하세요.")
    recorder = EventRecorder()
    history = [HumanMessage(content="Python 설치 질문입니다"), AIMessage(content="이전 안내입니다")]
    data = {"question": "그 버전은 무엇인가요", "session_id": "A", "document_ids": ["check-alpha"], "history": history}
    original = copy.deepcopy(data)
    result = chain.invoke(data, config={"callbacks": [recorder]})
    expect(isinstance(result, dict), "준비 체인은 Prepared dict를 반환해야 합니다.")
    for key in ("question", "session_id", "document_ids", "history"):
        expect(result.get(key) == data[key], f"준비 체인에서 {key}를 보존하세요.")
    expect([doc.metadata["doc_id"] for doc in result["documents"]] == ["check-alpha"],
           "후속 질문에서 search_query 규칙을 실제 검색에 연결하세요.")
    expect("check-alpha" in result["context"] and "check-beta" not in result["context"],
           "검색된 문서만 context에 넣으세요.")
    expect(data == original, "체인 실행 중 원입력이나 history를 수정하지 마세요.")
    parents = [parent for _, parent, _ in recorder.starts if parent is not None]
    expect(any(parents.count(parent) >= 2 for parent in parents), "Runnable 자식의 실제 실행 이벤트가 같은 부모 아래에 있어야 합니다.")


def chain_prompt_parser(module):
    prompt, parser = module.build_prompt_and_parser()
    expect(any(isinstance(item, ChatPromptTemplate) for item in runnable_nodes(prompt)), "ChatPromptTemplate을 반환하세요.")
    expect(any(isinstance(item, PydanticOutputParser) for item in runnable_nodes(parser)), "Answer에 대한 PydanticOutputParser를 반환하세요.")
    value = prepared(history=[HumanMessage(content="이전질문표식"), AIMessage(content="이전답변표식")])
    messages = prompt.invoke(value).to_messages()
    humans = [message.content for message in messages if isinstance(message, HumanMessage)]
    expect(humans == ["이전질문표식", value["question"]], "이전 대화와 현재 질문을 구분하고 현재 질문은 마지막 human에 한 번만 넣으세요.")
    combined = "\n".join(str(message.content) for message in messages)
    expect("이전답변표식" in combined and value["context"] in combined, "history와 현재 검색 근거가 prompt에 모두 필요합니다.")
    expect(all(field in combined for field in ("answer", "source_ids", "needs_human", "category")),
           "출력 형식 안내를 prompt에 포함하세요.")
    expect(isinstance(parser.invoke(json.dumps(good_reply(), ensure_ascii=False)), support.Answer),
           "parser는 제공된 Answer 자료형으로 결과를 검증해야 합니다.")


def chain_chain(module):
    model = support.FixtureChatModel(events=[good_reply(), good_reply(answer="두 번째 질문의 안내입니다.")])
    # Branch functions may contain a nested chain; the narrow primary must still be LCEL.
    primary = module.build_primary_chain(model)
    primary_nodes = runnable_nodes(primary)
    expect(any(isinstance(node, RunnableSequence) for node in primary_nodes), "prompt, model, parser를 LCEL 순차 체인으로 연결하세요.")
    expect(any(isinstance(node, ChatPromptTemplate) for node in primary_nodes)
           and any(isinstance(node, PydanticOutputParser) for node in primary_nodes)
           and any(node is model for node in primary_nodes), "순차 체인에 실제 prompt, 주입 모델, parser가 참여해야 합니다.")
    observed = {"prompt": 0, "parser": 0}
    original_builder = module.build_prompt_and_parser
    def observe(name):
        def start(_):
            observed[name] += 1
        return start
    def tracked_builder():
        prompt, parser = original_builder()
        return prompt.with_listeners(on_start=observe("prompt")), parser.with_listeners(on_start=observe("parser"))
    with patched(module, build_prompt_and_parser=tracked_builder):
        chain = module.build_answer_chain(model)
        expect(isinstance(chain, Runnable), "재사용 가능한 Runnable을 반환하세요.")
        for question in ("Python 설치 방법을 알려주세요", "Python 승인 절차를 알려주세요"):
            result = chain.invoke(prepared(question=question))
            assert_outcome(result)
    expect(model.calls == 2 and len(model.seen_messages) == 2, "한 체인을 서로 다른 두 질문에 재사용하고 모델을 한 번씩 호출하세요.")
    expect(observed == {"prompt": 2, "parser": 2}, "각 답변 실행에서 실제 prompt와 parser Runnable을 한 번씩 거쳐야 합니다.")
    expect(model.seen_messages[0][-1].content != model.seen_messages[1][-1].content,
           "첫 질문을 체인 안에 고정하지 마세요.")


def chain_bad_output(module, event):
    model = support.FixtureChatModel(events=[event])
    expect_raises(lambda: module.build_answer_chain(model).invoke(prepared()))
    expect(model.calls == 1, "기본 체인에서는 잘못된 출력을 거부하고 재시도하지 않습니다.")


def chain_sources(module):
    docs = [fixture_document()]
    answer = support.Answer.model_validate(good_reply())
    expect(module.validate_sources(answer, docs) == answer, "올바른 출처는 검증 후 같은 답변으로 돌려주세요.")
    other = support.Answer.model_validate(good_reply(source_ids=["check-beta"]))
    expect_raises(lambda: module.validate_sources(other, docs), (support.SourceValidationError,))
    safe = support.Answer.model_validate(good_reply(source_ids=[], needs_human=True))
    expect(module.validate_sources(safe, docs) == safe, "담당자 확인이 필요한 출처 없는 안내는 허용합니다.")


def chain_empty(module):
    model = support.FixtureChatModel(events=[RuntimeError("호출되면 안 되는 모델")])
    value = prepared(documents=[], context="관련 문서가 없습니다.")
    result = module.build_answer_chain(model).invoke(value)
    assert_outcome(result, "no_documents")
    expect(model.calls == 0, "검색 결과가 없을 때 모델을 호출하지 마세요.")


def independent_prompt_parser():
    """대화 이력과 스트리밍을 다른 기능과 분리해 확인하는 검사 입력입니다."""
    parser = PydanticOutputParser(pydantic_object=support.Answer)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "이번 검사 근거: {context}\n{format_instructions}"),
        MessagesPlaceholder("history"), ("human", "{question}"),
    ]).partial(format_instructions=parser.get_format_instructions())
    return prompt, parser


def independent_sources(answer, documents):
    allowed = {doc.metadata["doc_id"] for doc in documents}
    if not set(answer.source_ids) <= allowed or len(answer.source_ids) != len(set(answer.source_ids)):
        raise support.SourceValidationError("검사 문서 밖 출처")
    if not answer.source_ids and not answer.needs_human:
        raise support.SourceValidationError("근거 없는 해결 응답")
    return answer


def history_history(module):
    store = {}
    first = module.get_history(store, "A")
    again = module.get_history(store, "A")
    other = module.get_history(store, "B")
    expect(isinstance(first, InMemoryChatMessageHistory), "세션마다 InMemoryChatMessageHistory를 만드세요.")
    expect(first is again and first is not other, "같은 세션의 객체를 재사용하고 다른 세션과 분리하세요.")
    expect(first.messages == [] and other.messages == [], "새 이력에 현재 질문을 미리 저장하지 마세요.")
    module.commit_history(store, "A", "현재질문표식", primary_outcome())
    expect(len(first.messages) == 2 and isinstance(first.messages[0], HumanMessage)
           and isinstance(first.messages[1], AIMessage), "검증된 primary 뒤 Human, AI 한 쌍을 저장하세요.")
    expect(first.messages[0].content == "현재질문표식" and first.messages[1].content == good_reply()["answer"],
           "현재 질문과 최종 answer 본문을 저장하세요.")
    expect(other.messages == [], "다른 세션에 이력을 저장하지 마세요.")


def history_no_commit(module, route):
    store = {}
    history = module.get_history(store, "A")
    outcome = {"reply": support.Answer.model_validate(good_reply(source_ids=[], needs_human=True)), "route": route}
    module.commit_history(store, "A", "저장되면 안 되는 질문", outcome)
    expect(history.messages == [], "문서 없음과 fallback은 대화 이력에 저장하지 마세요.")


def history_turns(module):
    store, commits = {}, []
    model = support.FixtureChatModel(events=[good_reply(), good_reply(), good_reply()])
    original_commit = module.commit_history
    def commit(*args):
        commits.append(args[1])
        return original_commit(*args)
    def context(_):
        return RunnableLambda(lambda value: prepared(**{key: value[key]
            for key in ("question", "session_id", "document_ids", "history")}))
    def answer(selected_model, reliable=False):
        prompt, parser = independent_prompt_parser()
        return prompt | selected_model | parser | RunnableLambda(lambda reply: {"reply": reply, "route": "primary"})
    with patched(module, build_context_chain=context, build_answer_chain=answer, commit_history=commit):
        for session, question in (("A", "A전용표식 Python 설치 방법"), ("A", "그 버전은 무엇인가요"), ("B", "B전용표식 Python 설치 방법")):
            result = support.run_turn(module, {"question": question, "document_ids": ["check-alpha"], "session_id": session},
                                      [fixture_document()], model, store)
            assert_outcome(result)
    expect(commits == ["A", "A", "B"], "각 정상 턴 뒤 commit_history를 정확히 한 번 호출해야 합니다.")
    expect(len(store["A"].messages) == 4 and len(store["B"].messages) == 2, "A 두 턴과 B 한 턴의 이력 개수를 확인하세요.")
    expect(model.calls == 3, "세 턴은 모델을 한 번씩 호출해야 합니다.")
    second = model.seen_messages[1]
    third = model.seen_messages[2]
    second_humans = [message.content for message in second if isinstance(message, HumanMessage)]
    expect(second_humans == ["A전용표식 Python 설치 방법", "그 버전은 무엇인가요"],
           "이전 대화를 prompt에 넣되 현재 질문을 중복 저장하거나 삽입하지 마세요.")
    expect("A전용표식" not in str(third), "다른 세션의 대화 표식이 prompt에 섞였습니다.")
    expect(len([message for message in model.seen_messages[0] if isinstance(message, HumanMessage)]) == 1,
           "첫 호출 때 넘긴 history snapshot이 뒤의 저장에 따라 변경되면 안 됩니다.")


def recovery_case(module, failures, expected_route, expected_calls):
    calls = []
    def primary(value):
        calls.append(copy.deepcopy(value))
        event = failures[min(len(calls) - 1, len(failures) - 1)]
        if isinstance(event, Exception):
            raise event
        return primary_outcome()
    chain = module.build_resilient_chain(RunnableLambda(primary))
    nodes = runnable_nodes(chain)
    expect(any(isinstance(node, RunnableRetry) for node in nodes), "with_retry를 실제 Runnable에 적용하세요.")
    expect(any(isinstance(node, RunnableWithFallbacks) for node in nodes), "with_fallbacks를 실제 Runnable에 적용하세요.")
    value = prepared()
    original = copy.deepcopy(value)
    if expected_route == "raise":
        expect_raises(lambda: chain.invoke(value), (type(failures[-1]),))
    else:
        result = chain.invoke(value)
        assert_outcome(result, expected_route)
    expect(len(calls) == expected_calls, "오류 종류별 시도 횟수와 최초 포함 2회 상한을 확인하세요.")
    expect(all(call == original for call in calls) and value == original,
           "복구에서도 같은 질문, history와 근거를 사용하고 입력을 수정하지 마세요.")


def recovery_provider_error(module, event):
    model = support.FixtureChatModel(events=[event])
    chain = module.build_resilient_chain(RunnableLambda(lambda _: model.invoke([HumanMessage(content="검사 질문")])) )
    expect_raises(lambda: chain.invoke(prepared()))
    expect(model.calls == 1, "인증 오류와 공급자 429는 재시도하거나 fallback으로 숨기지 마세요.")


def stream_normal(module):
    model = support.FixtureChatModel(events=[good_reply()], chunk_size=11)
    value = prepared()
    original = copy.deepcopy(value)
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        iterator = iter(module.stream_answer(value, model))
        try:
            first = next(iterator)
            expect(first.get("type") == "delta" and bool(first.get("text")), "실제 모델의 첫 텍스트 청크를 즉시 delta로 내보내세요.")
            expect(any(event["event"] == "start" for event in model.stream_trace), "model.stream()의 시작이 관찰되어야 합니다.")
            expect(not any(event["event"] == "end" for event in model.stream_trace),
                   "모델이 끝나기 전에 첫 delta가 나와야 합니다. invoke 결과를 나누지 마세요.")
            events = [first, *list(iterator)]
        finally:
            if hasattr(iterator, "close"):
                iterator.close()
    expect(model.calls == 1, "정상 스트림은 모델을 한 번 호출해야 합니다.")
    expect(events[-1].get("type") == "final" and events[-1].get("route") == "primary", "끝까지 검증한 뒤 final primary를 내보내세요.")
    expect(sum(event.get("type") == "final" for event in events) == 1
           and not any(event.get("type") == "reset" for event in events), "정상 스트림의 final은 한 번이며 reset이 없어야 합니다.")
    assembled = "".join(event["text"] for event in events if event.get("type") == "delta")
    expect(support.Answer.model_validate_json(assembled).model_dump() == events[-1]["reply"],
           "전달한 청크를 모두 합친 결과와 검증된 final이 같아야 합니다.")
    expect(value == original, "스트림 중 Prepared나 history를 변경하지 마세요.")


def stream_recovery(module, event, after_text):
    script = [event, good_reply()]
    model = support.FixtureChatModel(events=script, chunk_size=12)
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        events = list(module.stream_answer(prepared(), model))
    if after_text:
        expect(model.calls == 1, "첫 텍스트를 전달한 뒤에는 다시 생성해 이어 붙이지 마세요.")
        expect(any(event.get("type") == "delta" for event in events), "중간 실패 검사에서 앞선 delta가 필요합니다.")
        resets = [index for index, item in enumerate(events) if item.get("type") == "reset"]
        expect(len(resets) == 1 and resets[0] < len(events) - 1, "임시 청크를 reset으로 한 번 폐기한 뒤 안전 안내를 확정하세요.")
        expect(events[-1].get("type") == "final" and events[-1].get("route") == "fallback", "중간 실패는 final fallback으로 구분하세요.")
        reply = support.Answer.model_validate(events[-1]["reply"])
        expect(reply.needs_human and reply.source_ids == [], "fallback은 담당자 확인과 빈 출처를 사용하세요.")
    else:
        expect(model.calls == 2, "첫 텍스트 전의 일시 실패에만 추가 시도 한 번을 허용하세요.")
        expect(events[-1].get("route") == "primary", "일시 실패 후 정상 결과를 검증해 primary로 확정하세요.")


def stream_repeated(module):
    model = support.FixtureChatModel(events=["temporary", "temporary", good_reply()])
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        events = list(module.stream_answer(prepared(), model))
    expect(model.calls == 2, "청크 전 반복 실패도 최초 포함 2회를 넘을 수 없습니다.")
    expect(events[-1].get("route") == "fallback", "두 번의 허용 오류 뒤에는 모델 없는 fallback으로 끝내세요.")


def stream_fatal(module, event, after_text):
    model = support.FixtureChatModel(events=[event, good_reply()], chunk_size=12)
    events, raised = [], False
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        iterator = iter(module.stream_answer(prepared(), model))
        try:
            for item in iterator:
                events.append(item)
        except NotImplementedError:
            raise
        except Exception:
            raised = True
        finally:
            if hasattr(iterator, "close"):
                iterator.close()
    expect(raised and model.calls == 1, "재시도 대상이 아닌 오류는 한 번 시도한 뒤 호출자에게 전달하세요.")
    expect(not any(item.get("type") == "final" for item in events), "재시도 대상이 아닌 오류에서는 final 대신 오류를 전달하세요.")
    if after_text:
        expect(any(item.get("type") == "delta" for item in events) and events[-1].get("type") == "reset",
               "이미 출력한 청크를 reset으로 폐기한 뒤 오류를 전달하세요.")


def stream_close(module):
    model = support.FixtureChatModel(events=[good_reply()], chunk_size=5)
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        iterator = iter(module.stream_answer(prepared(), model))
        expect(next(iterator).get("type") == "delta", "취소 전에 첫 delta를 받을 수 있어야 합니다.")
        iterator.close()
    expect(any(event["event"] == "closed" for event in model.stream_trace),
           "소비자가 중단하면 모델 iterator도 닫아야 합니다.")
    expect(not any(event["event"] == "end" for event in model.stream_trace), "취소를 정상 생성 완료로 표시하지 마세요.")


def stream_empty(module):
    model = support.FixtureChatModel(events=[RuntimeError("모델 호출 금지")])
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        events = list(module.stream_answer(prepared(documents=[], context="검색 결과 없음"), model))
    expect(model.calls == 0 and len(events) == 1 and events[0].get("type") == "final"
           and events[0].get("route") == "no_documents", "문서가 없는 스트림은 모델 없이 안내 final 하나로 끝내세요.")


def stream_trace(module):
    model = support.FixtureChatModel(events=[good_reply()], chunk_size=13)
    handler = module.TraceHandler(mode="fixture")
    with patched(module, build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources):
        events = list(module.stream_answer(prepared(question="질문비공개표식", history=[HumanMessage(content="세션비공개표식")]),
                                          model, config={"callbacks": [handler], "run_name": "stream-check"}))
    expect(events[-1].get("route") == "primary", "관측을 연결해도 정상 결과가 유지되어야 합니다.")
    records = handler.records
    expect(records and handler.model_attempts == 1, "실제 Callback을 연결하고 모델 시작 횟수를 기록하세요.")
    kinds = {record.get("event") for record in records}
    expect({"chain_start", "chain_end", "model_start", "model_end", "model_chunk"} <= kinds,
           "체인, 모델과 청크의 실제 실행 이벤트가 필요합니다.")
    starts = {record["run_id"] for record in records if record["event"].endswith("_start")}
    expect(any(record.get("parent_run_id") in starts for record in records if record.get("parent_run_id")),
           "자식 run의 parent_run_id가 실제 부모 run과 연결되어야 합니다.")
    for record in records:
        expect({"event", "stage", "run_id", "parent_run_id", "mode", "elapsed_ms", "chunk_count", "usage", "error_type"} <= set(record),
               "trace의 약속한 필드를 빠짐없이 기록하세요.")
        expect(record["mode"] == "fixture" and record["elapsed_ms"] >= 0, "fixture 모드와 음수가 아닌 경과 시간을 기록하세요.")
    text = json.dumps(records, ensure_ascii=False, default=str)
    expect(all(marker not in text for marker in ("질문비공개표식", "세션비공개표식", fixture_document().page_content, good_reply()["answer"])),
           "trace에 질문, 이력, 문서와 답변 원문을 기록하지 마세요.")
    end = next(record for record in reversed(records) if record["event"] == "model_end")
    delta_count = sum(item.get("type") == "delta" for item in events)
    expect(end["chunk_count"] == delta_count, "빈 usage 청크를 제외한 실제 텍스트 청크 수를 기록하세요.")


def stream_trace_clock(module):
    moments = iter([10.0, 10.125])
    handler = module.TraceHandler(mode="fixture", clock=lambda: next(moments))
    run_id, parent_id = uuid4(), uuid4()
    handler.on_chain_start({}, {"question": "민감질문표식"}, run_id=run_id, parent_run_id=parent_id, name="check-chain")
    handler.on_chain_error(TypeError("민감예외표식"), run_id=run_id, parent_run_id=parent_id)
    expect(len(handler.records) >= 2, "시작과 오류 이벤트를 모두 기록하세요.")
    final = handler.records[-1]
    expect(final["event"] == "chain_error" and abs(final["elapsed_ms"] - 125) < 0.001,
           "같은 run의 시작과 종료 시각 차이를 밀리초로 계산하세요.")
    expect(str(final["parent_run_id"]) == str(parent_id) and final["usage"] is None,
           "부모 관계를 보존하고 제공되지 않은 usage를 null로 두세요.")
    expect(final["error_type"] and "민감예외표식" not in json.dumps(handler.records, ensure_ascii=False, default=str),
           "예외의 안전한 종류만 기록하고 전문을 저장하지 마세요.")


def stream_missing_usage(module):
    handler = module.TraceHandler(mode="fixture")
    run_id = uuid4()
    handler.on_chat_model_start({}, [[HumanMessage(content="저장하면 안 되는 입력")]], run_id=run_id)
    handler.on_llm_new_token("", run_id=run_id)
    handler.on_llm_new_token([], run_id=run_id)
    handler.on_llm_new_token([{"type": "text", "text": ""}], run_id=run_id)
    handler.on_llm_end(LLMResult(generations=[[Generation(text="저장하면 안 되는 출력")]]), run_id=run_id)
    final = handler.records[-1]
    expect(final["event"] == "model_end" and final["chunk_count"] == 0 and final["usage"] is None,
           "빈 청크를 세지 말고 usage가 없으면 0토큰 추정 대신 null을 기록하세요.")
    block_run = uuid4()
    handler.on_chat_model_start({}, [[]], run_id=block_run)
    handler.on_llm_new_token([{"type": "text", "text": "비공개블록표식"}], run_id=block_run)
    handler.on_llm_new_token([{"type": "output_text", "text": "다음블록표식"}], run_id=block_run)
    handler.on_llm_new_token([{"type": "reasoning", "text": "기록하지 않는 블록"}], run_id=block_run)
    handler.on_llm_end(LLMResult(generations=[[Generation(text="")]]), run_id=block_run)
    expect(handler.records[-1]["chunk_count"] == 2,
           "Responses의 텍스트 블록 목록도 message_text로 읽고 비어 있지 않은 텍스트 청크만 세세요.")
    expect("비공개블록표식" not in json.dumps(handler.records, ensure_ascii=False, default=str),
           "블록 형식 청크의 본문도 trace에 저장하지 마세요.")


def stream_stream_history(module, kind):
    store, commits = {}, []
    model = support.FixtureChatModel(events=["midstream" if kind == "fallback" else good_reply()], chunk_size=7)
    def context(_):
        return RunnableLambda(lambda value: prepared(**{key: value[key]
            for key in ("question", "session_id", "document_ids", "history")}))
    def history(target, session_id):
        return target.setdefault(session_id, InMemoryChatMessageHistory())
    def commit(target, session_id, question, outcome):
        commits.append(outcome["route"])
        history(target, session_id).add_messages([HumanMessage(content=question), AIMessage(content=outcome["reply"].answer)])
    changes = dict(build_context_chain=context, get_history=history, commit_history=commit,
                   build_prompt_and_parser=independent_prompt_parser, validate_sources=independent_sources)
    with patched(module, **changes):
        iterator = iter(support.stream_turn(module,
            {"question": "Python 설치 질문", "document_ids": ["check-alpha"], "session_id": "A"},
            [fixture_document()], model, store))
        try:
            first = next(iterator)
            expect(first.get("type") == "delta" and not commits, "미검증 delta 단계에서 이력을 저장하지 마세요.")
            if kind != "cancel":
                list(iterator)
        finally:
            iterator.close()
    expected = ["primary"] if kind == "primary" else []
    expect(commits == expected, "완료된 primary 스트림에 한해서 저장을 한 번 호출하세요.")
    expect(len(store["A"].messages) == (2 if kind == "primary" else 0),
           "중단되거나 fallback으로 끝난 스트림은 이력에 남기지 마세요.")
    if kind == "cancel":
        expect(any(event["event"] == "closed" for event in model.stream_trace), "상위 스트림 중단도 모델 iterator를 닫아야 합니다.")


def challenge_case(module, decisions):
    reviews, rewrites = [], []
    draft = support.Answer.model_validate(good_reply())
    def reviewer(value):
        reviews.append(value)
        return decisions[min(len(reviews) - 1, len(decisions) - 1)]
    def rewriter(value):
        rewrites.append(value)
        return support.Answer.model_validate(good_reply(answer="문서 근거로 한 번 수정한 답변입니다."))
    result = module.review_draft(draft, [fixture_document()], reviewer, rewriter)
    wanted = "primary" if decisions[-1] == "keep" else "fallback"
    assert_outcome(result, wanted)
    expect(len(rewrites) == (1 if decisions[0] == "revise" else 0), "수정 경로에서만 최대 한 번 다시 작성하세요.")
    expect(len(reviews) == (2 if decisions[0] == "revise" else 1), "한 번 수정한 결과를 다시 검토하고 반복하지 마세요.")


def challenge_invalid_revision(module):
    reviews = []
    def reviewer(value):
        reviews.append(value)
        return "revise" if len(reviews) == 1 else "keep"
    def rewriter(value):
        return support.Answer.model_validate(good_reply(source_ids=["not-retrieved"]))
    expect_raises(lambda: module.review_draft(support.Answer.model_validate(good_reply()),
        [fixture_document()], reviewer, rewriter), (support.SourceValidationError,))
    expect(len(reviews) == 1, "잘못된 출처의 수정 답변을 정상 초안처럼 다시 검토하지 마세요.")


def cases_for(module):
    groups = {name: [] for name in ("search", "chain", "history", "recovery", "stream", "challenge")}
    def add(stage, name, operation, *args):
        groups[stage].append((name, lambda: operation(module, *args)))
    add("search", "Document와 원본 보존", search_documents)
    for kind, name in (("filter", "허용 후보 선필터"), ("score", "키워드 점수와 동점"), ("limit", "top_k 상한"), ("empty", "0점 제외")):
        add("search", name, search_search, kind)
    add("search", "근거 context", search_context)
    add("search", "실제 병렬 준비와 후속 검색", search_parallel)
    add("chain", "prompt와 parser 연결", chain_prompt_parser)
    add("chain", "실제 LCEL 순차 실행과 재사용", chain_chain)
    add("chain", "검색된 출처 검증", chain_sources)
    add("chain", "문서 없음 분기", chain_empty)
    for name, value in (("잘못된 JSON", "invalid_json"), ("없는 필드", {"answer": "안내입니다"}),
            ("추가 필드", good_reply(extra="금지")), ("boolean 문자열", good_reply(needs_human="false")),
            ("빈 답변", good_reply(answer="  ")), ("답변 release 범주", good_reply(category="release")),
            ("중복 출처", good_reply(source_ids=["check-alpha", "check-alpha"])),
            ("미검색 출처", good_reply(source_ids=["check-beta"])),
            ("출처 없는 해결 응답", good_reply(source_ids=[], needs_human=False))):
        add("chain", name, chain_bad_output, value)
    add("history", "세션별 history 객체와 저장 순서", history_history)
    add("history", "문서 없음 이력 제외", history_no_commit, "no_documents")
    add("history", "fallback 이력 제외", history_no_commit, "fallback")
    add("history", "A 두 턴과 B 한 턴의 분리", history_turns)
    for name, events, route, count in (
            ("정상 1회", [None], "primary", 1),
            ("일시 장애 후 성공", [support.TemporaryModelError("fixture"), None], "primary", 2),
            ("파서 오류 후 성공", [OutputParserException("fixture"), None], "primary", 2),
            ("출처 오류 후 성공", [support.SourceValidationError("fixture"), None], "primary", 2),
            ("두 번 실패 뒤 fallback", [support.TemporaryModelError("fixture")], "fallback", 2),
            ("두 번 파서 오류", [OutputParserException("fixture")], "fallback", 2),
            ("TypeError 전달", [TypeError("fixture")], "raise", 1),
            ("설정 오류 전달", [ValueError("fixture")], "raise", 1),
            ("인증 오류 전달", [PermissionError("fixture")], "raise", 1),
            ("일시 실패 뒤 코드 오류", [support.TemporaryModelError("fixture"), TypeError("fixture")], "raise", 2)):
        add("recovery", name, recovery_case, events, route, count)
    add("recovery", "실제 fixture 인증 분류", recovery_provider_error, "auth")
    add("recovery", "실제 fixture 공급자 429 분류", recovery_provider_error, "rate_limit")
    add("recovery", "실제 fixture 설정 오류 분류", recovery_provider_error, "config")
    add("stream", "종료 전 delta와 검증된 final", stream_normal)
    add("stream", "청크 전 일시 실패 복구", stream_recovery, "temporary", False)
    add("stream", "중간 실패 뒤 reset", stream_recovery, "midstream", True)
    add("stream", "완료 문자열 JSON 실패 뒤 reset", stream_recovery, "invalid_json", True)
    add("stream", "완료 문자열 출처 실패 뒤 reset", stream_recovery, good_reply(source_ids=["check-beta"]), True)
    add("stream", "완료 문자열 중복 출처 뒤 reset", stream_recovery, good_reply(source_ids=["check-alpha", "check-alpha"]), True)
    add("stream", "완료 문자열 스키마 실패 뒤 reset", stream_recovery, good_reply(needs_human="false"), True)
    add("stream", "청크 전 실패 2회 상한", stream_repeated)
    add("stream", "인증 오류 전달", stream_fatal, "auth", False)
    add("stream", "429 오류 전달", stream_fatal, "rate_limit", False)
    add("stream", "중간 코드 오류와 reset", stream_fatal, "midstream_fatal", True)
    add("stream", "소비 중단과 iterator 정리", stream_close)
    add("stream", "문서 없음 스트림", stream_empty)
    add("stream", "실제 Callback과 원문 없는 trace", stream_trace)
    add("stream", "run별 경과 시간과 오류 기록", stream_trace_clock)
    add("stream", "usage 부재와 빈 청크", stream_missing_usage)
    for kind in ("primary", "fallback", "cancel"):
        add("stream", "스트림 이력 저장 " + kind, stream_stream_history, kind)
    for decisions in (["keep"], ["human"], ["revise", "keep"], ["revise", "revise"], ["revise", "human"]):
        add("challenge", "검토 경로 " + " → ".join(decisions), challenge_case, decisions)
    add("challenge", "수정 답변의 출처 검증", challenge_invalid_revision)
    return groups


def run_checks(module, stage):
    """선택한 기능만 검사합니다. all은 선택 심화를 포함하지 않습니다."""
    stage = support.normalize_stage(stage)
    groups = cases_for(module)
    stages = ["search", "chain", "history", "recovery", "stream"] if stage == "all" else [stage]
    if any(name not in groups for name in stages):
        raise ValueError("검사 대상은 search, chain, history, recovery, stream, all, challenge 중 하나입니다.")
    results = []
    for current in stages:
        for name, operation in groups[current]:
            try:
                operation()
            except NotImplementedError:
                passed, detail = False, "현재 단계의 TODO를 먼저 구현하세요."
            except CheckFailure as error:
                passed, detail = False, str(error)
            except Exception as error:
                passed, detail = False, f"{type(error).__name__}: 입력, 반환 형식과 현재 단계의 구현을 확인하세요."
            else:
                passed, detail = True, "통과"
            results.append({"name": f"{support.STAGE_LABELS[current]}: {name}", "passed": passed, "detail": detail})
    passed = sum(item["passed"] for item in results)
    return {"stage": stage, "passed": passed, "failed": len(results) - passed, "results": results}
