import asyncio
import io
import re

import orjson
import pandas as pd
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, select
from pydantic import BaseModel

from apps.chat.crud.chat import list_chats, get_chat_with_records, create_chat, rename_chat, \
    delete_chat, get_chat_chart_data, get_chat_predict_data, get_chat_with_records_with_data, get_chat_record_by_id, \
    delete_chat_record, format_json_data, format_json_list_data, get_chart_config
from apps.chat.models.chat_model import CreateChat, ChatRecord, RenameChat, ChatQuestion, AxisObj
from apps.chat.task.llm import LLMService
from common.core.deps import CurrentAssistant, SessionDep, CurrentUser, Trans
from common.utils.data_format import DataFormat
from common.utils.input_validator import validate_chat_input
from common.audit.audit_helper import log_chat_created, log_chat_deleted, log_query_executed
from common.utils.locale import I18n

_i18n = I18n("locales")

router = APIRouter(tags=["Data Q&A"], prefix="/chat")


class AnalysisPredictRequest(BaseModel):
    """分析和预测请求模型"""
    pass  # RAG 永远开启，不需要参数


@router.get("/list")
async def chats(session: SessionDep, current_user: CurrentUser):
    return list_chats(session, current_user)


@router.get("/{chart_id}")
async def get_chat(session: SessionDep, current_user: CurrentUser, chart_id: int, current_assistant: CurrentAssistant):
    def inner():
        return get_chat_with_records(chart_id=chart_id, session=session, current_user=current_user,
                                     current_assistant=current_assistant)

    return await asyncio.to_thread(inner)


@router.get("/{chart_id}/with_data")
async def get_chat_with_data(session: SessionDep, current_user: CurrentUser, chart_id: int,
                             current_assistant: CurrentAssistant):
    def inner():
        return get_chat_with_records_with_data(chart_id=chart_id, session=session, current_user=current_user,
                                               current_assistant=current_assistant)

    return await asyncio.to_thread(inner)


@router.get("/record/{chat_record_id}/data")
async def chat_record_data(session: SessionDep, current_user: CurrentUser, chat_record_id: int):
    def inner():
        # 验证记录归属当前用户，防止越权访问
        record = session.get(ChatRecord, chat_record_id)
        if not record or record.create_by != current_user.id:
            raise HTTPException(status_code=404, detail="Record not found")
        data = get_chat_chart_data(chat_record_id=chat_record_id, session=session)
        return format_json_data(data)

    return await asyncio.to_thread(inner)


@router.get("/record/{chat_record_id}/predict_data")
async def chat_predict_data(session: SessionDep, current_user: CurrentUser, chat_record_id: int):
    def inner():
        # 验证记录归属当前用户，防止越权访问
        record = session.get(ChatRecord, chat_record_id)
        if not record or record.create_by != current_user.id:
            raise HTTPException(status_code=404, detail="Record not found")
        data = get_chat_predict_data(chat_record_id=chat_record_id, session=session)
        # 确保data是列表类型，如果是字典或其他类型则包装成列表
        if not isinstance(data, list):
            if isinstance(data, dict):
                # 如果是空字典，返回空列表
                if not data:
                    data = []
                else:
                    # 如果是非空字典，包装成列表
                    data = [data]
            else:
                # 其他类型返回空列表
                data = []
        return format_json_list_data(data)

    return await asyncio.to_thread(inner)


def _chat_trans(user) -> callable:
    """获取基于用户语言的翻译函数"""
    lang = (user.language or 'zh-CN').lower().replace('_', '-')
    translations = _i18n.translations.get(lang, _i18n.translations.get('zh-cn', {}))
    def _t(key: str, **kwargs) -> str:
        keys = key.split('.')
        current = translations
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return key
        if isinstance(current, str) and kwargs:
            try:
                return current.format(**kwargs)
            except (KeyError, ValueError):
                return current
        return current if isinstance(current, str) else key
    return _t


@router.post("/rename")
async def rename(session: SessionDep, current_user: CurrentUser, chat: RenameChat):
    try:
        return rename_chat(session=session, rename_object=chat, current_user=current_user)
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.error(f"Rename chat error: {e}")
        t = _chat_trans(current_user)
        raise HTTPException(status_code=500, detail=t('i18n_chat.rename_failed'))


