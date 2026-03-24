import { request } from '@/utils/request'

export const userApi = {
  // 分页查询用户列表
  pager: (
    pageNumber: number,
    pageSize: number,
    params?: { keyword?: string; status?: number; role?: string[] }
  ) => {
    // 处理role参数 - FastAPI需要多个同名参数而不是数组
    const queryParams: any = { ...params }
    if (params?.role && Array.isArray(params.role)) {
      delete queryParams.role
      const roleParams = params.role.map(r => `role=${r}`).join('&')
      const baseUrl = `/user/pager/${pageNumber}/${pageSize}`
      const otherParams = new URLSearchParams(queryParams).toString()
      const fullUrl = otherParams ? `${baseUrl}?${otherParams}&${roleParams}` : `${baseUrl}?${roleParams}`
      return request.get(fullUrl)
    }
    return request.get(`/user/pager/${pageNumber}/${pageSize}`, { params: queryParams })
  },
  // 创建用户
  add: (data: any) => request.post('/user', data),
  // 编辑用户
  edit: (data: any) => request.put('/user', data),
  // 删除单个用户 - 支持字符串ID
  delete: (id: number | string) => request.delete(`/user/${id}`),
  // 批量删除用户
  batchDelete: (ids: number[]) => request.delete('/user', { data: ids }),
  // 查询单个用户详情 - 支持字符串ID
  query: (id: number | string) => request.get(`/user/${id}`),
  // 修改语言
  language: (data: any) => request.put('/user/language', data),
  // 修改密码
  pwd: (data: any) => request.put('/user/pwd', data),
  // 重置密码（管理员）- 支持字符串ID
  resetPwd: (id: number | string) => request.patch(`/user/pwd/${id}`),
  // 修改用户状态 - 支持字符串ID
  changeStatus: (id: number | string, status: number) => request.patch('/user/status', { id, status }),
  // 获取默认密码
  getDefaultPwd: () => request.get('/user/defaultPwd'),
  // 获取可用工作空间列表
  ws_options: () => request.get('/workspace/options'),
  // 切换工作空间
  ws_change: (oid: number | string) => request.put(`/workspace/change/${oid}`),
}
