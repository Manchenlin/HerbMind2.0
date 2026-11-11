import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * 根目录 `test/` 的 vitest 配置。
 *
 * 为什么不带 `defineConfig`：这个文件在 `test/` 下，`test/` 里没有 node_modules，
 * `import { defineConfig } from 'vitest/config'` 会解析失败。裸对象同样能被 vitest 接受。
 *
 * 运行方式（必须在 frontend/ 下跑，依赖要从 frontend/node_modules 解析）：
 *   cd frontend && npx vitest run --config ../test/vitest.config.mts
 */
const here = path.dirname(fileURLToPath(import.meta.url))

export default {
  resolve: {
    alias: {
      '@': path.resolve(here, '../frontend/src')
    }
  },
  test: {
    root: path.resolve(here, '..'),
    include: ['test/**/*.test.ts'],
    environment: 'node'
  }
}
