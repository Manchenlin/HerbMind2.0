import { computed, ref } from 'vue'
import { getBooks, type Book } from '@/api/catalog'

/**
 * 书单的唯一来源（模块级单例，全站共享一次请求）。
 *
 * 为什么要有它：语料合并后库里只剩一本《中医经典方证案例研究》，后端 /biz/catalog/books
 * 早就只返回一本了，但页头语料切换器、典籍页 tab、检索页书名筛选、导出范围里各自硬编码着
 * 「伤寒论 / 温病学 / 金匮要略」三本，用户看到的永远是旧书名。
 * 统一走这个 composable，以后再加语料只改后端数据，前端不用再改。
 */
const books = ref<Book[]>([])
const loading = ref(false)
const error = ref('')
let inflight: Promise<void> | null = null

async function load(force = false): Promise<void> {
  if (!force && books.value.length) return
  if (inflight) return inflight
  loading.value = true
  error.value = ''
  inflight = (async () => {
    try {
      books.value = (await getBooks()) ?? []
    } catch (e) {
      error.value = e instanceof Error ? e.message : '语料列表加载失败'
    } finally {
      loading.value = false
      inflight = null
    }
  })()
  return inflight
}

export function useBooks() {
  /** 只有一本书时，页头的"切换语料"没有意义，调用方应据此隐藏 */
  const hasMultiple = computed(() => books.value.length > 1)
  const defaultBookId = computed(() => books.value[0]?.id ?? '')
  const titleOf = (id: string) => books.value.find((b) => b.id === id)?.title ?? id

  return { books, loading, error, hasMultiple, defaultBookId, titleOf, loadBooks: load }
}
