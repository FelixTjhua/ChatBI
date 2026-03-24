"""对话状态追踪模块 (Dialogue State Tracking)"""
import re
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from common.utils.utils import ChatBILogUtil


class DialogueIntent(Enum):
    """对话意图类型"""
    QUERY = "query"                    # 数据查询
    ANALYSIS = "analysis"              # 数据分析
    PREDICTION = "prediction"          # 数据预测
    CLARIFICATION = "clarification"    # 澄清/追问
    CORRECTION = "correction"          # 修正/纠错
    FOLLOW_UP = "follow_up"            # 追问/深入
    TOPIC_SWITCH = "topic_switch"      # 话题切换
    COMPARISON = "comparison"          # 对比分析
    DRILL_DOWN = "drill_down"          # 下钻分析


class TopicStatus(Enum):
    """话题状态"""
    ACTIVE = "active"          # 当前活跃话题
    COMPLETED = "completed"    # 已完成的话题
    SUSPENDED = "suspended"    # 暂停的话题（可能回来）


@dataclass
class DialogueTurn:
    """单轮对话记录"""
    turn_index: int
    question: str
    intent: DialogueIntent
    topic: str = ""
    entities: List[str] = field(default_factory=list)
    # SQL相关
    sql_generated: str = ""
    sql_success: bool = False
    # 时间
    timestamp: float = field(default_factory=time.time)
    # 与上一轮的关系
    relation_to_prev: str = ""  # continuation, clarification, correction, new_topic
    # 添加 record_id 字段，支持基于记录ID的去重
    record_id: Optional[int] = None
    # 存储上下文引用解析结果，供后续轮次和LLM提示词注入使用
    context_references: List[Dict] = field(default_factory=list)


@dataclass
class TopicState:
    """话题状态"""
    topic_name: str
    status: TopicStatus = TopicStatus.ACTIVE
    start_turn: int = 0
    end_turn: int = -1
    turn_count: int = 0
    entities: List[str] = field(default_factory=list)
    summary: str = ""


