
const searchInput = document.getElementById("pesquisar");

const cards = document.querySelectorAll(".card");

const mensagemVazia = document.getElementById("mensagemVazia");

searchInput.addEventListener("input", function () {

    const pesquisa = searchInput.value
        .trim()
        .toLocaleLowerCase("pt-BR");

    let encontrados = 0;

    cards.forEach(function (card) {

        const conteudo = (
            card.innerText + " " + card.dataset.search
        ).toLocaleLowerCase("pt-BR");

        const corresponde = conteudo.includes(pesquisa);

        card.hidden = !corresponde;

        if (corresponde) {
            encontrados++;
        }

    });

    mensagemVazia.hidden = encontrados !== 0;

});
