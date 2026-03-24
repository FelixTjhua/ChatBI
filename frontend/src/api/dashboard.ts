import { request } from '@/utils/request'

export const dashboardApi = {
  list_resource: (params: any) => request.post('/dashboard/list_resource', params),
  load_resource: (params: any) => request.post('/dashboard/load_resource', params),
  create_resource: (params: any) => request.post('/dashboard/create_resource', params),
  update_resource: (params: any) => request.post('/dashboard/update_resource', params),
  create_canvas: (params: any) => request.post('/dashboard/create_canvas', params),
  update_canvas: (params: any) => request.post('/dashboard/update_canvas', params),
  check_name: (params: any) => request.post('/dashboard/check_name', params),
  delete_resource: (params: any) =>
    request.delete(`/dashboard/delete_resource/${params.id}`, params),
  move_resource: (params: any) => request.post('/dashboard/move_resource', params),
  refresh_chart_data: (recordId: number) => request.get(`/chat/record/${recordId}/data`),
  // New APIs
  quick_save: (params: { chart_data: string; dashboard_id?: string }) =>
    request.post('/dashboard/quick_save', params),
  generate_summary: (dashboard_id: string) =>
    request.post('/dashboard/generate_summary', { dashboard_id }),
  refresh_all_charts: (dashboard_id: string) =>
    request.post('/dashboard/refresh_all_charts', { dashboard_id }),
  export_excel: (dashboard_id: string) =>
    request.get(`/dashboard/${dashboard_id}/excel/export`, {
      responseType: 'blob',
      requestOptions: { customError: true },
    }),
}