@router.delete("/{chart_id}")
async def delete(session: SessionDep, current_user: CurrentUser, chart_id: int):
    try:
        result = delete_chat(session=session, chart_id=chart_id, current_user=current_user)
        log_chat_deleted(session, current_user.id, current_user.name or '', chart_id,
                         oid=current_user.oid or 1)
        return result
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.error(f"Delete chat error: {e}")
        t = _chat_trans(current_user)
        raise HTTPException(status_code=500, detail=t('i18n_chat.delete_failed'))


@router.delete("/record/{record_id}")
async def delete_record(session: SessionDep, current_user: CurrentUser, record_id: int):
    """删除单个聊天记录"""
    try:
        return delete_chat_record(session=session, record_id=record_id, current_user=current_user)
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.error(f"Delete chat record error: {e}")
        t = _chat_trans(current_user)
        raise HTTPException(status_code=500, detail=t('i18n_chat.delete_record_failed'))


@router.post("/start")
async def start_chat(session: SessionDep, current_user: CurrentUser, create_chat_obj: CreateChat):
    try:
        chat_info = create_chat(session, current_user, create_chat_obj)
        log_chat_created(session, current_user.id, current_user.name or '', chat_info.id,
                         datasource_id=create_chat_obj.datasource, oid=current_user.oid or 1)
        return chat_info
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.error(f"Start chat error: {e}")
        t = _chat_trans(current_user)
        raise HTTPException(status_code=500, detail=t('i18n_chat.create_failed'))



@router.post("/recommend_questions/{chat_record_id}")
async def recommend_questions(session: SessionDep, current_user: CurrentUser, chat_record_id: int,
                              current_assistant: CurrentAssistant):
    def _return_empty():
        yield 'data:' + orjson.dumps({'content': '[]', 'type': 'recommended_question'}).decode() + '\n\n'

    try:
        record = get_chat_record_by_id(session, chat_record_id)

        if not record:
            return StreamingResponse(_return_empty(), media_type="text/event-stream")

        # 验证记录归属当前用户，防止 IDOR 越权访问
        if record.create_by != current_user.id:
            return StreamingResponse(_return_empty(), media_type="text/event-stream")

        request_question = ChatQuestion(chat_id=record.chat_id, question=record.question if record.question else '')

        llm_service = await LLMService.create(session, current_user, request_question, current_assistant, True)
        llm_service.set_record(record)
        llm_service.run_recommend_questions_task_async()
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()

        def _err(_e: Exception):
            # 不向客户端泄露内部异常详情，支持中英文
            _is_en = (current_user.language or '').lower().startswith('en')
            _msg = 'Failed to generate recommended questions' if _is_en else '推荐问题生成失败'
            yield 'data:' + orjson.dumps({'content': _msg, 'type': 'error'}).decode() + '\n\n'

        return StreamingResponse(_err(e), media_type="text/event-stream")

    return StreamingResponse(llm_service.await_result(), media_type="text/event-stream")








@router.post("/question")
async def stream_sql(session: SessionDep, current_user: CurrentUser, request_question: ChatQuestion,
                     current_assistant: CurrentAssistant):
    """Stream SQL analysis results"""

    # 输入验证：拒绝空白、纯特殊字符、超长输入
    is_valid, validation_msg = validate_chat_input(request_question.question)
    if not is_valid:
        def _validation_err():
            yield 'data:' + orjson.dumps({'content': orjson.dumps({'message': validation_msg, 'type': 'input-validation-err'}).decode(), 'type': 'error'}).decode() + '\n\n'
        return StreamingResponse(_validation_err(), media_type="text/event-stream")

    try:
        llm_service = await LLMService.create(session, current_user, request_question, current_assistant,
                                              embedding=True)
        llm_service.init_record(session=session)
        # 审计：记录用户查询
        try:
            log_query_executed(session, current_user.id, current_user.name or '',
                               request_question.chat_id, request_question.question,
                               oid=current_user.oid or 1)
        except Exception:
            pass  # 审计失败不影响主流程
        llm_service.run_task_async()
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()

        def _err(_e: Exception):
            # 不向客户端泄露内部异常详情
            yield 'data:' + orjson.dumps({'content': '服务处理异常，请稍后重试', 'type': 'error'}).decode() + '\n\n'

        return StreamingResponse(_err(e), media_type="text/event-stream")

    return StreamingResponse(llm_service.await_result(), media_type="text/event-stream")


