import { describe, expect, it } from 'vitest'

import { graphErrMsg, isEntityMissing } from '../frontend/src/api/graph'

/**
 * `src/api/graph.ts` 错误口径的单元测试。
 *
 * 这一层决定「用户看到哪句话」，也是前端唯一能区分 4000 / 4040 / 5000 的地方：
 * 判错一个分支，用户就会把"库里没有这首方"看成"图谱服务坏了"。
 *
 * 被测函数的输入是**拦截器包装后的 Error**（`request.ts` 把 HTTP status 挂到 `error.status`
 * 上、message 换成后端 `R.msg`），所以这里直接构造这种形状的 Error，不打真实网络。
 */

type HttpError = Error & { status?: number; response?: { status?: number; data?: { msg?: string } } }

/** 复刻 request.ts 的包装结果：message = 后端 msg，status 挂在属性上 */
function wrapped(status: number, msg?: string): HttpError {
  const err = new Error(msg ?? `Request failed with status code ${status}`) as HttpError
  err.status = status
  return err
}

/** 旧式 axios 错误（没有 status 属性，只在 response 里） */
function axiosLike(status: number, msg?: string): HttpError {
  const err = new Error(`Request failed with status code ${status}`) as HttpError
  err.response = { status, data: msg ? { msg } : {} }
  return err
}

describe('isEntityMissing — 只有「404 + 后端 msg」才算实体不存在', () => {
  it('4040（404 + 后端说明）判为实体不存在', () => {
    expect(isEntityMissing(wrapped(404, '图中找不到实体：桂枝（label=Formula）'))).toBe(true)
  })

  it('裸 404（路由没匹配上，没有后端 msg）不判为实体不存在', () => {
    expect(isEntityMissing(wrapped(404))).toBe(false)
    expect(isEntityMissing(axiosLike(404))).toBe(false)
  })

  it('400 / 500 一律不算实体不存在（避免把参数错误当成"查不到"重试）', () => {
    expect(isEntityMissing(wrapped(400, 'label 不支持'))).toBe(false)
    expect(isEntityMissing(wrapped(500, 'Neo4j 不可用'))).toBe(false)
  })

  it('不是 Error 的输入也不抛异常', () => {
    expect(isEntityMissing(undefined)).toBe(false)
    expect(isEntityMissing('boom')).toBe(false)
  })
})

describe('graphErrMsg — 错误压成可指导下一步的一句话', () => {
  it('4000：原样透传后端 msg（如方名重名需改用 ID）', () => {
    const msg = '方名「葛根汤」对应 2 首方，请改用 ID：f_128 / f_163'
    expect(graphErrMsg(wrapped(400, msg))).toBe(msg)
  })

  it('4040：原样透传后端 msg，而不是兜成"服务异常"', () => {
    const msg = '图中找不到实体：不存在的方（label=Formula）'
    expect(graphErrMsg(wrapped(404, msg))).toBe(msg)
  })

  it('裸 404：提示去查 BFF 路由，而不是让用户以为实体不存在', () => {
    const text = graphErrMsg(wrapped(404))
    expect(text).toContain('404')
    expect(text).toContain('bff')
  })

  it('5000：带后端说明时透传，没说明时提示查 svc-graph 与 Neo4j/PG', () => {
    expect(graphErrMsg(wrapped(500, 'Neo4j 连接失败'))).toBe('Neo4j 连接失败')
    expect(graphErrMsg(wrapped(500))).toContain('svc-graph')
  })

  it('501/405：提示检查网关放行（这两个码不代表实体问题）', () => {
    expect(graphErrMsg(wrapped(501, 'Not Implemented'))).toContain('501')
    expect(graphErrMsg(wrapped(405))).toContain('501/405')
  })

  it('没有状态码的普通错误：回落到 message', () => {
    expect(graphErrMsg(new Error('Network Error'))).toBe('Network Error')
  })

  it('完全取不到信息时给兜底文案，不返回空串', () => {
    expect(graphErrMsg(undefined)).toBe('请求失败')
    expect(graphErrMsg({})).toBe('请求失败')
  })

  it('兼容旧式 axios 错误（status 只在 response 里，msg 在 response.data 里）', () => {
    expect(graphErrMsg(axiosLike(400, 'hops 必须在 1~3'))).toBe('hops 必须在 1~3')
    expect(isEntityMissing(axiosLike(404, '图中找不到实体：x'))).toBe(true)
  })
})
