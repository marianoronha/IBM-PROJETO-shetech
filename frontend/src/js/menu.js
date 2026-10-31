// Recolher/expandir o menu lateral (páginas HTML). No React, isso está em components/Sidebar.tsx.
(function () {
  var side = document.querySelector('.gd-side');
  var btn = document.getElementById('gd-col');
  if (!side || !btn) return;
  if (window.matchMedia('(max-width:760px)').matches) side.classList.add('min');
  btn.addEventListener('click', function () {
    var min = side.classList.toggle('min');
    btn.setAttribute('aria-label', min ? 'Expandir menu' : 'Recolher menu');
  });
})();