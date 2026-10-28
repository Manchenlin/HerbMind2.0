import request from './request'

/** 用户公开信息（不含任何密码字段） */
export interface UserDto {
  id: string
  username: string
  role: string
  nickname: string
  avatar: string
}

export interface LoginResp {
  token: string
  user: UserDto
}

/** 登录（域2：POST /api/biz/user/login） */
export function login(username: string, password: string) {
  return request.post<unknown, LoginResp>('/biz/user/login', { username, password })
}

/** 注册（域2：POST /api/biz/user/register） */
export function register(username: string, password: string, nickname?: string) {
  return request.post<unknown, LoginResp>('/biz/user/register', { username, password, nickname })
}

/** 当前用户（需已登录，网关按 token 注入 X-User-Id） */
export function me() {
  return request.get<unknown, UserDto>('/biz/user/me')
}
