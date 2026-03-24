import { request } from '@/utils/request'

export const promptApi = {
  getList: (pageNum: any, pageSize: any, type: any, params: any) =>
    request.get(`/system/custom_prompt/${type}/page/${pageNum}/${pageSize}`, {
      params,
    }),
  updateEmbedded: (data: any) => request.put(`/system/custom_prompt`, data),
  // 改用 POST 方法发送批量删除请求
  deleteEmbedded: (ids: number[], promptType?: string) =>
    request.post('/system/custom_prompt/batch_delete', { ids, prompt_type: promptType }),
  // 单条删除
  deleteSingle: (id: number, promptType?: string) =>
    request.delete(`/system/custom_prompt/${id}`, {
      params: promptType ? { prompt_type: promptType } : {},
    }),
  // 传递 prompt_type 参数消歧，避免跨表 ID 冲突
  getOne: (id: any, promptType?: string) =>
    request.get(`/system/custom_prompt/detail/${id}`, {
      params: promptType ? { prompt_type: promptType } : {},
    }),
  export2Excel: (type: any, params: any) =>
    request.get(`/system/custom_prompt/${type}/export`, {
      params,
      responseType: 'blob',
      requestOptions: { customError: true },
    }),
}
