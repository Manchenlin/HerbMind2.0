/**
 * 出处标签：把章标题里的书名转成"出处"表述。
 *
 * 为什么：这本语料是《中医经典方证案例研究》，章标题形如「第二章《伤寒论》方证案例研究」。
 * 直接把章标题甩出来，用户会以为站里还有《伤寒论》《温病学》《金匮要略》三本独立的书。
 * 统一渲染成「出自《伤寒论》第二章」，语义是"本章引的是这部经典的原文"。
 */
const CHAPTER_BOOK = /^第([一二三四五六七八九十百]+)章\s*[《〈]?(.+?)[》〉]/

export function classicLabel(chapter?: string): string {
  if (!chapter) return ''
  const m = chapter.match(CHAPTER_BOOK)
  return m ? `出自《${m[2]}》第${m[1]}章` : chapter
}
