/* perfil.js — interatividade da página de perfil */
(function () {
  'use strict';

  /*  Tema global (persiste em localStorage, aplica em <html>) */
  const THEME_KEY = 'gd-theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    // sync segmented buttons on this page
    document.querySelectorAll('#theme-segmented .pf-seg').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === theme);
    });
  }

  // Restore saved theme on load
  const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
  applyTheme(savedTheme);

  // Segmented control on perfil page
  const themeGroup = document.getElementById('theme-segmented');
  themeGroup && themeGroup.querySelectorAll('.pf-seg').forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });

  /* Editar dados pessoais  */
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
    formDados.reset();            // volta aos valores originais
    setFormEditing(false);
  });
  formDados && formDados.addEventListener('submit', e => {
    e.preventDefault();
    setFormEditing(false);
  });

  /* Força da senha */
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

  /* Painel de alterar senha  */
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
  formSenha && formSenha.addEventListener('submit', e => {
    e.preventDefault();
    closePassPanel();
  });

  /*  Mostrar/ocultar senha */
  document.querySelectorAll('.pf-eye').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.closest('.pf-pass-wrap').querySelector('input');
      if (!input) return;
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      btn.setAttribute('aria-label', showing ? 'Mostrar senha' : 'Ocultar senha');
    });
  });

  /* Stats animadas */
  function animCount(el, target, dur) {
    const start = performance.now();
    function step(now) {
      const p = Math.min((now - start) / dur, 1);
      el.textContent = Math.round(p * target);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  const statData = {
    'stat-analises':   12,
    'stat-bloqueios':   3,
    'stat-simulacoes':  5,
    'stat-dias':        7,
  };

  Object.entries(statData).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) animCount(el, val, 900);
  });

})();