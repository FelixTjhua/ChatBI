"""
ChatBI RAG 效果测试 API
用于测试RAG检索效果，展示术语和SQL示例的检索结果
"""

from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil
from apps.terminology.crud.terminology import select_terminology_by_word_with_details
from apps.data_training.crud.data_training import select_training_by_question_with_details

router = APIRouter(tags=["system/rag-test"], prefix="/system/rag-test")


class RagTestRequest(BaseModel):
    question: str
    datasource_id: Optional[int] = None

    # 限制查询长度，防止超长输入导致 embedding 模型 OOM
    @field_validator('question')
    @classmethod
    def validate_question_length(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question 不能为空")
        if len(v) > 2000:
            raise ValueError("question 长度不能超过 2000 字符")
        return v.strip()


class TerminologyResult(BaseModel):
    word: str
    description: str
    similarity: float
    match_type: str  # 'keyword' or 'vector'


class SqlExampleResult(BaseModel):
    question: str
    sql: str
    similarity: float
    match_type: str  # 'keyword' or 'vector'


class RagTestResponse(BaseModel):
    terminologies: List[TerminologyResult]
    sql_examples: List[SqlExampleResult]
    rag_enabled: bool = True


@router.post("/test")
async def test_rag_retrieval(
    session: SessionDep,
    current_user: CurrentUser,
    request: RagTestRequest
) -> RagTestResponse:
    """
    测试RAG检索效果
    返回检索到的术语和SQL示例，包含相似度和重排序分数
    """
    oid = current_user.oid
    ds_id = request.datasource_id
    
    # 查询重写
    from apps.chat.thinking.query_rewriter import QueryRewriter
    rewrite_result = QueryRewriter.rewrite(request.question)
    retrieval_question = rewrite_result['rewritten']
    
    # 获取术语检索结果
    terminology_results = []
    try:
        terms = select_terminology_by_word_with_details(
            session, retrieval_question, oid, ds_id
        )
        
        # 多路检索：使用扩展查询补充
        for eq in rewrite_result.get('expanded_queries', []):
            try:
                extra = select_terminology_by_word_with_details(session, eq, oid, ds_id)
                existing = {t.get('word', '') for t in terms}
                for et in extra:
                    if et.get('word', '') not in existing:
                        terms.append(et)
                        existing.add(et.get('word', ''))
            except Exception as e:
                ChatBILogUtil.error(f"Expanded terminology query failed for '{eq}': {e}")
        
        # 智能重排序
        from apps.chat.thinking.rag_reranker import RAGReranker
        reranked_terms = RAGReranker.rerank_terminologies(terms, request.question, ds_id, top_k=10)
        
        for term in reranked_terms:
            terminology_results.append(TerminologyResult(
                word=term.get('word', ''),
                description=term.get('description', ''),
                similarity=term.get('similarity', 0.0),
                match_type=term.get('match_type', 'keyword')
            ))
    except Exception as e:
        ChatBILogUtil.error(f"Error getting terminology: {e}")
    
    # 获取SQL示例检索结果
    sql_example_results = []
    try:
        examples = select_training_by_question_with_details(
            session, retrieval_question, oid, ds_id, None
        )
        
        # 多路检索
        for eq in rewrite_result.get('expanded_queries', []):
            try:
                extra = select_training_by_question_with_details(session, eq, oid, ds_id, None)
                existing = {e.get('question', '') for e in examples}
                for ee in extra:
                    if ee.get('question', '') not in existing:
                        examples.append(ee)
                        existing.add(ee.get('question', ''))
            except Exception as e:
                ChatBILogUtil.error(f"Expanded SQL example query failed for '{eq}': {e}")
        
        # 智能重排序
        reranked_examples = RAGReranker.rerank_sql_examples(examples, request.question, ds_id, top_k=10)
        
        for example in reranked_examples:
            sql_example_results.append(SqlExampleResult(
                question=example.get('question', ''),
                sql=example.get('sql', ''),
                similarity=example.get('similarity', 0.0),
                match_type=example.get('match_type', 'keyword')
            ))
    except Exception as e:
        ChatBILogUtil.error(f"Error getting SQL examples: {e}")
    
    return RagTestResponse(
        terminologies=terminology_results,
        sql_examples=sql_example_results,
        rag_enabled=True
    )
