import { request } from '@/utils/request'

export const analyticsApi = {
  getOverview: () => request.get('/analytics/overview'),
  getDatasourceStats: () => request.get('/analytics/datasource_stats'),
  getChatStats: () => request.get('/analytics/chat_stats'),
  getRecentConversations: () => request.get('/analytics/recent_conversations'),
}
