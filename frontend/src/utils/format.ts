import type { Herb } from '@/api/catalog'

/** 剂量 + 单位：9 + g → 9g；9 + 枚 → 9 枚 */
export function doseText(h: Herb): string {
  if (h.dose === undefined || h.dose === null) {
    return h.name
  }
  const n = Number.isInteger(Number(h.dose)) ? String(h.dose) : String(h.dose)
  const unit = h.unit ?? ''
  return unit === '枚' || unit === '片' || unit === '支' ? `${n} ${unit}` : `${n}${unit}`
}

/** 君 / 臣 / 佐 / 使 → 样式类 */
export function roleClass(role?: string): string {
  switch (role) {
    case '君':
      return 'jun'
    case '臣':
      return 'chen'
    case '佐':
      return 'zuo'
    case '使':
      return 'shi'
    default:
      return ''
  }
}

/** 相关度 → badge 样式 */
export function scoreClass(score: number): string {
  if (score >= 0.8) return 'badge ok'
  if (score >= 0.5) return 'badge warn'
  return 'badge'
}

export function scoreText(score: number): string {
  return `相似度 ${score.toFixed(2)}`
}

/** 命中类型 → 中文 + 缩略字 */
export function typeLabel(type?: string): string {
  switch (type) {
    case 'formula':
      return '方剂'
    case 'case':
      return '医案'
    case 'quote':
      return '条文'
    default:
      return '内容'
  }
}

export function typeThumb(type?: string): string {
  switch (type) {
    case 'formula':
      return '方'
    case 'case':
      return '案'
    case 'quote':
      return '条'
    default:
      return '文'
  }
}

export interface CaseBlock {
  label: string
  content: string
}

const BLOCK_LABELS = [
  '现病史',
  '主诉',
  '病史',
  '查体',
  '辨证',
  '立法',
  '治法',
  '处方',
  '治疗效果',
  '效果',
  '按语',
  '提要',
  '问题解答',
  '问题'
]

/**
 * 把医案「案例原文」大段文本拆成栏目块。
 * 真实数据形如：
 *   徐某,男,23岁……
 *   现病史：发热恶寒……
 *   查体：……
 *   辨证：……
 * 没有识别到栏目时，整段作为一块返回。
 */
export function parseCaseText(text?: string): CaseBlock[] {
  if (!text) return []
  const normalized = text.replace(/\r\n/g, '\n')
  const pattern = new RegExp(`(${BLOCK_LABELS.join('|')})\\s*[：:]`, 'g')

  const marks: Array<{ label: string; start: number; end: number }> = []
  let m: RegExpExecArray | null
  while ((m = pattern.exec(normalized)) !== null) {
    marks.push({ label: m[1], start: m.index, end: m.index + m[0].length })
  }
  if (marks.length === 0) {
    return [{ label: '案例原文', content: normalized.trim() }]
  }

  const blocks: CaseBlock[] = []
  const head = normalized.slice(0, marks[0].start).trim()
  if (head) {
    blocks.push({ label: '病例', content: head })
  }
  marks.forEach((mk, i) => {
    const stop = i + 1 < marks.length ? marks[i + 1].start : normalized.length
    const content = normalized.slice(mk.end, stop).trim()
    if (content) {
      blocks.push({ label: mk.label, content })
    }
  })
  return blocks
}

/** 先思后看：辨证 / 治法 / 处方 / 效果 属于「答案区」 */
export function isAnswerBlock(label: string): boolean {
  return ['辨证', '立法', '治法', '处方', '治疗效果', '效果'].includes(label)
}

/** 数字千分位 */
export function num(n?: number): string {
  return n === undefined || n === null ? '—' : n.toLocaleString('zh-CN')
}

/** 简单高亮：把命中的词包成 <mark>（返回 HTML，调用方用 v-html） */
export function highlight(text: string | undefined, keywords: string[]): string {
  if (!text) return ''
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const words = keywords.filter((k) => k && k.length >= 2).sort((a, b) => b.length - a.length)
  if (words.length === 0) return escaped
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g')
  return escaped.replace(re, '<mark style="background:#FBF3DF;color:#8A6D3B;border-radius:3px;padding:0 2px">$1</mark>')
}
