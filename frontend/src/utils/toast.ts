/**
 * 轻量 toast —— 与原型 assets/app.js 的 toast 行为一致（复用 theme.css 的 .toast 样式）。
 */
export function toast(msg: string) {
  const t = document.createElement('div')
  t.className = 'toast'
  t.textContent = msg
  document.body.appendChild(t)
  requestAnimationFrame(() => t.classList.add('show'))
  setTimeout(() => {
    t.classList.remove('show')
    setTimeout(() => t.remove(), 240)
  }, 1800)
}
