// Chat do hóspede: carrega a conversa pela API, envia mensagens e atualiza a cada 3 s
(function () {
  const hotel = window.HOTEL;
  const seletor = document.getElementById("contato");
  const caixaNovo = document.getElementById("caixa-novo");
  const telNovo = document.getElementById("tel-novo");
  const lista = document.getElementById("mensagens");
  const status = document.getElementById("status");
  const info = document.getElementById("info-hospede");
  const form = document.getElementById("form-msg");
  const campo = document.getElementById("texto");
  const ROTULOS = { bot: "Assistente virtual", equipe: "Equipe do hotel", sistema: "" };
  let assinatura = "";
  let enviando = false;

  function numeroAleatorio() {
    const n = String(Math.floor(Math.random() * 1e8)).padStart(8, "0");
    return `(27) 9${n.slice(0, 4)}-${n.slice(4)}`;
  }

  function lerNovo() {
    try { return sessionStorage.getItem("novo-contato-" + hotel); } catch (e) { return null; }
  }

  function gravarNovo(valor) {
    try { sessionStorage.setItem("novo-contato-" + hotel, valor); } catch (e) { /* sem storage */ }
  }

  function telefoneAtual() {
    return seletor.value === "__novo" ? telNovo.value.trim() : seletor.value;
  }

  function atualizarCaixaNovo() {
    caixaNovo.hidden = seletor.value !== "__novo";
  }

  function bolha(m) {
    const div = document.createElement("div");
    div.className = "bolha autor-" + m.autor;
    if (ROTULOS[m.autor]) {
      const r = document.createElement("span");
      r.className = "rotulo";
      r.textContent = ROTULOS[m.autor];
      div.appendChild(r);
    }
    const t = document.createElement("div");
    t.className = "texto";
    t.textContent = m.texto;
    div.appendChild(t);
    const h = document.createElement("span");
    h.className = "hora";
    h.textContent = m.hora;
    div.appendChild(h);
    return div;
  }

  function desenhar(dados) {
    const nova = dados.telefone + "|" + dados.status + "|" + dados.mensagens.map((m) => m.id).join(",");
    if (nova === assinatura) return;
    assinatura = nova;

    if (dados.status === "humano") {
      status.textContent = "Com a equipe · assistente pausado";
      status.className = "status-conversa humano";
    } else {
      status.textContent = "Assistente virtual";
      status.className = "status-conversa bot";
    }
    info.textContent = dados.hospede
      ? `${dados.hospede} · ${dados.reserva || "sem reserva ativa"} · ${dados.telefone}`
      : `${dados.telefone} · contato sem reserva`;

    lista.innerHTML = "";
    if (!dados.mensagens.length) {
      const vazio = document.createElement("p");
      vazio.className = "vazio";
      vazio.textContent = "Nenhuma mensagem ainda. Mande uma pergunta como se fosse o hóspede.";
      lista.appendChild(vazio);
    }
    dados.mensagens.forEach((m) => lista.appendChild(bolha(m)));
    lista.scrollTop = lista.scrollHeight;
  }

  async function carregar() {
    const tel = telefoneAtual();
    if (!tel || enviando) return;
    const url = `/api/conversa?hotel=${encodeURIComponent(hotel)}&telefone=${encodeURIComponent(tel)}`;
    const resp = await fetch(url);
    if (resp.ok) desenhar(await resp.json());
  }

  async function enviar(texto) {
    const tel = telefoneAtual();
    texto = texto.trim();
    if (!tel || !texto) return;
    enviando = true;
    lista.querySelector(".vazio")?.remove();
    lista.appendChild(bolha({ autor: "hospede", texto, hora: "agora" }));
    const digitando = document.createElement("div");
    digitando.className = "digitando";
    digitando.textContent = "…";
    lista.appendChild(digitando);
    lista.scrollTop = lista.scrollHeight;
    try {
      const resp = await fetch("/api/mensagem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hotel, telefone: tel, texto }),
      });
      assinatura = "";
      if (resp.ok) desenhar(await resp.json());
    } finally {
      digitando.remove();
      enviando = false;
    }
  }

  function trocarContato() {
    atualizarCaixaNovo();
    assinatura = "";
    const url = new URL(window.location);
    if (seletor.value === "__novo") url.searchParams.delete("telefone");
    else url.searchParams.set("telefone", seletor.value);
    history.replaceState(null, "", url);
    carregar();
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = campo.value;
    campo.value = "";
    enviar(texto);
    campo.focus();
  });
  document.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => enviar(b.dataset.texto)));
  seletor.addEventListener("change", trocarContato);
  telNovo.addEventListener("change", () => { gravarNovo(telNovo.value.trim()); assinatura = ""; carregar(); });

  telNovo.value = lerNovo() || numeroAleatorio();
  gravarNovo(telNovo.value);
  atualizarCaixaNovo();
  carregar();
  setInterval(carregar, 3000);
})();
