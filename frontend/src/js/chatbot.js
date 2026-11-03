
/* CHATBOT GUARDIÃO */

(function () {
  "use strict";

  if (window.__gdbotLoaded) return;
  window.__gdbotLoaded = true;

  // CONFIGURAÇÃO
  const CONFIG = {
    nome: "Guardião",
    saudacao:
      "Olá! 👋 Eu sou o Guardião, seu assistente virtual. " +
      "Posso responder perguntas sobre golpes, finanças, " +
      "tecnologia, estudos e muitos outros assuntos. " +
      "Como posso ajudar você hoje?",
    endpoint: "/api/chat",
    limiteHistorico: 30
  };

  const script =
    document.currentScript ||
    document.querySelector('script[src*="chatbot.js"]');

  const scriptSrc = script?.src || "";
  const base = scriptSrc.replace(/js\/chatbot\.js.*$/, "");

  const mascote =
    script?.getAttribute("data-mascote") ||
    (base ? base + "img/Amascote.png" : "");

  const SHIELD = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2 4 5v6c0 5 3.4 9.4 8 11
           4.6-1.6 8-6 8-11V5l-8-3Z"
        fill="#fcd116"
      />
      <path
        d="m8.5 12 2.6 2.6L16 9.7"
        fill="none"
        stroke="#002a63"
        stroke-width="2.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  `;

  // PERGUNTAS SUGERIDAS
  const perguntas = [
    "Como identificar um golpe?",
    "Como me proteger na internet?",
    "O que fazer se caí em um golpe?",
    "O que é inteligência artificial?",
    "Como organizar minhas finanças?",
    "Como estudar melhor?",
    "O que é phishing?",
    "Como saber se um link é falso?",
    "O que são juros?",
    "Como criar uma senha segura?"
  ];

  // ESTADO DA CONVERSA
  const STORAGE_KEY = "guardiao-chat-geral";

  let state = {
    open: false,
    msgs: []
  };

  try {
    const salvo = JSON.parse(
      sessionStorage.getItem(STORAGE_KEY)
    );

    if (
      salvo &&
      Array.isArray(salvo.msgs)
    ) {
      state = salvo;
    }
  } catch (erro) {
    console.warn("Histórico não disponível.");
  }

  function salvar() {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(state)
      );
    } catch (erro) {
      console.warn("Não foi possível salvar a conversa.");
    }
  }

  // ELEMENTOS
  let root;
  let launcher;
  let panel;
  let log;
  let form;
  let input;
  let sendButton;

  let enviando = false;

  function el(tag, classe = "", texto = null) {
    const elemento = document.createElement(tag);

    if (classe) elemento.className = classe;

    if (texto !== null) {
      elemento.textContent = texto;
    }

    return elemento;
  }

  function hora() {
    return new Date().toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  // CSS EXISTENTE
  function injetarCSS() {
    if (
      !base ||
      document.querySelector(
        'link[href*="chatbot.css"]'
      )
    ) {
      return;
    }

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = base + "styles/chatbot.css";

    document.head.appendChild(link);
  }

  // AVATAR
  function avatar(classe) {
    const elemento = el("span", classe);

    if (!mascote) {
      elemento.innerHTML = SHIELD;
      return elemento;
    }

    const imagem = document.createElement("img");
    imagem.src = mascote;
    imagem.alt = "";

    imagem.addEventListener("error", function () {
      elemento.innerHTML = SHIELD;
    });

    elemento.appendChild(imagem);

    return elemento;
  }

  // MONTAGEM DO CHAT
  function montar() {
    injetarCSS();

    root = el("div", "gdbot");

    root.innerHTML = `
      <button
        type="button"
        class="gdbot-launcher"
        aria-label="Abrir chatbot"
        aria-expanded="false"
        aria-controls="gdbot-panel"
      >
        <svg
          class="gdbot-ico-chat"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M4 5h16v11H9l-5 4z"/>
        </svg>

        <svg
          class="gdbot-ico-x"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M6 6l12 12M18 6 6 18"/>
        </svg>
      </button>

      <section
        class="gdbot-panel"
        id="gdbot-panel"
        role="dialog"
        aria-label="Chat com Guardião"
        hidden
      >
        <header class="gdbot-head">
          <div class="gdbot-title">
            <strong class="gdbot-name">
              Guardião
            </strong>

            <span class="gdbot-status">
              <i></i> Assistente virtual
            </span>
          </div>

          <button
            type="button"
            class="gdbot-close"
            aria-label="Fechar chat"
          >
            <svg viewBox="0 0 24 24">
              <path d="M6 6l12 12M18 6 6 18"/>
            </svg>
          </button>
        </header>

        <div
          class="gdbot-log"
          role="log"
          aria-live="polite"
          tabindex="0"
        ></div>

        <form
          class="gdbot-form"
          autocomplete="off"
        >
          <input
            class="gdbot-input"
            type="text"
            maxlength="2000"
            placeholder="Pergunte qualquer coisa..."
            aria-label="Digite sua pergunta"
          />

          <button
            type="submit"
            class="gdbot-send"
            aria-label="Enviar mensagem"
          >
            <svg viewBox="0 0 24 24">
              <path d="M21 3 3 10.5l7 2.5 2.5 7z"/>
              <path d="m10 13 4-4"/>
            </svg>
          </button>
        </form>
      </section>
    `;

    launcher = root.querySelector(".gdbot-launcher");
    panel = root.querySelector(".gdbot-panel");
    log = root.querySelector(".gdbot-log");
    form = root.querySelector(".gdbot-form");
    input = root.querySelector(".gdbot-input");
    sendButton = root.querySelector(".gdbot-send");

    const header = root.querySelector(".gdbot-head");

    header.insertBefore(
      avatar("gdbot-av gdbot-av--head"),
      header.firstChild
    );

    launcher.addEventListener("click", function () {
      definirAberto(panel.hidden);
    });

    root
      .querySelector(".gdbot-close")
      .addEventListener("click", function () {
        definirAberto(false);
        launcher.focus();
      });

    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        definirAberto(false);
        launcher.focus();
      }
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      const texto = input.value.trim();

      if (!texto || enviando) return;

      input.value = "";
      perguntar(texto);
    });

    document.body.appendChild(root);

    // RESTAURAR HISTÓRICO
    if (state.msgs.length) {
      state.msgs.forEach(function (msg) {
        log.appendChild(
          linha(msg.from, msg.text, msg.time)
        );
      });
    } else {
      mensagem("bot", CONFIG.saudacao);
    }

    mostrarSugestoes();
    definirAberto(state.open, true);
  }

  // ABRIR E FECHAR
  function definirAberto(abrir, semFoco = false) {
    panel.hidden = !abrir;

    launcher.classList.toggle("is-open", abrir);

    launcher.setAttribute(
      "aria-expanded",
      String(abrir)
    );

    state.open = abrir;
    salvar();

    if (abrir) {
      rolarFim();

      if (!semFoco) {
        input.focus();
      }
    }
  }

  function rolarFim() {
    log.scrollTop = log.scrollHeight;
  }

  // LINHA DE MENSAGEM
  function linha(de, texto, horario) {
    const row = el(
      "div",
      "gdbot-row gdbot-row--" + de
    );

    if (de === "bot") {
      row.appendChild(avatar("gdbot-av"));
    }

    const bolha = el("div", "gdbot-bubble");

    // textContent evita injetar HTML do usuário ou IA
    bolha.appendChild(
      el("span", "gdbot-txt", texto)
    );

    bolha.appendChild(
      el("time", "", horario || hora())
    );

    row.appendChild(bolha);

    return row;
  }

  // ADICIONAR MENSAGEM
  function mensagem(de, texto) {
    removerSugestoes();

    const horario = hora();

    log.appendChild(
      linha(de, texto, horario)
    );

    state.msgs.push({
      from: de,
      text: texto,
      time: horario
    });

    if (
      state.msgs.length >
      CONFIG.limiteHistorico
    ) {
      state.msgs = state.msgs.slice(
        -CONFIG.limiteHistorico
      );
    }

    salvar();
    rolarFim();
  }

  // INDICADOR DE DIGITAÇÃO
  function digitando() {
    removerSugestoes();

    const row = el(
      "div",
      "gdbot-row gdbot-row--bot"
    );

    row.appendChild(avatar("gdbot-av"));

    const bolha = el(
      "div",
      "gdbot-bubble gdbot-typing"
    );

    bolha.setAttribute(
      "aria-label",
      "Guardião está digitando"
    );

    bolha.innerHTML = "<i></i><i></i><i></i>";

    row.appendChild(bolha);
    log.appendChild(row);
    rolarFim();

    return function parar() {
      row.remove();
    };
  }

  // PERGUNTAS FREQUENTES COMO SUGESTÕES
  function removerSugestoes() {
    const existente =
      log.querySelector(".gdbot-chips");

    if (existente) existente.remove();
  }

  function mostrarSugestoes() {
    removerSugestoes();

    const box = el("div", "gdbot-chips");

    box.setAttribute("role", "group");
    box.setAttribute(
      "aria-label",
      "Perguntas sugeridas"
    );

    // Sugestões mudam conforme a conversa
    const ultimaPergunta = [...state.msgs]
      .reverse()
      .find(m => m.from === "user");

    let lista = [...perguntas];

    if (ultimaPergunta) {
      const texto =
        ultimaPergunta.text.toLowerCase();

      if (
        texto.includes("golpe") ||
        texto.includes("fraude")
      ) {
        lista = [
          "Como identificar um golpe?",
          "Como saber se um link é falso?",
          "O que fazer se caí em um golpe?",
          ...perguntas
        ];
      } else if (
        texto.includes("dinheiro") ||
        texto.includes("finança") ||
        texto.includes("juros")
      ) {
        lista = [
          "Como organizar minhas finanças?",
          "O que são juros?",
          ...perguntas
        ];
      }
    }

    lista = [...new Set(lista)].slice(0, 4);

    lista.forEach(function (pergunta) {
      const botao = el(
        "button",
        "gdbot-chip",
        pergunta
      );

      botao.type = "button";

      botao.addEventListener("click", function () {
        perguntar(pergunta);
      });

      box.appendChild(botao);
    });

    log.appendChild(box);
    rolarFim();
  }

  // CONSULTA À INTELIGÊNCIA ARTIFICIAL
  async function perguntar(texto) {
    texto = String(texto || "").trim();

    if (!texto || enviando) return;

    mensagem("user", texto);

    enviando = true;
    input.disabled = true;
    sendButton.disabled = true;

    const pararDigitacao = digitando();

    try {
      // Histórico recente da conversa
      const historico = state.msgs
        .filter(m =>
          m.from === "user" ||
          m.from === "bot"
        )
        .slice(-12)
        .map(m => ({
          role:
            m.from === "user"
              ? "user"
              : "assistant",
          content: m.text
        }));

      const resposta = await fetch(
        CONFIG.endpoint,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            messages: historico
          })
        }
      );

      const dados = await resposta.json();

      if (!resposta.ok) {
        throw new Error(
          dados.erro || "Falha ao consultar a IA"
        );
      }

      pararDigitacao();

      mensagem(
        "bot",
        dados.resposta ||
          "Não consegui gerar uma resposta."
      );

    } catch (erro) {
      console.error(
        "Erro no chatbot:",
        erro
      );

      pararDigitacao();

      mensagem(
        "bot",
        "Desculpe, não consegui responder agora. " +
        "Verifique a conexão com o servidor " +
        "e tente novamente."
      );

    } finally {
      enviando = false;
      input.disabled = false;
      sendButton.disabled = false;

      mostrarSugestoes();

      if (
        !panel.hidden &&
        !window.matchMedia(
          "(pointer: coarse)"
        ).matches
      ) {
        input.focus();
      }
    }
  }

  // INICIAR
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      montar
    );
  } else {
    montar();
  }
})();
