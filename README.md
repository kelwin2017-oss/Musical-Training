# Musical Training (Treino de Letras)

Um app para aprender idiomas com música que roda só no seu PC. Ele segue as mecânicas do LingoClip/LyricsTraining, não tem limite diário e vem com várias funções extras de estudo.

## Como abrir

1. Precisa ter **Python 3** instalado (no Windows, marque "Add to PATH" na instalação).
2. Dê dois cliques em **`Musical Training.exe`**, na pasta principal. Ele só abre o `App\iniciar.bat`, e funciona em qualquer pasta e em qualquer PC. No Linux ou Mac, rode `App/iniciar.sh`.
3. O navegador abre em `http://localhost:8765`. O servidor do app roda **sem janela** e fica aberto **enquanto a aba do app estiver aberta** (não importa quanto tempo, nem se a aba está em segundo plano). Quando você fecha a aba, ou o navegador inteiro, ele se encerra sozinho em uns 15 segundos. Recarregar a página (F5) não fecha o app. Também dá para fechar em Configurações → **⏻ Encerrar o app**. Se o servidor fechar com o app aberto, nada se perde: o que você fizer fica guardado no navegador e vai para a pasta `dados/` quando você abrir o `Musical Training.exe` de novo (pode continuar na mesma aba).

> **Abas que "dormem":** o Chrome (*Economia de memória*) e o Edge (*Guias em suspensão*) podem descarregar abas paradas há muito tempo, e isso conta como fechar a aba. Para evitar, adicione `localhost:8765` em Chrome → Configurações → Desempenho → *Sempre manter estes sites ativos*, ou em Edge → Configurações → Sistema e desempenho → *Nunca colocar estes sites em suspensão*.

> Para ver as mensagens do servidor (útil quando algo dá errado), elas ficam em `App/dados/servidor.log`. Se preferir a janela preta como antes, rode `App\iniciar.bat --janela`.

**Atalho na Área de Trabalho:** clique com o botão direito no `Musical Training.exe` → *Mostrar mais opções* → *Enviar para* → *Área de trabalho (criar atalho)*. O atalho já vem com o ícone.

**Aviso do Windows na primeira vez:** como o `.exe` não tem assinatura digital paga, o Windows pode mostrar *"O Windows protegeu o computador"*. Clique em **Mais informações → Executar assim mesmo**. O código-fonte do iniciador (cerca de 30 linhas) está em `App/launcher/launcher.c`, e o `build.sh` gera o `.exe` de novo. Se preferir, use o `App\iniciar.bat` direto, que faz a mesma coisa.

> Por que um servidor? O YouTube recusa o player incorporado em páginas abertas com `file://` (é o erro 153). Com o `server.py` o app roda como um site local. Ele escuta só em `127.0.0.1`, então nada fica exposto na sua rede.

Use **Chrome ou Edge**: o modo 🎤 Falar só funciona nesses dois.

## Atalhos

`Esc` pausa · `↑` volta para a linha anterior · `Shift+↑` repete devagar · `↓` dica · `Tab` pula · `Enter` aceita com tolerância · `1–4` escolhem uma opção

## Como funciona por dentro (para você modificar)

Tudo está em um único arquivo, o `index.html` (HTML + CSS + JS, sem build e sem dependências). Ele é dividido em blocos comentados:

| Bloco | Responsabilidade |
|---|---|
| `Utilidades` | `tokenize()` separa palavras e pontuação; `norm()` normaliza para comparar; `lev()` calcula a distância de edição |
| `Banco de dados` | Grava na pasta `App/dados/` pelo `server.py` (cai para o IndexedDB do navegador se o servidor não estiver rodando): `songs`, `blobs` (arquivos de mídia), `words` (revisão), `history` |
| `LRC` | `parseLyrics()` e `toLRC()` |
| `Helpers de metadados` | `guessMeta()` limpa o título do YouTube (tira "Official Video", "[4K]" etc.) e separa artista e música; `lrclibFind()` escolhe a melhor letra; `findCover()` busca a capa |
| `Menu` / `Importar` | `renderMenu()`, `openImport()`, `runImport()` (3 buscas em paralelo) |
| `server.py` | Rotas `/api/playlist`, `/api/oembed` e `/api/itunes`. O navegador sozinho não consegue acessar esses sites por causa de CORS |
| `Players` | `YTPlayer` (YouTube IFrame API) e `FilePlayer` (`<video>`), com a mesma interface: `play/pause/seek/time/duration/setRate` |
| `Jogo` | `computeWordTimes()` calcula os tempos de cada palavra; `updateFollow()` faz o destaque; `prepareGame()` sorteia as lacunas; `tick()` roda a cada 50 ms e descobre a linha atual e se precisa pausar; `resolveGap()` cuida da pontuação |
| `Revisão espaçada` | `srsMiss()`, `srsHit()`, `BOX_DAYS` |


