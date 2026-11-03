/* GUARDIÃO — HOME (interações) */

document.addEventListener('DOMContentLoaded', () => {
  iniciarTopicos();
  iniciarBusca();
  iniciarSimulador();
});

/*  Temas que abrem na própria página  */
function iniciarTopicos() {
  const topicos = document.querySelectorAll('.topico');

  topicos.forEach((topico) => {
    topico.addEventListener('toggle', () => {
      if (!topico.open) return;
      // mantém só um tema aberto por vez
      topicos.forEach((outro) => {
        if (outro !== topico) outro.open = false;
      });
    });
  });
}

/*Busca de temas  */
function iniciarBusca() {
  const campo = document.getElementById('busca');
  const topicos = document.querySelectorAll('.topico');
  const aviso = document.getElementById('busca-vazia');

  if (!campo) return;

  // remove acentos e deixa tudo minúsculo
  const normalizar = (texto) =>
    texto.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

  campo.addEventListener('input', () => {
    const termo = normalizar(campo.value).trim();
    let visiveis = 0;

    topicos.forEach((topico) => {
      const alvo = normalizar(topico.dataset.busca || topico.textContent);
      const mostrar = termo === '' || alvo.includes(termo);
      topico.hidden = !mostrar;
      if (mostrar) visiveis++;
    });

    aviso.hidden = visiveis !== 0;
  });
}

/* Simulador (quiz) */
function iniciarSimulador() {
  const opcoes = document.querySelectorAll('.opcao');
  const feedback = document.getElementById('quiz-feedback');
  const titulo = document.getElementById('quiz-feedback-titulo');
  const texto = document.getElementById('quiz-feedback-texto');

  if (!opcoes.length) return;

  opcoes.forEach((opcao) => {
    opcao.addEventListener('click', () => {
      // limpa a escolha anterior
      opcoes.forEach((o) => o.classList.remove('opcao--certa', 'opcao--errada'));

      const correta = opcao.dataset.correta === 'true';
      opcao.classList.add(correta ? 'opcao--certa' : 'opcao--errada');

      titulo.textContent = opcao.dataset.titulo;
      texto.textContent = opcao.dataset.texto;
      feedback.hidden = false;
    });
  });
}