@router.post("/record/{chat_record_id}/{action_type}")
async def analysis_or_predict(
    session: SessionDep, 
    current_user: CurrentUser, 
    chat_record_id: int, 
    action_type: str,
    current_assistant: CurrentAssistant,
    request_body: AnalysisPredictRequest = Body(default=AnalysisPredictRequest())
):
    # RAG 永远开启（对齐 SQLBot）
    rag_enabled = True
    try:
        if action_type != 'analysis' and action_type != 'predict':
            raise HTTPException(status_code=400, detail=f"Type {action_type} Not Found")
        record: ChatRecord | None = None

        # 查询完整的记录（包括 analysis_record_id 和 predict_record_id）
        stmt = select(ChatRecord).where(ChatRecord.id == chat_record_id)
        result = session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail=f"Chat record with id {chat_record_id} not found")

        # 验证记录归属当前用户，防止 IDOR 越权访问
        if record.create_by != current_user.id:
            raise HTTPException(status_code=404, detail=f"Chat record with id {chat_record_id} not found")

        # 对于分析和预测任务，从原始记录读取 chart 和 data
        base_record_id = chat_record_id
        if action_type == 'analysis' and record.analysis_record_id:
            base_record_id = record.analysis_record_id
        elif action_type == 'predict' and record.predict_record_id:
            base_record_id = record.predict_record_id
        
        # 如果需要从原始记录读取，重新查询
        if base_record_id != chat_record_id:
            stmt = select(ChatRecord.chart, ChatRecord.data).where(ChatRecord.id == base_record_id)
            result = session.execute(stmt)
            base_record = result.one_or_none()
            if base_record:
                # 使用 expunge 将 record 从 session 中分离后再修改
                # 直接修改 session 中的 ORM 对象会导致脏数据被意外 flush 到数据库
                session.expunge(record)
                record.chart = base_record.chart
                record.data = base_record.data

        # PDF数据源不支持数据分析和数据预测，在API层提前拦截
        try:
            from apps.chat.models.chat_model import Chat
            _chat = session.get(Chat, record.chat_id)
            if _chat:
                from apps.datasource.models.datasource import CoreDatasource as _APIDatasource
                _api_ds = session.get(_APIDatasource, _chat.datasource) if _chat.datasource else None
                if _api_ds and (_api_ds.type or '').lower() == 'pdf':
                    _action_label = '数据分析' if action_type == 'analysis' else '数据预测'
                    raise HTTPException(
                        status_code=400,
                        detail=f"PDF文档不支持{_action_label}功能。PDF属于非结构化文档类型，仅支持文档问答（内容理解、知识问答、内容总结）。"
                    )
        except HTTPException:
            raise
        except Exception as e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.error(f"[analysis_or_predict] PDF guard check failed: {e}")
            # 检查失败不阻断，让后续流程的PDF guard兜底

        # 验证是否有图表
        if not record.chart:
            raise HTTPException(status_code=400, 
                detail=f"Base record (id={base_record_id}) has not generated chart yet. Please generate a chart first before performing {action_type}.")

        # 验证是否有数据
        if not record.data:
            raise HTTPException(status_code=400, 
                detail=f"Base record (id={base_record_id}) has no data available. The data may not have been loaded or the query returned no results. Cannot perform {action_type}.")
        
        # 对于预测，需要额外验证数据是否包含时间序列和数值字段
        if action_type == 'predict':
            try:
                import orjson
                data_obj = orjson.loads(record.data) if isinstance(record.data, str) else record.data
                
                # 提取数据数组
                data_array = []
                if isinstance(data_obj, list):
                    data_array = data_obj
                elif isinstance(data_obj, dict) and 'data' in data_obj:
                    data_array = data_obj['data']
                
                if not data_array or len(data_array) < 3:
                    raise HTTPException(status_code=400, 
                        detail=f"Insufficient data rows for prediction. At least 3 rows are required for time series prediction, but only {len(data_array)} rows found. Please query more data.")
                
                # 检查是否有时间字段
                sample_rows = data_array[:min(3, len(data_array))]
                has_time_field = False
                has_numeric_field = False
                
                # 打印第一行数据用于调试
                from common.utils.utils import ChatBILogUtil
                from datetime import datetime as _dt, date as _date
                ChatBILogUtil.info(f"Checking time field in sample rows (count={len(sample_rows)})")
                
                # 同时检查字段名和字段值（与前端 advancedPredictionValidator 对齐）
                _time_field_name_pattern = re.compile(r'date|time|日期|时间|年|月|week|quarter|季度', re.IGNORECASE)
                
                for row in sample_rows:
                    for key, value in row.items():
                        # 方式1：字段名匹配时间模式（与前端、visualization_intent、llm.py 对齐）
                        if _time_field_name_pattern.search(str(key)):
                            has_time_field = True
                            ChatBILogUtil.info(f"Found time field by name: '{key}'")
                        
                        # 方式2：字段值匹配日期格式
                        if isinstance(value, str):
                            if re.match(r'^\d{4}[-/]\d{1,2}([-/]\d{1,2})?', value) or \
                               re.match(r'^\d{4}年\d{1,2}月(\d{1,2}日)?', value) or \
                               re.match(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}', value):
                                has_time_field = True
                                ChatBILogUtil.info(f"Found time field by value: '{key}' = '{value}'")
                        
                        # 也检查datetime对象（对齐run_task逻辑）
                        if isinstance(value, (_dt, _date)):
                            has_time_field = True
                        
                        if isinstance(value, (int, float)):
                            has_numeric_field = True
                        elif isinstance(value, str):
                            try:
                                float(value)
                                has_numeric_field = True
                            except (ValueError, TypeError):
                                pass
                        if has_time_field and has_numeric_field:
                            break  # 两个条件都满足，无需继续检查
                    if has_time_field and has_numeric_field:
                        break  # 两个条件都满足，无需继续检查行
                
                ChatBILogUtil.info(f"Time field check result: has_time_field={has_time_field}, has_numeric_field={has_numeric_field}")
                
                if not has_time_field:
                    # 提供更详细的错误信息，包括实际的字段名和值
                    first_row = data_array[0] if data_array else {}
                    field_info = ", ".join([f"'{k}': '{v}'" for k, v in first_row.items()])
                    raise HTTPException(status_code=400, 
                        detail=f"数据中缺少时间字段，无法进行时间序列预测。预测需要包含日期/时间数据（例如：'2024-01-01'、'2024年1月'）。当前数据字段：{field_info}")
                
                if not has_numeric_field:
                    raise HTTPException(status_code=400, 
                        detail="数据中缺少数值字段，无法进行预测。预测需要包含数值数据（例如：销售额、数量）。请查询包含数值的数据。")
                    
            except HTTPException:
                raise
            except Exception as e:
                from common.utils.utils import ChatBILogUtil
                ChatBILogUtil.error(f"Failed to validate prediction data: {e}")
                # 数据格式错误，但不阻止执行（让LLM处理）

        request_question = ChatQuestion(chat_id=record.chat_id, question=record.question)

        llm_service = await LLMService.create(session, current_user, request_question, current_assistant)
        # RAG 永远开启（对齐 SQLBot）
        llm_service.run_analysis_or_predict_task_async(session, action_type, record, True)
    except Exception as e:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()

        def _err(_e: Exception):
            # 不向客户端泄露内部异常详情
            # HTTPException 的 detail 是面向用户的消息，可以安全返回
            if isinstance(_e, HTTPException):
                yield 'data:' + orjson.dumps({'content': _e.detail, 'type': 'error'}).decode() + '\n\n'
            else:
                yield 'data:' + orjson.dumps({'content': '服务处理异常，请稍后重试', 'type': 'error'}).decode() + '\n\n'

        return StreamingResponse(_err(e), media_type="text/event-stream")

    return StreamingResponse(llm_service.await_result(), media_type="text/event-stream")