## Novidades da versão 6

- **Sincronização pelas legendas do próprio vídeo (método principal)**: muitos clipes têm legenda no YouTube, oficial ou automática, já cronometrada com o vídeo. O app compara as palavras da legenda com as da letra e recalcula o tempo de cada verso — funciona até quando o clipe tem cenas extras no meio da música (ele detecta a mudança de "regime" e compensa).
  - Roda sozinho na primeira vez que a música abre, e também na importação de playlist (as prontas ganham a marca "🤖 sincronizada pela legenda").
  - Para rodar na mão: botão **🤖 Auto** (ao lado do ±0,25s) ou, no Menu, **⋯ → 🤖 Sincronizar pelas legendas do vídeo**.
  - O `iniciar.bat` agora instala o **yt-dlp** na primeira vez: é o plano B para ler a legenda quando o YouTube muda o formato da página. As legendas baixadas ficam em cache em `dados/legendas/` (só para alinhar — nada disso aparece no jogo).
- **Nome do vídeo na escolha da letra**: se o vídeo é "Live", "Acoustic", "Remix", "Sped up" etc., o app prefere a versão da letra com a mesma marcação e evita as outras (além de continuar comparando a duração).
- **🎯 em qualquer verso, com desfazer**: passe o mouse sobre um verso e clique no **🎯** dele no exato instante em que ele começa a ser cantado — ele e os seguintes se realinham (os anteriores ficam como estão). O **🎯 1º verso** move a letra inteira. O **↶** desfaz os últimos ajustes, e **⋯ → ↺ Restaurar tempos originais** volta à letra como veio do LRCLIB.
- **A música não corta mais o fim do verso**: o jogo agora pausa um pouquinho depois da virada para o próximo verso (+0,35s por padrão, ajustável em Configurações → Correção → "Pausar depois do fim do verso") e, quando você completa a linha, ele volta para o comecinho do verso seguinte para você não perder nada.

## Novidades da versão 5

- **Editor**: ficaram só **Salvar** (salva tudo e continua onde você está) e **Salvar e jogar ▶** (salva e abre o jogo). Se você editar a música que está aberta, as mudanças valem na hora. Se der erro ao salvar, ele aparece na tela.
- **O vídeo começa do 0:00.** Quem quiser pular a introdução pode ativar isso em Configurações.
- **Letra do mesmo tamanho do vídeo**:
  - Na importação, o app escolhe a versão da letra no LRCLIB com a duração mais próxima da do vídeo.
  - Quando o clipe tem introdução ou final extra, o app mede o vídeo na primeira vez que a música abre e ajusta a sincronia sozinho.
  - Na busca manual de letra, as versões mostram a diferença em relação ao vídeo (ex.: "+12s vs vídeo").
  - O **⋯ → 🔄 Buscar letra do tamanho do vídeo** refaz a escolha para músicas já importadas.
- **🎯 1ª linha**: com o vídeo tocando, clique no instante em que o primeiro verso começa e a letra inteira se alinha. Depois, refine com ±0,25s se precisar.
- **Divisória arrastável** entre o vídeo e a letra, com tamanho mínimo para os dois lados. O app guarda um tamanho para o modo normal e outro para o modo recolhido. Duplo clique na divisória volta ao padrão.

## Onde ficam seus dados (versão 4)

Tudo fica na pasta **`dados/`**, dentro da pasta do app:

| Arquivo | Conteúdo |
|---|---|
| `songs.json` | Músicas: título, artista, capa, letra, sincronia e melhores % |
| `history.json` | Histórico de partidas (XP, sequência, gráficos, últimas jogadas) |
| `words.json` | Palavras da revisão espaçada |
| `settings.json` | Configurações |
| `midia/` | Cópias dos arquivos de áudio e vídeo que você escolheu do PC |
| `backups/AAAA-MM-DD/` | Cópia automática diária dos `.json`. Fica guardada por 14 dias |


## Novidades da versão 3

- **▴ Recolher · vídeo maior**: o botão no quadro da música esconde modo, nível, acompanhamento, velocidade e atalhos, e o vídeo fica bem maior. Uma etiqueta resume o que está selecionado. Clique em **▾ Ajustes** para mostrar tudo de novo. O app lembra a sua escolha.
- **↑ volta para a linha anterior**: a música recomeça na linha de antes, para você ouvir no contexto. Se a linha anterior estiver longe (intro ou solo), ela volta só 3 segundos. Na Revisão, **↑** e **🔊 Ouvir trecho** fazem o mesmo, e **▶ Só a linha** toca só o verso da palavra. Para voltar ao comportamento antigo, desmarque a opção em Configurações → Correção.
- **🗑️ Apagar tudo** (Configurações → Zona de perigo): apaga músicas, arquivos, progresso e configurações. Antes, pede para você digitar APAGAR e oferece exportar um backup.

## Adicionando uma música

