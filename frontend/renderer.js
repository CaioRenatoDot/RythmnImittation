const { ipcRenderer } = require('electron');

function escolherPasta() {
  ipcRenderer.invoke('selecionar-pasta').then((pasta) => {
    if (pasta) {
      document.getElementById('pasta').value = pasta;
    }
  });
}

function gerarAudios() {
  const pasta = document.getElementById('pasta').value;
  const quantidade = document.getElementById('quantidade').value;

  ipcRenderer.invoke('gerar-audios', { pasta, quantidade }).then((resposta) => {
    document.getElementById('mensagem').innerText = resposta;
  });
}
