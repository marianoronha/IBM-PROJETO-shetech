/* perfil.js — interatividade + integração com a API de perfil */
(function () {
  'use strict';

  /* ── Constante de API ───────────────────────────────────────────────────── */
  const API_BASE = '/api/auth';

  /* ── Token e dados locais ─────────────────────────────────────────────── */
  function getToken() { return localStorage.getItem('gd_token'); }
  function getUser()  {
    try { return JSON.parse(localStorage.getItem('gd_user') || '{}'); }
    catch { return {}; }
  }
  function saveUser(u) { localStorage.setItem('gd_user', JSON.stringify(u)); }
  async function clearSession() {
    const token = getToken();
    if (token) {
      // Notifica o backend (best-effort — não bloqueia o logout local)
      fetch(API_BASE + '/logout', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token },
      }).catch(() => {});
    }
    localStorage.removeItem('gd_token');
    localStorage.removeItem('gd_user');
    window.location.href = 'login.html';
  }

  /* ── Chamadas à API ───────────────────────────────────────────────────── */
  async function apiGet(path) {
    const resp = await fetch(API_BASE + path, {
      headers: { 'Authorization': 'Bearer ' + getToken() },
    });
    if (resp.status === 401) { clearSession(); }
    if (!resp.ok) throw new Error('Erro ' + resp.status);
    return resp.json();
  }

  async function apiPatch(path, body) {
    const resp = await fetch(API_BASE + path, {
      method: 'PATCH',
      headers: {
        'Authorization': 'Bearer ' + getToken(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (resp.status === 401) { clearSession(); }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data?.detail?.error || 'Erro ao salvar.');
    }
    return resp.json();
  }

  async function apiPost(path, body) {
    const resp = await fetch(API_BASE + path, {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + getToken(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (resp.status === 401) { clearSession(); }
    if (resp.status === 204) return null;
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data?.detail?.error || 'Erro ao salvar.');
    }
    return resp.json();
  }

  async function apiDelete(path) {
    const resp = await fetch(API_BASE + path, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + getToken() },
    });
    if (resp.status === 401) { clearSession(); }
    if (resp.status === 204) return;
    if (!resp.ok) throw new Error('Erro ao excluir.');
  }

  /* ── Redireciona para login se não autenticado ───────────────────────── */
  if (!getToken()) { clearSession(); return; }

  /* ── Carrega e exibe dados do perfil ─────────────────────────────────── */
  async function carregarPerfil() {
    try {
      const user = await apiGet('/me');
      saveUser(user);

      /* Preenche campos do formulário */
      const nomeEl = document.getElementById('nome');
      const emailEl = document.getElementById('email');
      const telEl = document.getElementById('telefone');
      if (nomeEl)  nomeEl.value  = user.nome  || '';
      if (emailEl) emailEl.value = user.email || '';
      if (telEl)   telEl.value   = user.telefone || '';

      /* Preenche hero */
      const nameEl    = document.getElementById('pf-name');
      const emailHero = document.getElementById('pf-email');
      const initialsEl = document.getElementById('pf-initials');
      if (nameEl)    nameEl.textContent    = user.nome  || 'Usuário';
      if (emailHero) emailHero.textContent = user.email || '';
      if (initialsEl) {
        const parts = (user.nome || 'US').split(' ');
        initialsEl.textContent = (
          (parts[0]?.[0] || '') + (parts[parts.length - 1]?.[0] || '')
        ).toUpperCase() || 'US';
      }

      /* Dias ativo */
      const diasEl = document.getElementById('stat-dias');
      if (diasEl && user.criado_em) {
        const days = Math.floor((Date.now() - new Date(user.criado_em).getTime()) / 86400000);
        animCount(diasEl, Math.max(0, days), 900);
      }
    } catch (err) {
      /* Silencioso — usa dados do localStorage como fallback */
      const cached = getUser();
      const nomeEl  = document.getElementById('nome');
      const emailEl = document.getElementById('email');
      if (nomeEl && cached.nome)   nomeEl.value  = cached.nome;
      if (emailEl && cached.email) emailEl.value = cached.email;
    }
  }

  carregarPerfil();

  /* ── Tema global (persiste em localStorage, aplica em <html>) ─────────── */
  const THEME_KEY = 'gd-theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    document.querySelectorAll('#theme-segmented .pf-seg').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === theme);
    });
  }

  const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
  applyTheme(savedTheme);

  const themeGroup = document.getElementById('theme-segmented');
  themeGroup && themeGroup.querySelectorAll('.pf-seg').forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });

  /* ── Editar dados pessoais ─────────────────────────────────────────────── */
  const btnEdit   = document.getElementById('btn-edit-dados');
  const btnCancel = document.getElementById('btn-cancel-dados');
  const btnSave   = document.getElementById('btn-save-dados');
  const formDados = document.getElementById('form-dados');

  function setFormEditing(editing) {
    formDados.querySelectorAll('input').forEach(inp => { inp.disabled = !editing; });
    btnEdit.hidden   = editing;
    btnCancel.hidden = !editing;
    btnSave.hidden   = !editing;
    if (editing) formDados.querySelector('input').focus();
  }

  btnEdit && btnEdit.addEventListener('click', () => setFormEditing(true));
  btnCancel && btnCancel.addEventListener('click', () => {
    /* Restaura valores da sessão */
    const cached = getUser();
    const nomeEl  = document.getElementById('nome');
    const telEl   = document.getElementById('telefone');
    if (nomeEl && cached.nome)     nomeEl.value  = cached.nome;
    if (telEl  && cached.telefone) telEl.value   = cached.telefone;
    setFormEditing(false);
  });

  formDados && formDados.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nome     = document.getElementById('nome').value.trim();
    const telefone = document.getElementById('telefone').value.trim();
    btnSave.disabled = true;
    btnSave.textContent = 'Salvando…';
    try {
      const updated = await apiPatch('/me', { nome, telefone });
      saveUser(updated);
      /* Atualiza hero */
      const nameEl = document.getElementById('pf-name');
      if (nameEl) nameEl.textContent = updated.nome || nome;
      setFormEditing(false);
      mostrarFeedback('Dados salvos com sucesso.', 'ok');
    } catch (err) {
      mostrarFeedback(err.message, 'erro');
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = 'Salvar alterações';
    }
  });

  /* ── Força da senha ──────────────────────────────────────────────────── */
  const novaSenha   = document.getElementById('nova-senha');
  const strengthBox = document.getElementById('pass-strength');
  const bars        = document.querySelectorAll('#pass-strength .pf-strength__bars span');
  const strengthLbl = document.getElementById('pass-strength-label');
  const levels      = ['', 'Fraca', 'Razoável', 'Boa', 'Forte'];
  const classes     = ['', 'weak', 'fair', 'good', 'strong'];

  function scorePassword(pw) {
    let s = 0;
    if (pw.length >= 8)          s++;
    if (/[A-Z]/.test(pw))        s++;
    if (/[0-9]/.test(pw))        s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;
    return s;
  }

  function resetStrength() {
    bars.forEach(b => { b.className = ''; });
    if (strengthLbl) strengthLbl.textContent = '—';
    if (strengthBox) strengthBox.hidden = true;
  }

  novaSenha && novaSenha.addEventListener('input', () => {
    const pw = novaSenha.value;
    if (!pw) { resetStrength(); return; }
    strengthBox.hidden = false;
    const score = scorePassword(pw);
    bars.forEach((b, i) => { b.className = i < score ? classes[score] : ''; });
    if (strengthLbl) strengthLbl.textContent = levels[score] || '—';
  });

  /* ── Painel de alterar senha ─────────────────────────────────────────── */
  const btnChangePass = document.getElementById('btn-change-pass');
  const btnCancelPass = document.getElementById('btn-cancel-pass');
  const passPanel     = document.getElementById('pass-panel');
  const formSenha     = document.getElementById('form-senha');

  btnChangePass && btnChangePass.addEventListener('click', () => {
    passPanel.hidden = false;
    passPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  function closePassPanel() {
    if (passPanel) passPanel.hidden = true;
    formSenha && formSenha.reset();
    resetStrength();
  }

  btnCancelPass && btnCancelPass.addEventListener('click', closePassPanel);

  formSenha && formSenha.addEventListener('submit', async (e) => {
    e.preventDefault();
    const senhaAtual  = document.getElementById('senha-atual').value;
    const novaSenhaV  = document.getElementById('nova-senha').value;
    const confirmaSenha = document.getElementById('confirma-senha').value;

    if (novaSenhaV !== confirmaSenha) {
      mostrarFeedback('As novas senhas não coincidem.', 'erro');
      return;
    }

    const submitBtn = formSenha.querySelector('[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Salvando…';

    try {
      await apiPost('/me/change-password', {
        senha_atual: senhaAtual,
        nova_senha:  novaSenhaV,
      });
      closePassPanel();
      mostrarFeedback('Senha alterada com sucesso.', 'ok');
    } catch (err) {
      mostrarFeedback(err.message, 'erro');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Salvar senha';
    }
  });

  /* ── Mostrar/ocultar senha ───────────────────────────────────────────── */
  document.querySelectorAll('.pf-eye').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.closest('.pf-pass-wrap').querySelector('input');
      if (!input) return;
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      btn.setAttribute('aria-label', showing ? 'Mostrar senha' : 'Ocultar senha');
    });
  });

  /* ── Exclusão de conta ───────────────────────────────────────────────── */
  const btnExcluir = document.querySelector('.pf-btn--danger');
  btnExcluir && btnExcluir.addEventListener('click', async () => {
    const confirmado = window.confirm(
      'Tem certeza que deseja excluir sua conta?\nEsta ação é permanente e não pode ser desfeita.'
    );
    if (!confirmado) return;
    btnExcluir.disabled = true;
    btnExcluir.textContent = 'Excluindo…';
    try {
      await apiDelete('/me');
      clearSession();
    } catch (err) {
      mostrarFeedback('Erro ao excluir a conta. Tente novamente.', 'erro');
      btnExcluir.disabled = false;
      btnExcluir.textContent = 'Excluir conta';
    }
  });

  /* ── Logout ──────────────────────────────────────────────────────────── */
  const btnSair = document.querySelector('.gd-out');
  btnSair && btnSair.addEventListener('click', (e) => {
    e.preventDefault();
    clearSession();
  });

  /* ── Stats animadas ──────────────────────────────────────────────────── */
  function animCount(el, target, dur) {
    const start = performance.now();
    function step(now) {
      const p = Math.min((now - start) / dur, 1);
      el.textContent = Math.round(p * target);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* Análises, bloqueios, simulações mantêm valores default até que
     um backend de histórico seja implementado. Dias ativo vem da API. */
  const staticStats = {
    'stat-analises':  0,
    'stat-bloqueios': 0,
    'stat-simulacoes': 0,
  };
  Object.entries(staticStats).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) animCount(el, val, 900);
  });

  /* ── Feedback visual inline ──────────────────────────────────────────── */
  function mostrarFeedback(msg, tipo) {
    let el = document.getElementById('pf-feedback');
    if (!el) {
      el = document.createElement('p');
      el.id = 'pf-feedback';
      el.style.cssText = 'font-size:.9rem;margin:.75rem 0;padding:.6rem 1rem;border-radius:6px;text-align:center;';
      const mainContent = document.querySelector('.pf-main');
      if (mainContent) mainContent.prepend(el);
    }
    el.textContent = msg;
    el.style.color      = tipo === 'ok' ? '#1a7a3c' : '#c0392b';
    el.style.background = tipo === 'ok' ? '#e6f9ee' : '#fdf0f0';
    el.style.border     = tipo === 'ok' ? '1px solid #a3d9b1' : '1px solid #f5b7b1';
    clearTimeout(el._timeout);
    el._timeout = setTimeout(() => { el.textContent = ''; el.style.display = 'none'; }, 5000);
    el.style.display = 'block';
  }

})();
