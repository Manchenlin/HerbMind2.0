import request from './request'

export interface BookTreeNode {
  id: string
  title: string
  /** chapter / section / category —— 注意是 camelCase，不是 node_type */
  nodeType: string
  children: BookTreeNode[]
}

/** 典籍目录树（域1：/api/biz/library/tree） */
export function getLibraryTree(bookId = 'bk_1') {
  return request.get<unknown, BookTreeNode[]>('/biz/library/tree', { params: { bookId } })
}