@router.get("/record/{chat_record_id}/excel/export")
async def export_excel(session: SessionDep, current_user: CurrentUser, chat_record_id: int, trans: Trans):
    # 添加 CurrentUser 鉴权，防止越权导出
    chat_record = session.get(ChatRecord, chat_record_id)
    if not chat_record or chat_record.create_by != current_user.id:
        raise HTTPException(
            status_code=404,
            detail=f"ChatRecord with id {chat_record_id} not found"
        )

    is_predict_data = chat_record.predict_record_id is not None

    _origin_data = format_json_data(get_chat_chart_data(chat_record_id=chat_record_id, session=session))

    _base_field = _origin_data.get('fields')
    _data = _origin_data.get('data')

    if not _data:
        raise HTTPException(
            status_code=500,
            detail=trans("i18n_excel_export.data_is_empty")
        )

    chart_info = get_chart_config(session, chat_record_id)

    _title = chart_info.get('title') if chart_info.get('title') else 'Excel'

    fields = []
    if chart_info.get('columns') and len(chart_info.get('columns')) > 0:
        for column in chart_info.get('columns'):
            fields.append(AxisObj(name=column.get('name'), value=column.get('value')))
    if chart_info.get('axis'):
        for _type in ['x', 'y', 'series']:
            if chart_info.get('axis').get(_type):
                column = chart_info.get('axis').get(_type)
                fields.append(AxisObj(name=column.get('name'), value=column.get('value')))

    _predict_data = []
    if is_predict_data:
        _predict_data = format_json_list_data(get_chat_predict_data(chat_record_id=chat_record_id, session=session))

    def inner():

        data_list = DataFormat.convert_large_numbers_in_object_array(_data + _predict_data)

        md_data, _fields_list = DataFormat.convert_object_array_for_pandas(fields, data_list)

        # data, _fields_list, col_formats = LLMService.format_pd_data(fields, _data + _predict_data)

        df = pd.DataFrame(md_data, columns=_fields_list)

        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine='xlsxwriter',
                            engine_kwargs={'options': {'strings_to_numbers': False}}) as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=False)

        buffer.seek(0)
        return io.BytesIO(buffer.getvalue())

    result = await asyncio.to_thread(inner)
    # 使用 urllib.parse.quote 对文件名进行编码，支持中文文件名
    from urllib.parse import quote
    safe_title = quote(_title, safe='')
    return StreamingResponse(
        result,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}.xlsx"}
    )


