"""图表生成服务 - 从llm.py中提取的图表生成相关逻辑"""
import time
from typing import Optional, Dict, Any

import orjson
from langchain_core.messages import HumanMessage, AIMessage
from sqlmodel import Session

from apps.chat.crud.chat import (
    save_chart_answer, save_chart, start_log, end_log,
    get_chart_config, format_chart_fields
)
from apps.chat.models.chat_model import OperationEnum
from apps.chat.thinking.thinking_integration import record_chart_stage
from common.error import SingleMessageError
from common.utils.utils import ChatBILogUtil, extract_nested_json, extract_json_robust


class ChartGeneratorMixin:
    """图表生成相关方法的Mixin类"""

    def get_fields_from_chart(self, _session: Session, record_id: int = None):
        # 允许指定 record_id，默认使用 self.record.id
        if record_id is None:
            record_id = self.record.id
        chart_info = get_chart_config(_session, record_id)
        return format_chart_fields(chart_info)

    def generate_chart(self, _session: Session, chart_type: Optional[str] = ''):
        # append current question
        self.chart_message.append(HumanMessage(self.chat_question.chart_user_question(chart_type)))

        self.current_logs[OperationEnum.GENERATE_CHART] = start_log(session=_session,
                                                                    ai_modal_id=self.chat_question.ai_modal_id,
                                                                    ai_modal_name=self.chat_question.ai_modal_name,
                                                                    operate=OperationEnum.GENERATE_CHART,
                                                                    record_id=self.record.id,
                                                                    full_message=[
                                                                        {'type': msg.type, 'content': msg.content} for
                                                                        msg
                                                                        in self.chart_message])
        
        # 使用普通LLM进行图表配置生成（不使用JSON模式，以保留<think>标签的推理输出）
        # extract_json_robust可以从普通输出中正确提取JSON结果
        
        full_thinking_text = ''
        full_chart_text = ''
        token_usage = {}
        
        # 记录LLM调用开始时间
        llm_start_time = time.time()
        
        from apps.chat.task.llm import process_stream, stream_with_retry
        
        # 空响应自动重试（最多重试2次，指数退避）
        _max_empty_retries = 2
        _original_chart_user_msg = self.chart_message[-1].content if self.chart_message else ''
        for _empty_attempt in range(_max_empty_retries + 1):
            full_thinking_text = ''  # 重试时需要重置
            full_chart_text = ''
            
            res = process_stream(stream_with_retry(self.llm, self.chart_message), token_usage)
            for chunk in res:
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_chart_text += content
                reasoning_content = chunk.get('reasoning_content')
                if reasoning_content:
                    full_thinking_text += reasoning_content
                yield chunk
            
            # 如果有内容（包括仅有推理内容），跳出重试循环
            if (full_chart_text and full_chart_text.strip()) or (full_thinking_text and full_thinking_text.strip()):
                break
            
            # 空响应：判断是否需要重试
            if _empty_attempt < _max_empty_retries:
                _wait_time = 1.0 * (2 ** _empty_attempt)  # 指数退避：1s, 2s
                ChatBILogUtil.warning(
                    f"[generate_chart] LLM returned empty content (attempt {_empty_attempt + 1}/{_max_empty_retries + 1}), "
                    f"retrying in {_wait_time:.0f}s... Token usage: {token_usage}"
                )
                _is_en_retry_ch = (self.chat_question.lang or '').lower().startswith('en')
                _retry_hint_ch = (f"\n\n(Retry attempt {_empty_attempt + 2}: Please generate the chart configuration JSON now.)"
                                  if _is_en_retry_ch else
                                  f"\n\n（第{_empty_attempt + 2}次请求：请立即生成图表配置JSON。）")
                self.chart_message[-1] = HumanMessage(content=_original_chart_user_msg + _retry_hint_ch)
                time.sleep(_wait_time)
            # else: 最后一次尝试也失败，继续到下面的保存逻辑
        
        # 安全兜底：如果LLM只输出了推理内容但没有最终回答
        if not full_chart_text.strip() and full_thinking_text.strip():
            ChatBILogUtil.warning(
                f"[generate_chart] LLM returned only reasoning content (length={len(full_thinking_text)}), "
                f"attempting to use as chart text"
            )
            full_chart_text = full_thinking_text

        self.chart_message.append(AIMessage(full_chart_text))

        self.record = save_chart_answer(session=_session, record_id=self.record.id,
                                        answer=orjson.dumps({'content': full_chart_text, 'reasoning_content': full_thinking_text}).decode())
        self.current_logs[OperationEnum.GENERATE_CHART] = end_log(session=_session,
                                                                  log=self.current_logs[OperationEnum.GENERATE_CHART],
                                                                  full_message=[
                                                                      {'type': msg.type, 'content': msg.content}
                                                                      for msg in self.chart_message],
                                                                  reasoning_content=full_thinking_text,
                                                                  token_usage=token_usage)
        
        # 计算图表生成耗时（使用实际的LLM调用时间）
        chart_generation_time = time.time() - llm_start_time
        
        # 记录图表生成阶段到思考过程
        try:
            # 不调用check_save_chart（会重复保存到DB），只解析JSON获取chart_type
            chart_type_for_thinking = 'unknown'
            try:
                json_str = extract_json_robust(full_chart_text)
                if json_str:
                    parsed = orjson.loads(json_str)
                    chart_type_for_thinking = parsed.get('type', 'unknown')
            except Exception:
                pass
            
            record_chart_stage(
                self.thinking_process,
                chart_type=chart_type_for_thinking,
                reasoning=full_thinking_text,
                generation_time=chart_generation_time,
                token_usage=token_usage
            )
            
            # 发送图表思考过程
            chart_stage_data = self.thinking_process.get_stage('chart_generation')
            if chart_stage_data:
                yield {'type': 'thinking_stage', 'stage': 'chart_generation', 'data': chart_stage_data}
            
            # 记录AntV G2可视化配置生成阶段
            try:
                from apps.chat.thinking.thinking_integration import record_antv_g2_config_stage
                _chart_dimensions = {}
                try:
                    _chart_json_str = extract_json_robust(full_chart_text)
                    if _chart_json_str:
                        _chart_parsed = orjson.loads(_chart_json_str)
                        if _chart_parsed.get('axis'):
                            _chart_dimensions = _chart_parsed['axis']
                        elif _chart_parsed.get('columns'):
                            _chart_dimensions = {'columns': _chart_parsed['columns']}
                except Exception:
                    pass
                record_antv_g2_config_stage(
                    self.thinking_process,
                    chart_type=chart_type_for_thinking,
                    dimensions=_chart_dimensions,
                )
                _g2_stage = self.thinking_process.get_stage('antv_g2_config')
                if _g2_stage:
                    yield {'type': 'thinking_stage', 'stage': 'antv_g2_config', 'data': _g2_stage}
            except Exception as e2:
                ChatBILogUtil.error(f"Failed to record antv_g2_config stage: {e2}")
        except Exception as e:
            ChatBILogUtil.error(f"Failed to record chart thinking stage: {e}")

    @staticmethod
    def get_chart_type_from_sql_answer(res: str) -> Optional[str]:
        """获取图表类型"""
        # 优先使用 extract_json_robust 进行更健壮的 JSON 提取
        json_str = extract_json_robust(res)
        if json_str is None:
            json_str = extract_nested_json(res)
        if json_str is None:
            return None

        chart_type: Optional[str]
        data: dict
        try:
            data = orjson.loads(json_str)

            if data.get('success'):
                chart_type = data.get('chart-type')
            else:
                return None
        except Exception:
            return None

        return chart_type

    def check_save_chart(self, session: Session, res: str) -> Dict[str, Any]:
        _is_en = (self.chat_question.lang or '').lower().startswith('en') if hasattr(self, 'chat_question') else True
        _parse_err_msg = ('Unable to parse chart configuration, please try again'
                          if _is_en else '无法解析图表配置，请重新提问')
        
        # 使用强大的 JSON 提取函数
        json_str = extract_json_robust(res)
        
        if json_str is None:
            raise SingleMessageError(orjson.dumps({'message': _parse_err_msg,
                                                   'traceback': "Cannot parse chart config from answer:\n" + res}).decode())
        data: dict

        chart: Dict[str, Any] = {}
        message = ''
        error = False

        try:
            data = orjson.loads(json_str)
            ChatBILogUtil.info(f"Parsed chart data: {data}")
            ChatBILogUtil.info(f"Chart type: {data.get('type')}")
            
            if data.get('type') and data.get('type') != 'error':
                # 图表类型校验
                chart = data
                ChatBILogUtil.info(f"Chart before processing: {chart}")
                
                # 如果columns是字典（错误格式），转换为axis格式
                if chart.get('columns') and isinstance(chart.get('columns'), dict):
                    # LLM生成了错误的columns格式，转换为正确的axis格式
                    columns_dict = chart.pop('columns')
                    chart['axis'] = {}
                    if 'x' in columns_dict:
                        chart['axis']['x'] = columns_dict['x']
                        if chart['axis']['x'].get('value'):
                            chart['axis']['x']['value'] = str(chart['axis']['x'].get('value')).lower()
                    if 'y' in columns_dict:
                        chart['axis']['y'] = columns_dict['y']
                        if chart['axis']['y'].get('value'):
                            chart['axis']['y']['value'] = str(chart['axis']['y'].get('value')).lower()
                    if 'series' in columns_dict:
                        chart['axis']['series'] = columns_dict['series']
                        if chart['axis']['series'].get('value'):
                            chart['axis']['series']['value'] = str(chart['axis']['series'].get('value')).lower()
                elif chart.get('columns') and isinstance(chart.get('columns'), list):
                    # columns是列表（table类型的正确格式）
                    for v in chart.get('columns'):
                        if v.get('value'):
                            v['value'] = str(v.get('value')).lower()
                
                if chart.get('axis'):
                    if chart.get('axis').get('x') and chart.get('axis').get('x').get('value'):
                        chart.get('axis').get('x')['value'] = str(chart.get('axis').get('x').get('value')).lower()
                    if chart.get('axis').get('y') and chart.get('axis').get('y').get('value'):
                        chart.get('axis').get('y')['value'] = str(chart.get('axis').get('y').get('value')).lower()
                    if chart.get('axis').get('series') and chart.get('axis').get('series').get('value'):
                        chart.get('axis').get('series')['value'] = str(chart.get('axis').get('series').get('value')).lower()
                
                ChatBILogUtil.info(f"Chart after processing: {chart}")
                
                # 验证chart不为空
                if not chart or not chart.get('type'):
                    raise Exception('Chart is empty after processing')
                
                # 验证图表类型为支持的类型之一
                valid_chart_types = {'table', 'column', 'bar', 'line', 'pie', 'box', 'area', 'heatmap', 'dual_axis', 'sankey', 'funnel', 'kpi', 'scatter', 'radar', 'waterfall', 'treemap', 'rose', 'gauge'}
                if chart.get('type') not in valid_chart_types:
                    ChatBILogUtil.warning(f"Unknown chart type '{chart.get('type')}', falling back to 'table'")
                    chart['type'] = 'table'
                    
            elif data.get('type') == 'error':
                message = data.get('reason', 'Chart generation failed')
                error = True
            else:
                ChatBILogUtil.error(f"Chart validation failed - data: {data}, type: {data.get('type')}")
                raise Exception('Chart is empty')
        except Exception as e:
            ChatBILogUtil.error(f"Exception in check_save_chart: {str(e)}, type: {type(e)}")
            error = True
            message = orjson.dumps({'message': _parse_err_msg,
                                    'traceback': f"Cannot parse chart config from answer:\n{res}\nError: {str(e)}"}).decode()

        if error:
            raise SingleMessageError(message)

        save_chart(session=session, chart=orjson.dumps(chart).decode(), record_id=self.record.id)

        return chart
