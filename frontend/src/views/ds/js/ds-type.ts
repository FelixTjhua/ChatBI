import excel from '@/assets/datasource/icon_excel.svg?url'
import csv from '@/assets/datasource/icon_csv.svg?url'
import pdf from '@/assets/datasource/icon_pdf.svg?url'
import pg from '@/assets/datasource/icon_PostgreSQL.svg?url'
import mysql from '@/assets/datasource/icon_mysql.svg?url'
import oracle from '@/assets/datasource/icon_oracle.svg?url'
import { i18n } from '@/i18n'

const t = i18n.global.t
// ChatBI 支持 PostgreSQL、MySQL、Oracle、Excel、CSV、PDF
export const dsType = [
  { label: 'Excel', value: 'excel' },
  { label: 'CSV', value: 'csv' },
  { label: 'PDF', value: 'pdf' },
  { label: 'PostgreSQL', value: 'pg' },
  { label: 'MySQL', value: 'mysql' },
  { label: 'Oracle', value: 'oracle' },
]

export const dsTypeWithImg = [
  { name: 'Excel', type: 'excel', img: excel },
  { name: 'CSV', type: 'csv', img: csv },
  { name: 'PDF', type: 'pdf', img: pdf },
  { name: 'PostgreSQL', type: 'pg', img: pg },
  { name: 'MySQL', type: 'mysql', img: mysql },
  { name: 'Oracle', type: 'oracle', img: oracle },
]

// 文件类型（Excel/CSV/PDF）
export const isFileType = (type: string) => type === 'excel' || type === 'csv' || type === 'pdf'

// 根据后端type获取图标
export const getDsIcon = (type: string) => {
  return (dsTypeWithImg.find((ele) => type === ele.type) || {}).img
}

// 后端 get_schema() 已支持全部3种数据库类型的 Schema 查询
export const haveSchema = ['pg', 'oracle', 'mysql']
