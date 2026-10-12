<template>
  <div class="app">
    <header class="topbar">
      <b>HerbMind 本草心智</b>
      <nav>
        <RouterLink to="/library">典籍</RouterLink>
        <RouterLink to="/login">登录</RouterLink>
      </nav>
    </header>
    <main class="wrap">
      <RouterView />
    </main>
  </div>
</template>

<style>
body { margin: 0; font-family: 'Noto Sans SC', 'Microsoft YaHei', system-ui, sans-serif; color: #2c2c2a; }
.topbar { display: flex; gap: 20px; align-items: center; padding: 12px 24px; border-bottom: 1px solid #e5e5e2; }
.topbar nav { display: flex; gap: 12px; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 24px; }
</style>
