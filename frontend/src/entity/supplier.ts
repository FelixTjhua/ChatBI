import icon_openai_colorful from '@/assets/model/icon_openai_colorful.svg?url'
import icon_grok_colorful from '@/assets/model/icon_grok_colorful.svg?url'
import icon_claude_colorful from '@/assets/model/icon_claude_colorful.svg?url'
import icon_deepseek_colorful from '@/assets/model/icon_deepseek_colorful.svg?url'
import icon_gemini_colorful from '@/assets/model/icon_gemini_colorful.svg?url'
import icon_qwen_colorful from '@/assets/model/icon_qwen_colorful.svg?url'

type ModelArg = { key: string; val?: string | number; type: string; range?: string }
type ModelOption = { name: string; api_domain?: string; args?: ModelArg[] }
type ModelConfig = Record<
  number,
  {
    api_domain: string
    common_args?: ModelArg[]
    model_options: ModelOption[]
  }
>

export const supplierList: Array<{
  id: number
  name: string
  i18nKey: string
  icon: any
  type?: string
  is_private?: boolean
  model_config: ModelConfig
}> = [
  {
    id: 7,
    name: 'ChatGPT',
    i18nKey: 'supplier.chatgpt',
    icon: icon_openai_colorful,
    is_private: true,
    model_config: {
      0: {
        api_domain: 'https://api.openai.com/v1',
        common_args: [{ key: 'temperature', val: 1.0, type: 'number', range: '[0, 2]' }],
        model_options: [
          { name: 'gpt-4.1' },
          { name: 'gpt-4.1-mini' },
          { name: 'gpt-4.1-nano' },
          { name: 'gpt-4o' },
          { name: 'gpt-4o-mini' },
          { name: 'o4-mini' },
          { name: 'o3' },
          { name: 'o3-mini' },
          { name: 'o1' },
          { name: 'o1-mini' },
        ],
      },
    },
  },
  {
    id: 16,
    name: 'Grok',
    i18nKey: 'supplier.grok',
    icon: icon_grok_colorful,
    model_config: {
      0: {
        api_domain: 'https://api.x.ai/v1',
        common_args: [{ key: 'temperature', val: 0.7, type: 'number', range: '[0, 1]' }],
        model_options: [
          { name: 'grok-4' },
          { name: 'grok-3' },
          { name: 'grok-3-fast' },
          { name: 'grok-3-mini' },
          { name: 'grok-3-mini-fast' },
          { name: 'grok-2' },
        ],
      },
    },
  },
  {
    id: 15,
    name: 'Claude',
    i18nKey: 'supplier.claude',
    icon: icon_claude_colorful,
    model_config: {
      0: {
        api_domain: 'https://api.anthropic.com/v1',
        common_args: [{ key: 'temperature', val: 0.7, type: 'number', range: '[0, 1]' }],
        model_options: [
          { name: 'claude-sonnet-4-20250514' },
          { name: 'claude-opus-4-20250514' },
          { name: 'claude-haiku-4-20250514' },
          { name: 'claude-3-5-sonnet-20241022' },
          { name: 'claude-3-5-haiku-20241022' },
          { name: 'claude-3-opus-20240229' },
        ],
      },
    },
  },
  {
    id: 3,
    name: 'DeepSeek',
    i18nKey: 'supplier.deepseek',
    icon: icon_deepseek_colorful,
    model_config: {
      0: {
        api_domain: 'https://api.deepseek.com',
        model_options: [
          { name: 'deepseek-chat' },
          { name: 'deepseek-reasoner' },
        ],
      },
    },
  },
  {
    id: 6,
    name: 'Gemini',
    i18nKey: 'supplier.gemini',
    icon: icon_gemini_colorful,
    model_config: {
      0: {
        api_domain: 'https://generativelanguage.googleapis.com/v1beta/openai/',
        common_args: [{ key: 'temperature', val: 0.7, type: 'number', range: '(0, 1]' }],
        model_options: [
          { name: 'gemini-2.5-pro' },
          { name: 'gemini-2.5-flash' },
          { name: 'gemini-2.5-flash-lite' },
          { name: 'gemini-2.0-flash' },
          { name: 'gemini-2.0-flash-lite' },
        ],
      },
    },
  },
  {
    id: 17,
    name: 'Qwen',
    i18nKey: 'supplier.qwen',
    icon: icon_qwen_colorful,
    model_config: {
      0: {
        api_domain: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        common_args: [
          { key: 'temperature', val: 1.0, type: 'number', range: '[0, 2)' },
          { key: 'extra_body', val: '{"enable_thinking": false}', type: 'json' },
        ],
        model_options: [
          { name: 'qwen3-coder-plus' },
          { name: 'qwen3-coder-flash' },
          { name: 'qwen-plus' },
          { name: 'qwen-max' },
          { name: 'qwen-turbo' },
          { name: 'qwen-long' },
        ],
      },
    },
  },
]

export const base_model_options = (supplier_id: number, model_type?: number) => {
  const supplier = get_supplier(supplier_id)
  return supplier?.model_config[model_type || 0].model_options
}

export const get_supplier = (supplier_id: number) => {
  return supplierList.find((item: any) => item.id === supplier_id)
}