@router.get("/record/{chat_record_id}/csv/export")
async def export_csv(session: SessionDep, current_user: CurrentUser, chat_record_id: int, trans: Trans):
    """导出聊天记录数据为CSV格式"""
    chat_record = session.get(ChatRecord, chat_record_id)
    if not chat_record or chat_record.create_by != current_user.id:
        raise HTTPException(
            status_code=404,
            detail=f"ChatRecord with id {chat_record_id} not found"
        )

    is_predict_data = chat_record.predict_record_id is not None

    _origin_data = format_json_data(get_chat_chart_data(chat_record_id=chat_record_id, session=session))
    _data = _origin_data.get('data')

    if not _data:
        raise HTTPException(
            status_code=500,
            detail=trans("i18n_excel_export.data_is_empty")
        )

    chart_info = get_chart_config(session, chat_record_id)
    _title = chart_info.get('title') if chart_info.get('title') else 'data'

    fields = []
    if chart_info.get('columns') and len(chart_info.get('columns')) > 0:
        for column in chart_info.get('columns'):
            fields.append(AxisObj(name=column.get('name'), value=column.get('value')))
    if chart_info.get('axis'):
        for _type in ['x', 'y', 'series']:
            if chart_info.get('axis').get(_type):
                column = chart_info.get('axis').get(_type)
                fields.append(AxisObj(name=column.get('name'), value=column.get('value')))

    _predict_data = []
    if is_predict_data:
        _predict_data = format_json_list_data(get_chat_predict_data(chat_record_id=chat_record_id, session=session))

    def inner():
        data_list = DataFormat.convert_large_numbers_in_object_array(_data + _predict_data)
        md_data, _fields_list = DataFormat.convert_object_array_for_pandas(fields, data_list)
        df = pd.DataFrame(md_data, columns=_fields_list)

        buffer = io.BytesIO()
        df.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        return io.BytesIO(buffer.getvalue())

    result = await asyncio.to_thread(inner)
    from urllib.parse import quote
    safe_title = quote(_title, safe='')
    return StreamingResponse(
        result,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}.csv"}
    )
