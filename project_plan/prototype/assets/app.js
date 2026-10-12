/* HerbMind 原型 · 交互脚本（页面转场 + 微交互） */
(function () {
  var NAV = [
    { href: 'index.html',   label: '首页' },
    { href: 'shelf.html',   label: '书架' },
    { href: 'library.html', label: '典籍' },
    { href: 'search.html',  label: '检索' },
    { href: 'train.html',   label: '练习' },
    { href: 'graph.html',   label: '图谱' },
    { href: 'ask.html',     label: '智能问答' },
    { href: 'me.html',      label: '我的' }
  ];
  var here = (location.pathname.split('/').pop() || 'index.html');

  /* ---- 顶栏 ---- */
  function buildTopbar() {
    var el = document.querySelector('.topbar');
    if (!el) return;
    var nav = NAV.map(function (n) {
      var active = (n.href === here) || (here === '' && n.href === 'index.html');
      return '<a href="' + n.href + '" class="' + (active ? 'active' : '') + '">' + n.label + '</a>';
    }).join('');
    el.innerHTML =
      '<div class="inner">' +
        '<a class="brand" href="index.html"><span class="logo">H</span>HerbMind 本草心智</a>' +
        '<nav class="nav">' + nav + '</nav>' +
        '<span class="spacer"></span>' +
        bookSelect() +
        '<a class="btn primary sm" href="login.html">登录 / 注册</a>' +
      '</div>';
  }

  /* ---- 语料切换器（可插拔书籍） ---- */
  function bookSelect() {
    var books = (window.MOCK && MOCK.books) || [];
    if (!books.length) return '';
    var opts = books.map(function (b) {
      var mark = b.current ? '★ ' : '';
      var st = b.status.indexOf('规划') >= 0 ? '（规划中）' : '';
      return '<option value="' + b.id + '"' + (b.current ? ' selected' : '') + '>' + mark + b.title + st + '</option>';
    }).join('');
    return '<select class="booksel" title="切换语料（插拔式）" onchange="switchBook(this.value)">' + opts + '</select>';
  }
  window.switchBook = function (id) {
    var books = (window.MOCK && MOCK.books) || [];
    var b = books.filter(function (x) { return x.id === id; })[0];
    if (!b) return;
    if (b.status.indexOf('规划') >= 0) { toast('「' + b.title + '」规划中，敬请期待'); return; }
    toast('已切换语料：' + b.title);
  };

  /* ---- 页脚 ---- */
  function buildFooter() {
    var f = document.querySelector('footer');
    if (!f) return;
    f.innerHTML = 'HerbMind 重构原型（M0）· 现代极简 · ' +
      '<a href="me.html">我的</a> · <a href="favorites.html">收藏笔记</a> · ' +
      '<a href="admin.html">治理后台</a> · <a href="../00_README_总览.md">计划文档</a>';
  }

  /* ---- 进度条 ---- */
  var prog = document.getElementById('progress');
  function startProgress() { if (!prog) return; prog.classList.add('on'); prog.style.width = '12%';
    setTimeout(function(){ prog.style.width = '68%'; }, 120); }
  function endProgress() { if (!prog) return; prog.style.width = '100%';
    setTimeout(function(){ prog.classList.remove('on'); prog.style.width = '0'; }, 250); }

  /* ---- 页面进入动画 ---- */
  function enter() {
    requestAnimationFrame(function () {
      document.body.classList.add('loaded');
      document.body.classList.remove('leaving');
      endProgress();
    });
  }

  /* ---- 拦截站内链接，做离场转场 ---- */
  function hookLinks() {
    document.addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (!a) return;
      var href = a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('http') || href.startsWith('mailto')) return;
      if (a.target === '_blank') return;
      e.preventDefault();
      startProgress();
      document.body.classList.add('leaving');
      setTimeout(function () { location.href = href; }, 180);
    });
  }

  /* ---- 计数滚动 ---- */
  function countUp() {
    document.querySelectorAll('[data-count]').forEach(function (el) {
      var target = parseFloat(el.getAttribute('data-count'));
      var dur = 800, t0 = null;
      function step(ts) {
        if (!t0) t0 = ts;
        var p = Math.min((ts - t0) / dur, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = (target % 1 === 0 ? Math.round(target * eased) : (target * eased).toFixed(1));
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  /* ---- 列表 stagger ---- */
  function stagger() {
    document.querySelectorAll('.stagger').forEach(function (box) {
      Array.prototype.forEach.call(box.children, function (c, i) {
        c.style.animationDelay = (i * 40) + 'ms';
      });
    });
  }

  /* ---- Toast ---- */
  window.toast = function (msg) {
    var t = document.createElement('div');
    t.className = 'toast'; t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('show'); });
    setTimeout(function () { t.classList.remove('show'); setTimeout(function(){ t.remove(); }, 240); }, 1800);
  };

  /* ---- 抽屉 ---- */
  window.openDrawer = function (html) {
    var d = document.querySelector('.drawer');
    if (!d) { d = document.createElement('aside'); d.className = 'drawer';
      var ov = document.createElement('div'); ov.className = 'overlay'; document.body.appendChild(ov);
      document.body.appendChild(d);
      ov.addEventListener('click', window.closeDrawer);
    }
    d.innerHTML = html;
    document.querySelector('.overlay').classList.add('open');
    requestAnimationFrame(function () { d.classList.add('open'); });
  };
  window.closeDrawer = function () {
    var d = document.querySelector('.drawer'); if (d) d.classList.remove('open');
    var ov = document.querySelector('.overlay'); if (ov) ov.classList.remove('open');
  };

  /* ---- 揭晓（先思后看） ---- */
  window.revealAnswer = function () {
    document.querySelectorAll('.reveal').forEach(function (r) { r.classList.add('show'); });
    var btn = document.getElementById('revealBtn'); if (btn) { btn.textContent = '已揭晓原著答案 ✓'; btn.disabled = true; }
    toast('已揭晓原著答案');
  };

  /* ---- Pill tabs ---- */
  function tabs() {
    document.querySelectorAll('.pill-tabs').forEach(function (box) {
      box.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        box.querySelectorAll('button').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        var tgt = b.getAttribute('data-tab');
        if (tgt) document.querySelectorAll('[data-panel]').forEach(function (p) {
          p.style.display = (p.getAttribute('data-panel') === tgt) ? '' : 'none';
        });
      });
    });
  }

  /* ---- 收藏 ---- */
  window.fav = function (el) {
    el.classList.toggle('active');
    toast(el.classList.contains('active') ? '已加入我的方证库 ★' : '已取消收藏');
  };

  /* ---- 启动 ---- */
  document.addEventListener('DOMContentLoaded', function () {
    startProgress();
    buildTopbar();
    buildFooter();
    hookLinks();
    enter();
    setTimeout(function () { countUp(); stagger(); }, 60);
    tabs();
  });
})();