class DialogueStateTracker:
    """对话状态追踪器"""

    # 澄清/追问关键词
    CLARIFICATION_KEYWORDS = [
        '什么意思', '怎么理解', '不太明白', '不理解',
        '再说一下', '能不能解释', '是不是说'
    ]

    # 修正关键词
    CORRECTION_KEYWORDS = [
        '不对', '错了', '应该是', '改成', '换成',
        '修改', '纠正', '更正'
    ]

    # 追问/深入关键词
    FOLLOW_UP_KEYWORDS = [
        '那么', '然后', '接着', '还有', '另外', '除此之外',
        '进一步', '深入', '更详细', '展开'
    ]

    # 下钻关键词
    DRILL_DOWN_KEYWORDS = [
        '按照', '细分', '拆分', '具体到', '每个',
        '各个', '分别', '逐一', '明细', '分组'
    ]

    # 对比关键词
    COMPARISON_KEYWORDS = [
        '对比', '比较', '相比', 'vs',
        '差异', '区别', '哪个更', '谁更'
    ]

    # 上下文引用模式
    # 增强上下文引用模式，覆盖更多自然语言指代表达
    CONTEXT_REF_PATTERNS = [
        (r'上面的|上述的|刚才的|之前的|前面的|上一个', 'prev_result'),
        (r'这个|这些|它的|它们的|该', 'current_entity'),
        (r'同样的|一样的|相同的|同样方法|同样条件', 'same_condition'),
        (r'换一个|换成|改为|用(.+?)替换|改成|调整为', 'modify_condition'),
        # 新增：动作延续类指代（"继续分析"、"再看看"、"深入一下"）
        (r'继续|接着|再看|深入|进一步|详细说|展开', 'prev_result'),
        # 新增：方法复用类指代（"用同样的方法分析另一个"）
        (r'同样.{0,4}方法|同样.{0,4}方式|照着.{0,4}做|按照.{0,4}来', 'same_condition'),
        # 新增：对比类指代（"和上次对比"、"跟之前比"）
        (r'和.{0,4}(上次|之前|刚才).{0,4}(对比|比较|比)|跟.{0,4}(上次|之前).{0,4}比', 'prev_result'),
    ]

    def __init__(self):
        self.turns: List[DialogueTurn] = []
        self.topics: List[TopicState] = []
        self.current_topic: Optional[TopicState] = None
        self.current_intent: DialogueIntent = DialogueIntent.QUERY
        self.entity_memory: Dict[str, List[str]] = {}  # 实体记忆

    def load_history(self, history_records: List[Dict]):
        """从数据库加载历史对话记录，恢复对话状态"""
        if not history_records:
            return
        
        try:
            for record in history_records:
                question = record.get('question', '')
                if not question:
                    continue
                # 从历史记录中正确提取 sql_success 状态
                _raw_success = record.get('sql_success')
                if _raw_success is None:
                    # 无 sql_success 字段：如果有 SQL 且无错误信息，推断为成功
                    _sql = record.get('sql', '')
                    _has_error = bool(record.get('error') or record.get('error_message'))
                    sql_success = bool(_sql and not _has_error)
                elif isinstance(_raw_success, str):
                    sql_success = _raw_success.lower() in ('true', '1', 'yes')
                else:
                    sql_success = bool(_raw_success)
                
                self.track_turn(
                    question=question,
                    sql=record.get('sql', ''),
                    sql_success=sql_success,
                    record_id=record.get('id'),  # 传入 record_id 用于去重判断
                )
            
            if self.turns:
                ChatBILogUtil.info(
                    f"Loaded {len(self.turns)} history turns, "
                    f"current topic: {self.current_topic.topic_name if self.current_topic else 'none'}, "
                    f"entities: {len(self.entity_memory)}"
                )
        except Exception as e:
            ChatBILogUtil.error(f"Failed to load dialogue history: {e}")

    def track_turn(
        self,
        question: str,
        sql: str = "",
        sql_success: bool = False,
        record_id: int = None
    ) -> Dict[str, Any]:
        """追踪新的对话轮次"""
        turn_index = len(self.turns)

        # 1. 意图检测
        intent = self._detect_intent(question)

        # 2. 实体提取
        entities = self._extract_entities(question)

        # 3. 话题检测
        topic, relation = self._detect_topic_change(question, entities, intent)

        # 4. 上下文引用解析
        context_refs = self._resolve_context_references(question)

        # 5. 创建轮次记录
        turn = DialogueTurn(
            turn_index=turn_index,
            question=question,
            intent=intent,
            topic=topic,
            entities=entities,
            sql_generated=sql,
            sql_success=sql_success,
            relation_to_prev=relation,
            record_id=record_id,
            context_references=context_refs
        )
        self.turns.append(turn)

        # 6. 更新话题状态
        self._update_topic_state(topic, turn_index, entities)

        # 7. 更新实体记忆
        for entity in entities:
            if entity not in self.entity_memory:
                self.entity_memory[entity] = []
            self.entity_memory[entity].append(str(turn_index))

        # 实体记忆清理，基于重要性而非仅时间
        # 保留最近20个实体，优先保留：当前话题实体 > 高频引用实体 > 最近引用实体
        MAX_ENTITY_MEMORY = 20
        if len(self.entity_memory) > MAX_ENTITY_MEMORY:
            # 当前话题的实体受保护，不被清理
            protected_entities = set()
            if self.current_topic:
                protected_entities.update(self.current_topic.entities)
            
            # 归一化 recency_score，避免高轮次时频次权重形同虚设
            # recency 归一化到 [0, 1]：(最近引用轮次 / 当前最大轮次)
            max_turn = max(turn_index, 1)
            entity_scores = {}
            for entity, turn_refs in self.entity_memory.items():
                if entity in protected_entities:
                    entity_scores[entity] = float('inf')  # 当前话题实体不清理
                else:
                    freq_score = min(len(turn_refs) / 5.0, 1.0) * 0.4  # 频次归一化到 [0,1]，5次封顶
                    recency_score = (max(int(t) for t in turn_refs) / max_turn if turn_refs else 0) * 0.6
                    entity_scores[entity] = freq_score + recency_score
            
            # 按分数从低到高排序，移除分数最低的
            sorted_entities = sorted(entity_scores.items(), key=lambda x: x[1])
            for entity, _ in sorted_entities[:len(self.entity_memory) - MAX_ENTITY_MEMORY]:
                del self.entity_memory[entity]

        self.current_intent = intent

        return {
            'turn_index': turn_index,
            'intent': intent.value,
            'topic': topic,
            'relation_to_prev': relation,
            'entities': entities,
            'context_references': context_refs,
            'topic_changed': relation == 'new_topic',
            'is_clarification': intent == DialogueIntent.CLARIFICATION,
            'is_correction': intent == DialogueIntent.CORRECTION,
            'is_follow_up': intent in (DialogueIntent.FOLLOW_UP, DialogueIntent.DRILL_DOWN),
            'dialogue_length': len(self.turns),
            'current_topic_turns': self.current_topic.turn_count if self.current_topic else 0
        }

    def _detect_intent(self, question: str) -> DialogueIntent:
        """检测对话意图"""
        q = question.strip()
        has_history = len(self.turns) > 0

        # === 1. 对话关系意图（需要有历史对话）===
        if has_history:
            if any(kw in q for kw in self.CLARIFICATION_KEYWORDS):
                return DialogueIntent.CLARIFICATION
            if any(kw in q for kw in self.CORRECTION_KEYWORDS):
                return DialogueIntent.CORRECTION
            if any(kw in q for kw in self.FOLLOW_UP_KEYWORDS):
                return DialogueIntent.FOLLOW_UP
            if any(kw in q for kw in self.DRILL_DOWN_KEYWORDS):
                return DialogueIntent.DRILL_DOWN

        # === 2. 业务意图（无论是否有历史都可识别）===
        if any(kw in q for kw in ['预测', '预估', '预计', '未来', '下一年', '明年', 'forecast', 'predict']):
            return DialogueIntent.PREDICTION
        # 对比
        if any(kw in q for kw in ['对比', '比较', '相比', '差异', 'vs', 'compare']):
            return DialogueIntent.COMPARISON
        # 分析
        if any(kw in q for kw in ['分析', '趋势', '原因', '为什么', '影响因素', 'analyze']):
            return DialogueIntent.ANALYSIS

        # === 3. 话题切换（兜底：无明确业务意图 + 实体重叠低）===
        if has_history and self._is_topic_switch(question):
            return DialogueIntent.TOPIC_SWITCH

        return DialogueIntent.QUERY

    # 业务实体关键词（用于实体提取增强）
    BUSINESS_ENTITY_PATTERNS = [
        # 业务指标
        r'(?:销售额|营收|收入|利润|毛利|净利|成本|费用|GMV|ROI|ARPU|CLV)',
        # 业务维度
        r'(?:产品|品类|品牌|部门|区域|渠道|门店|客户|用户|供应商)',
        # 时间维度
        r'(?:季度|月度|年度|周度|日度)',
        # 分析指标
        r'(?:增长率|转化率|复购率|留存率|流失率|客单价|坪效|人效|市场份额)',
    ]

    # 复合实体模式（用于提取"华东区域"、"A品牌"等修饰+实体组合）
    COMPOUND_ENTITY_PATTERNS = [
        # 区域+维度：华东区域、北方市场、一线城市
        r'(?:华东|华南|华北|华中|西南|西北|东北|北方|南方|一线|二线|三线|四线|五线)(?:区域|地区|市场|城市)',
        # 品牌/产品修饰：A品牌、高端产品、新品
        r'(?:[A-Za-z\u4e00-\u9fff]{1,4})(?:品牌|产品|系列|型号)',
        # 部门修饰：销售部、技术部、华东分公司
        r'(?:[A-Za-z\u4e00-\u9fff]{1,6})(?:部门|部|分公司|事业部|团队|组)',
        # 渠道修饰：线上渠道、电商平台、直营店
        r'(?:线上|线下|电商|直营|加盟|批发|零售)(?:渠道|平台|门店|店铺)',
        # 客户分类：VIP客户、新客户、大客户
        r'(?:VIP|新|老|大|小|核心|重点|潜在|流失)(?:客户|用户|会员)',
    ]

    def _extract_entities(self, question: str) -> List[str]:
        """提取问题中的关键实体"""
        # 停用词集合：常见动词、助词、连词等不应作为实体的词
        ENTITY_STOP_WORDS = {
            '查询', '统计', '显示', '帮我', '请问', '一下', '什么', '哪些', '多少',
            '怎么', '如何', '分析', '对比', '比较', '计算', '列出', '展示', '看看',
            '告诉', '给我', '我想', '知道', '了解', '查看', '需要', '可以', '能否',
            '是否', '为什么', '请', '的', '了', '吗', '呢', '吧', '啊', '哦',
            '和', '与', '或', '但', '而', '也', '都', '就', '在', '有', '是',
            '不', '没', '很', '更', '最', '这', '那', '它', '他', '她',
        }
        entities = []

        # 提取引号中的内容
        quoted = re.findall(r'[""「」『』](.+?)[""「」『』]', question)
        entities.extend(quoted)

        # 提取数字+单位
        numbers = re.findall(r'\d+(?:\.\d+)?(?:万|亿|千|百|%|元|个|条|项)?', question)
        entities.extend(numbers)

        # 提取时间表达
        times = re.findall(r'\d{4}年|\d{1,2}月|\d{1,2}日|今年|去年|上个月|本月|Q[1-4]', question)
        entities.extend(times)

        for pattern in self.COMPOUND_ENTITY_PATTERNS:
            matches = re.findall(pattern, question)
            entities.extend(matches)

        for pattern in self.BUSINESS_ENTITY_PATTERNS:
            matches = re.findall(pattern, question)
            entities.extend(matches)

        # 过滤停用词
        filtered = [e for e in set(entities) if e not in ENTITY_STOP_WORDS and len(e.strip()) > 0]
        return filtered

    def _detect_topic_change(
        self,
        question: str,
        entities: List[str],
        intent: DialogueIntent
    ) -> Tuple[str, str]:
        """检测话题变化"""
        # 如果是第一轮，直接创建新话题
        if not self.turns:
            topic = self._generate_topic_name(question)
            return topic, "new_topic"

        prev_turn = self.turns[-1]

        # 修正/澄清不算话题切换
        if intent in (DialogueIntent.CLARIFICATION, DialogueIntent.CORRECTION):
            return prev_turn.topic, "clarification" if intent == DialogueIntent.CLARIFICATION else "correction"

        # 追问/下钻是话题延续
        if intent in (DialogueIntent.FOLLOW_UP, DialogueIntent.DRILL_DOWN):
            return prev_turn.topic, "continuation"

        # 消除 _detect_topic_change 和 _is_topic_switch 使用不同阈值的问题
        if self._is_topic_switch(question):
            topic = self._generate_topic_name(question)
            return topic, "new_topic"

        return prev_turn.topic, "continuation"

    def _is_topic_switch(self, question: str) -> bool:
        """
        判断是否为话题切换
        
         使用词级重叠替代字符级重叠，并考虑语义动作变化。
        "查询销售额" vs "分析销售额趋势" 共享"销售额"但动作从查询变为分析，
        应视为话题延续（同一数据不同操作），而非话题切换。
        """
        if not self.turns:
            return False

        prev = self.turns[-1].question
        # 提取2字以上的中文词组和英文单词
        prev_words = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]+', prev.lower()))
        curr_words = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]+', question.lower()))
        # 移除常见停用词和操作词（操作词变化不算话题切换）
        stop_words = {'查询', '统计', '显示', '帮我', '请问', '一下', '什么', '哪些', '多少', '怎么', '如何'}
        action_words = {'分析', '预测', '对比', '比较', '趋势', '排名', '排序', '计算', '列出', '展示'}
        prev_words -= stop_words
        curr_words -= stop_words
        
        # 计算去除操作词后的实体重叠（核心话题是否相同）
        prev_entities = prev_words - action_words
        curr_entities = curr_words - action_words
        
        if not prev_entities or not curr_entities:
            # 无有效实体词，用全词集判断
            if not prev_words or not curr_words:
                return True
            overlap = len(prev_words & curr_words) / max(len(prev_words | curr_words), 1)
            return overlap < 0.2
        
        entity_overlap = len(prev_entities & curr_entities) / max(len(prev_entities | curr_entities), 1)
        return entity_overlap < 0.15  # 实体重叠低于15%才算话题切换

    def _generate_topic_name(self, question: str) -> str:
        """从问题生成话题名称"""
        # 取问题的前20个字符作为话题名
        clean = re.sub(r'[？?！!。，,\s]+', '', question)
        return clean[:20] if len(clean) > 20 else clean

    def _update_topic_state(self, topic: str, turn_index: int, entities: List[str]):
        """更新话题状态"""
        if self.current_topic and self.current_topic.topic_name == topic:
            self.current_topic.turn_count += 1
            self.current_topic.entities = list(set(self.current_topic.entities + entities))
        else:
            # 关闭当前话题
            if self.current_topic:
                self.current_topic.status = TopicStatus.COMPLETED
                self.current_topic.end_turn = turn_index - 1

            # 创建新话题
            new_topic = TopicState(
                topic_name=topic,
                status=TopicStatus.ACTIVE,
                start_turn=turn_index,
                turn_count=1,
                entities=entities
            )
            self.topics.append(new_topic)
            self.current_topic = new_topic

    @staticmethod
    def _extract_outermost_where(sql: str) -> Optional[str]:
        """从 SQL 中提取最外层 WHERE 子句的条件部分。"""
        if not sql:
            return None
        
        # 将 SQL 转为大写用于关键词匹配，保留原始大小写用于结果
        sql_upper = sql.upper()
        depth = 0
        outermost_where_pos = -1
        i = 0
        in_single_quote = False
        in_double_quote = False
        
        while i < len(sql_upper):
            ch = sql_upper[i]
            
            # 跟踪字符串字面量状态，跳过引号内的内容
            if ch == "'" and not in_double_quote:
                # 处理转义的单引号 ''
                if i + 1 < len(sql_upper) and sql_upper[i + 1] == "'":
                    i += 2
                    continue
                in_single_quote = not in_single_quote
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif not in_single_quote and not in_double_quote:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth = max(0, depth - 1)
                elif depth == 0 and sql_upper[i:i+5] == 'WHERE' and (i == 0 or not sql_upper[i-1].isalpha()):
                    # 确保 WHERE 是完整关键词（前面不是字母）
                    after = i + 5
                    if after >= len(sql_upper) or not sql_upper[after].isalpha():
                        outermost_where_pos = i
            i += 1
        
        if outermost_where_pos < 0:
            return None
        
        # 从最后一个顶层 WHERE 开始，提取到 GROUP/ORDER/LIMIT/HAVING 或末尾
        after_where = sql[outermost_where_pos + 5:].strip()
        # 在顶层找终止关键词
        depth = 0
        end_pos = len(after_where)
        j = 0
        in_single_quote = False
        in_double_quote = False
        terminators = ['GROUP', 'ORDER', 'LIMIT', 'HAVING']
        while j < len(after_where):
            ch = after_where[j]
            # 跟踪字符串字面量
            if ch == "'" and not in_double_quote:
                if j + 1 < len(after_where) and after_where[j + 1] == "'":
                    j += 2
                    continue
                in_single_quote = not in_single_quote
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif not in_single_quote and not in_double_quote:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth = max(0, depth - 1)
                elif depth == 0:
                    upper_rest = after_where[j:].upper()
                    for term in terminators:
                        if upper_rest.startswith(term) and (j == 0 or not after_where[j-1].isalpha()):
                            after_term = j + len(term)
                            if after_term >= len(after_where) or not after_where[after_term].isalpha():
                                end_pos = j
                                break
                    if end_pos != len(after_where):
                        break
            j += 1
        
        condition = after_where[:end_pos].strip().rstrip(';').strip()
        return condition if condition else None

    def _resolve_context_references(self, question: str) -> List[Dict[str, str]]:
        """解析上下文引用"""
        refs = []
        for pattern, ref_type in self.CONTEXT_REF_PATTERNS:
            if re.search(pattern, question):
                refs.append({
                    'type': ref_type,
                    'pattern': pattern,
                    'resolved': self._resolve_reference(ref_type)
                })
        return refs

    def _resolve_reference(self, ref_type: str) -> str:
        """解析具体的引用内容"""
        if not self.turns:
            return ""

        prev = self.turns[-1]

        if ref_type == 'prev_result':
            # 引用前一轮的查询结果：优先使用SQL，其次使用问题
            if prev.sql_generated:
                sql_brief = prev.sql_generated[:200]
                question_brief = prev.question[:80] if prev.question else ''
                return f"Previous query / 前一轮查询「{question_brief}」(SQL: {sql_brief})"
            elif prev.question:
                return f"Answer to previous question / 前一轮问题「{prev.question[:80]}」的回答内容"
            return ""

        elif ref_type == 'current_entity':
            # 引用当前话题中的实体
            if prev.entities:
                entity_str = ', '.join(prev.entities[:5])
                return f"Current entities / 当前讨论的实体: {entity_str}"
            if prev.question:
                return f"Previous topic / 前一轮讨论的主题「{prev.question[:60]}」"
            return ""

        elif ref_type == 'same_condition':
            # 沿用前一轮的查询条件
            if prev.sql_generated:
                condition = self._extract_outermost_where(prev.sql_generated)
                if condition:
                    return f"Reuse previous filter / 沿用前一轮的筛选条件: {condition[:150]}"
            if prev.question:
                return f"Reuse conditions from / 沿用前一轮「{prev.question[:60]}」中的条件"
            return "Reuse previous query conditions / 沿用前一轮的查询条件"

        elif ref_type == 'modify_condition':
            # 修改前一轮的条件
            if prev.sql_generated:
                condition = self._extract_outermost_where(prev.sql_generated)
                if condition:
                    return f"Modify previous condition / 在前一轮条件「{condition[:120]}」的基础上修改"
            if prev.question:
                return f"Adjust conditions from / 在前一轮「{prev.question[:60]}」的基础上调整条件"
            return "Modify previous query conditions / 修改前一轮的查询条件"

        return ""

    def get_dialogue_context(self, max_turns: int = 5) -> Dict[str, Any]:
        """获取对话上下文摘要（用于注入LLM提示词）"""
        recent_turns = self.turns[-max_turns:] if self.turns else []

        # 将上下文引用解析结果包含在对话上下文中
        # 当用户说"继续分析上面的数据"时，LLM需要知道"上面的"指的是什么
        context_refs = []
        if self.turns:
            latest_turn = self.turns[-1]
            if latest_turn.context_references:
                context_refs = [
                    {'type': ref.get('type', ''), 'resolved': ref.get('resolved', '')}
                    for ref in latest_turn.context_references
                    if ref.get('resolved')
                ]

        return {
            'total_turns': len(self.turns),
            'current_intent': self.current_intent.value,
            'current_topic': self.current_topic.topic_name if self.current_topic else "",
            'topic_turn_count': self.current_topic.turn_count if self.current_topic else 0,
            'recent_questions': [t.question for t in recent_turns],
            'recent_intents': [t.intent.value for t in recent_turns],
            'active_entities': list(self.entity_memory.keys())[-10:],
            'context_references': context_refs,
            'topic_history': [
                {'name': t.topic_name, 'status': t.status.value, 'turns': t.turn_count}
                for t in self.topics[-5:]
            ]
        }

    def map_to_rewriter_intent(self) -> str:
        """统一 DialogueIntent 与 QueryRewriter 9种意图的映射"""
        _DIALOGUE_TO_REWRITER = {
            DialogueIntent.QUERY: 'fact_query',
            DialogueIntent.ANALYSIS: 'statistical_analysis',
            DialogueIntent.PREDICTION: 'prediction',
            DialogueIntent.COMPARISON: 'comparison_analysis',
            DialogueIntent.FOLLOW_UP: 'follow_up',
            DialogueIntent.DRILL_DOWN: 'follow_up',
            DialogueIntent.CLARIFICATION: 'follow_up',
            DialogueIntent.CORRECTION: 'follow_up',
            DialogueIntent.TOPIC_SWITCH: 'fact_query',
        }
        return _DIALOGUE_TO_REWRITER.get(self.current_intent, 'fact_query')

    def get_state_summary(self) -> Dict[str, Any]:
        """获取对话状态摘要（用于前端展示）"""
        # 提取最近一轮的上下文引用解析结果
        context_references = []
        if self.turns:
            latest_turn = self.turns[-1]
            if latest_turn.context_references:
                for ref in latest_turn.context_references:
                    ref_type = ref.get('type', '')
                    pattern = ref.get('pattern', '')
                    resolved = ref.get('resolved', '')
                    if resolved:
                        # 从最近一轮的问题中提取匹配的原始文本
                        original_text = ''
                        match = re.search(pattern, latest_turn.question)
                        if match:
                            original_text = match.group(0)
                        context_references.append({
                            'original': original_text or ref_type,
                            'resolved': resolved,
                            'type': ref_type,
                            'confidence': 0.85 if len(self.turns) > 1 else 0.6,
                        })

        # 构建话题变化时间线（含时间戳）
        topic_timeline = []
        for t in self.topics:
            start_ts = self.turns[t.start_turn].timestamp if t.start_turn < len(self.turns) else 0
            topic_timeline.append({
                'name': t.topic_name,
                'status': t.status.value,
                'turns': t.turn_count,
                'start_turn': t.start_turn,
                'timestamp': start_ts,
            })

        # 构建意图变化轨迹（每轮对话的意图）
        intent_history = []
        for turn in self.turns:
            intent_history.append({
                'turn': turn.turn_index,
                'intent': turn.intent.value,
                'topic': turn.topic,
                'timestamp': turn.timestamp,
            })

        return {
            'dialogue_length': len(self.turns),
            'current_intent': self.current_intent.value,
            'current_topic': self.current_topic.topic_name if self.current_topic else "",
            'topic_count': len(self.topics),
            'entity_count': len(self.entity_memory),
            'topics': [
                {
                    'name': t.topic_name,
                    'status': t.status.value,
                    'turns': t.turn_count
                }
                for t in self.topics
            ],
            'context_references': context_references,
            'topic_timeline': topic_timeline,
            'intent_history': intent_history,
        }
