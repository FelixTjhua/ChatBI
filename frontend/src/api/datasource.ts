import { request } from '@/utils/request'

export const datasourceApi = {
  // 文档解析与向量化上传（RAG知识库构建）
  parseDocument: (file: File, onProgress?: (percent: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/datasource/document/parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000, // 5 min for large docs
      onUploadProgress: (e: any) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
  },
  // 获取已上传文档列表
  getDocuments: () => request.get('/datasource/document/list'),
  // 删除文档
  deleteDocument: (id: number) => request.post(`/datasource/document/delete/${id}`),
  // 获取文档分块详情
  getDocumentChunks: (id: number) => request.get(`/datasource/document/chunks/${id}`),
  // 新增：根据数据源ID获取PDF文档信息和分块预览
  getDocumentByDatasource: (dsId: number) => request.get(`/datasource/document/byDatasource/${dsId}`),
  check: (data: any) => request.post('/datasource/check', data),
  check_by_id: (id: any) => request.get(`/datasource/check/${id}`),
  relationGet: (id: any) => request.post(`/table_relation/get/${id}`),
  relationSave: (dsId: any, data: any) => request.post(`/table_relation/save/${dsId}`, data),
  add: (data: any) => request.post('/datasource/add', data),
  list: () => request.get('/datasource/list'),
  update: (data: any) => request.post('/datasource/update', data),
  delete: (id: number) => request.post(`/datasource/delete/${id}`),
  getTables: (id: number) => request.post(`/datasource/getTables/${id}`),
  getTablesByConf: (data: any) => request.post('/datasource/getTablesByConf', data),
  getFields: (id: number, table_name: string) =>
    request.post(`/datasource/getFields/${id}/${table_name}`),
  execSql: (id: number | string, sql: string) =>
    request.post(`/datasource/execSql/${id}`, { sql: sql }),
  chooseTables: (id: number, data: any) => request.post(`/datasource/chooseTables/${id}`, data),
  tableList: (id: number) => request.post(`/datasource/tableList/${id}`),
  fieldList: (id: number) => request.post(`/datasource/fieldList/${id}`),
  edit: (data: any) => request.post('/datasource/editLocalComment', data),
  previewData: (id: number, data: any) => request.post(`/datasource/previewData/${id}`, data),
  saveTable: (data: any) => request.post('/datasource/editTable', data),
  saveField: (data: any) => request.post('/datasource/editField', data),
  getDs: (id: number) => request.post(`/datasource/get/${id}`),
  cancelRequests: () => request.cancelRequests(),
  getSchema: (data: any) => request.post('/datasource/getSchemaByConf', data),
}
