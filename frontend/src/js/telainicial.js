(function () {
  var hero    = document.querySelector('.hero');
  var slides  = [].slice.call(document.querySelectorAll('.hero__slide'));
  var pontos  = document.getElementById('heroPontos');
  var atual   = 0;
  var timer;

  if (!hero || slides.length < 2) return;

  // cria uma bolinha para cada imagem
  slides.forEach(function (_, i) {
    var b = document.createElement('button');
    b.className = 'hero__ponto';
    b.setAttribute('aria-label', 'Ir para o slide ' + (i + 1));
    b.addEventListener('click', function () { ir(i); iniciar(); });
    pontos.appendChild(b);
  });

  // mostra o slide n
  function ir(n) {
    atual = n;
    slides.forEach(function (s, i) {
      s.classList.toggle('hero__slide--ativo', i === n);
    });
    [].forEach.call(pontos.children, function (b, i) {
      b.setAttribute('aria-current', i === n);
    });
    // só os slides com a classe --sombra recebem o degradê
    hero.setAttribute(
      'data-sombra',
      slides[n].classList.contains('hero__slide--sombra')
    );
  }

  // troca sozinho a cada 5 s (desligado para quem prefere menos movimento)
  function iniciar() {
    clearInterval(timer);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    timer = setInterval(function () { ir((atual + 1) % slides.length); }, 3000);
  }

  ir(0);
  iniciar();
})();