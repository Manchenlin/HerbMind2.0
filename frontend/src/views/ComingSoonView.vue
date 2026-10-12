<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / {{ title }}</div>

  <div class="card" style="margin-top:12px">
    <h1 class="serif" style="margin-bottom:6px">{{ title }}</h1>
    <p class="muted">此页面尚未实现。</p>

    <div class="hr"></div>

    <div class="grid cols-2" style="margin-top:6px">
      <div>
        <div class="muted" style="font-size:12.5px;margin-bottom:4px">负责人</div>
        <div><b>{{ owner }}</b>（见 <span class="mono">15_团队分工与接口协作.md</span>）</div>
      </div>
      <div>
        <div class="muted" style="font-size:12.5px;margin-bottom:4px">照这个原型做</div>
        <div><span class="mono">project_plan/prototype/{{ proto }}</span></div>
      </div>
    </div>

    <div class="hr"></div>

    <p class="muted" style="font-size:13px">
      实现要求：① 复用 <span class="mono">src/styles/theme.css</span> 里的样式类（不要另起一套颜色/间距）；
      ② 数据来自 <span class="mono">/api/biz/**</span>（经 <span class="mono">src/api/request.ts</span>）；
      ③ 字段名用 camelCase（如 <span class="mono">nodeType</span>）。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => (route.meta.title as string) ?? '页面')
const owner = computed(() => (route.meta.owner as string) ?? '待分配')
const proto = computed(() => (route.meta.proto as string) ?? '—')
</script>