1. Clique em **+ Nova música**.
2. Escolha a fonte:
   - **YouTube**: cole o link (pode ser clipe, lyric video ou áudio oficial). O app preenche título, artista, capa e letra sozinho. Se você trocar o link por outro vídeo, ele limpa tudo e preenche de novo com os dados do novo vídeo.
   - **Arquivo do PC**: mp3, m4a, wav, ogg, mp4, webm… O arquivo é copiado para o banco do navegador.
3. Escolha a letra:
   - **🔎 Buscar** procura no [LRCLIB](https://lrclib.net), um banco aberto de letras **já sincronizadas**.
   - Ou cole um `.lrc` (`[00:12.30] texto`).
   - Ou cole o texto puro e clique em **Salvar e sincronizar ⏱️**. Aí é só dar play e apertar **Espaço** no começo de cada verso.
4. Se a letra estiver adiantada ou atrasada em relação ao vídeo (clipes costumam ter introdução), ajuste com **−0,25s / +0,25s**. O ajuste fica salvo na música.

## Novidades da versão 2

- **Menu**: a tela inicial mostra suas músicas em cards com capa e o melhor resultado em cada nível (N1–N4). As cores indicam o desempenho: verde é 90% ou mais, amarelo é 70% ou mais, e 👑 marca um 100%. Dá para filtrar entre Todas, Não jogadas, Concluídas e Com ?, e ordenar a lista. Clicar no logo sempre volta para o Menu.
- **Últimas jogadas**: a barra lateral lista as músicas que você jogou, com o último resultado de cada uma.
- **📥 Importar playlist do YouTube**: cole o link de uma playlist, ou vários links de vídeos, e o app cria todas as músicas sozinho. Ele tira título e artista do nome do vídeo, busca a letra sincronizada no LRCLIB e a capa no iTunes.
  - O que não for encontrado aparece com **?** no card. Passe o mouse e clique em **⋯ → Editar informações** para completar. Quando estiver tudo certo, o **?** some.
  - No editor, o botão **🪄 Preencher automático** refaz a busca de uma música só.
- **Acompanhamento da letra**: escolha entre ▤ *Por linha*, ▦ *Palavra a palavra* ou ▮ *Letra a letra* (preenchimento estilo karaokê). Se a letra tiver tempos por palavra (`<00:12.30>palavra`, o formato "LRC enhanced"), eles são usados. Se não tiver, o ritmo é estimado pelo tamanho das palavras.

> Atualizando da versão 1: feche a janela preta antiga do servidor antes de abrir o novo `iniciar.bat`. Suas músicas e estatísticas continuam lá, porque ficam no navegador.

## Modos

| Modo | O que faz |
|---|---|
| ⌨️ Escrever | Igual ao LingoClip: lacunas na letra, você digita, e o vídeo pausa no fim da linha até completar |
| 🔘 Escolher | 4 opções por lacuna (teclas 1–4). Dois erros revelam a palavra |
| 📝 Ditado | **Novo.** Some a linha inteira e você digita tudo. A correção alinha as palavras (LCS) |
| 🎤 Falar | **Novo.** Shadowing: você repete a linha em voz alta e o reconhecimento de voz confere |
| 🎤 Karaokê | Letra completa, sem jogo. Tem loop de linha para treinar um trecho |

Níveis (Escrever/Escolher): Iniciante 10%, Intermediário 25%, Avançado 50% e Expert 100% das palavras.

## Funções a mais em relação ao original

- **Revisão espaçada (Leitner)**: tudo que você erra, pula ou resolve com dica vai para a aba Revisão, com a frase da música como contexto e um botão para **ouvir o trecho original**. Os intervalos são 1, 3, 7, 14 e 30 dias.
- **Lacunas inteligentes**: as palavras que estão na revisão aparecem mais como lacuna, e "the/a/I" aparecem menos.
- **Velocidade 0.5×–1.25×** e **🐢 repetir a linha a 0.75×** (Shift+↑).
- **Dica** (↓) revela uma letra. No modo Escolher, ela elimina uma opção.
- **Tolerância**: ignora acentos e aceita 1 erro de digitação com Enter (vale meio ponto).
- **Clique em qualquer palavra**: mostra tradução (MyMemory), definição e fonética em inglês (dictionaryapi.dev), áudio nativo, voz sintética e links para Google Tradutor, WordReference e YouGlish.
- **🌐 Traduzir a linha inteira** (passe o mouse na linha).
- **Estatísticas**: XP, sequência de dias, precisão média, gráfico de 21 dias, palavras que mais te pegam e histórico.
- **Backup** em JSON (exportar e importar).



## Observações

- Alguns vídeos do YouTube não permitem ser incorporados (erros 101/150). Nesse caso, procure outro upload da mesma música (lyric video ou "Topic").
- Tradução e dicionário precisam de internet. O jogo com arquivos locais funciona offline.
