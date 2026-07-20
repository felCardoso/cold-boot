# Project: COLD-BOOT

RPG de texto / TUI retro-cyberpunk. Você é um hacker rebelde dentro de uma
VAX-11/785 corporativa abandonada de 1988. O terminal do jogo **é** o terminal
da máquina invadida.

Feito com **Python 3 + [Textual](https://textual.textualize.io/)**.

```
python -m pip install -r requirements.txt
python main.py
```

> Terminal recomendado: um emulador com UTF-8 e cores (Windows Terminal, iTerm2,
> qualquer terminal Linux). No `conhost` legado do Windows, rode `chcp 65001`
> antes para os caracteres de caixa/mapa aparecerem certos.

## Por que Textual

O requisito mais difícil — "logs continuam rodando enquanto o jogador digita" —
é resolvido de graça pelo **event loop assíncrono** do Textual. Teletype, logs
de sistema em tempo real e o cronômetro do combate rítmico são apenas timers e
workers assíncronos; nenhum bloqueia o input. O sistema de widgets dá o
split-screen dos 3 painéis, e o Rich dá o verde-fósforo/âmbar ANSI.

## Arquitetura

Camadas desacopladas (as três primeiras não sabem que a UI existe):

| Papel             | Arquivo                | Responsabilidade                                   |
|-------------------|------------------------|----------------------------------------------------|
| **State Manager** | `coldboot/state.py`    | Todo o estado (trace, RAM, filesystem, rede). Puro. |
| Conteúdo          | `coldboot/world.py`    | Monta o filesystem UNIX falso (rede é procedural).  |
| **Proc-gen**      | `coldboot/procgen/`    | RNG semeado + rede (F1) + filesystem por host (F2) + lore (F3). |
| Combate/LOCKDOWN  | `coldboot/combat.py` · `lockdown.py` | ICE escalado por profundidade (F4) + minigame de Trace 100%. |
| **Command Parser**| `coldboot/parser.py`   | Texto cru → intenção (`Command`). Shell + PT natural.|
| Combate           | `coldboot/combat.py`   | Máquina de estados do Combate Rítmico de Digitação. |
| **UI Manager**    | `coldboot/ui.py`       | Render dos painéis + widget de teletype assíncrono. |
| **Game Loop**     | `coldboot/app.py`      | `App` Textual: layout, timers, dispatcher, workers. |

Fluxo de um comando:

```
Input.Submitted → parser.parse() → Command → app.do_<verbo>() → muta State
                                                              → UI re-renderiza
```

## Geração procedural (Fase 0 + 1)

A **rede** (o mini-mapa) é gerada a cada partida a partir de uma **seed**
determinística: mesma seed → mesma rede (bom para "seed do dia" e para debugar).
O algoritmo faz um random-walk num grid, adiciona loops e usa BFS a partir do
`GATE` para eleger o nó mais distante como objetivo (`CORE`, o daemon).

```python
from coldboot.app import ColdBootApp
ColdBootApp(seed=1337).run()   # roda uma rede específica
ColdBootApp().run()            # rede aleatória (a seed usada vai no boot e em state.seed)
```

Já implementado:
- **F1 — rede procedural** (`procgen/network.py`): grafo + BFS elege o CORE.
- **F2 — filesystem por host** (`procgen/filesystem.py`): cada nó tem seu próprio
  `/etc`, `/var/log`, `/home/admin` (trancado), `/sys`, `/tmp`... e ao invadir um
  host você "pivota" para o filesystem dele (o prompt vira `guest@<host>`).
- **F3 — lore por gramática** (`procgen/grammar.py`): MOTD, passwd, logs, e-mails
  e provocações da IA montados por fragmentos — variam por host, determinísticos.
- **F4 — ICE escalonado** (`combat.py`): rounds/tempo/penalidade escalam pela
  profundidade do alvo, e cada tipo tem um **verbo próprio** — não são só números
  diferentes:

  | Tipo | O que ele faz |
  |---|---|
  | Sentinela | poucos códigos, curtos — o aquecimento |
  | Firewall | códigos longos, direto ao ponto |
  | Caçador | o código **escapa** no meio do round e vira outro (uma vez) |
  | Guardião | o código **some** depois de um instante: digite de cabeça |
  | Fantasma | some **ainda mais cedo** E troca **enquanto está escondido** — o pior dos dois: memorizar não basta, o que você guardou pode já ter mudado. Só aparece bem fundo (`_PHANTOM_MIN_DEPTH`) |

**LOCKDOWN** (`lockdown.py`): ao bater Trace 100%, dispara um minigame do-or-die.
Vencer "rebate" o sinal (Trace → 55%) e sobe `lockdown_level` (o próximo é mais
rápido/longo). Errar = o vilão (a IA) solta uma fala impactante e a run acaba
(mas o jogo não: veja `reboot`). `reset_lockdown()` zera o escalonamento — o
cerco é da run, não seu — e quem chama é o **scrambler** e a incursão nova.

### Itens, cripto e hardware

Pastas escondem itens procedurais (`btc_miner_3f.py`, `wallet_a2c1.dat`,
`admin_7b.key`...), com chance moderada de spawn — a maioria fica vazia. Um
minerador roda em segundo plano (`run <arquivo>`) e gera **CRN** conforme o rig:
como o algoritmo é memory-hard, RAM pesa tanto quanto CPU. Minerar esquenta o
rig. Acima de 82 °C entra em throttle: a mineração para, o texto desacelera e
comandos podem abortar.

O rig é montado peça a peça (`store` / `comprar <id>`): a placa-mãe define
geração de RAM, socket, slots PCIe e teto de watts; a fonte limita a potência;
o cooler dissipa o calor. A CPU também dá segundos extras nos minigames de
combate e LOCKDOWN.

**Minerar faz barulho.** Você está queimando CPU de uma máquina alheia, e isso
aparece no `ps` deles: o minerador sobe o Trace a cada tick. O ruído cresce com
a raiz do hashrate — dobrar o rig não dobra o risco, mas rig grande é rig
barulhento. Com o rig inicial a mineração é quase impune (~17 min até o cerco);
com um rig de topo você tem uns 2 min. Minerar vira decisão, não renda passiva.

### Os 640K do host

`ram_total`/`ram_free` são a memória da **VAX invadida**, não do seu rig — e
tudo que você deixa lá dentro ocupa espaço:

- o **minerador** ocupa KB proporcionais à RAM do *seu* rig (memory-hard: a
  tabela precisa caber do outro lado). Cresce com a raiz para que o rig de topo
  ainda caiba nos 640K — mas por pouco;
- cada **item no buffer** (`take`) ocupa 40K.

Isso amarra os dois sistemas: um rig de topo mineirando deixa espaço para ~2
itens. Com a memória no talo o host desconfia e o ruído **dobra**. E o `run` se
recusa a subir um minerador que não cabe — `drop` alguma coisa antes.

### O rig e a loja

O rig é montado peça a peça, com marcas fictícias (FIC, NTX, Husky, PNU,
Kestrel) e specs de verdade: CPU por socket, RAM por geração/clock, **várias
GPUs** (uma por slot PCIe da placa), fonte por watts, cooler por dissipação e um
**roteador** cujo sinal (1–5) deixa o Trace passivo correr mais devagar
(`economy.creep_mult`).

A loja é um **pop-up** (`ShopScreen`), não uma lista no terminal: categorias no
topo, vitrine com a situação de cada peça, um **carrinho** e um **checkout**. O
carrinho é validado como um todo antes de cobrar — comprar a placa nova e a RAM
dela na mesma cesta funciona, e a ordem importa (`economy.preview_cart` /
`checkout`). Ou vai tudo, ou não vai nada. Abre pela mesa ou por `store` dentro
do setor.

### HUD em três painéis

O topo é dividido em **STATUS/REDE · RIG · MAPA**:

- **Status** são só medidores ao vivo (`hardware.telemetry`): Trace, CPU%, RAM
  usada, uma linha **por GPU** (`GPU 0`, `GPU 1`...), PSU em watts, sinal de
  internet, memória do host e o setor atual.
- **RIG** é o que está montado na sua mesa, peça por peça, com a temperatura e o
  hashrate — o que você *tem*, separado do que está *acontecendo*.

As barras são desenhadas por um helper único (`_meter`); a estrutura segue a que
você esboçou, sem copiar os caracteres.

### Itens que você carrega

`take <item>` carrega para o buffer; `use` funciona do buffer, em qualquer
lugar; `drop` devolve e libera RAM. Isso é o que torna o **scrambler** uma carta
na manga de verdade: dá para achar um cedo e guardar para o Trace 100%, em vez
de ser obrigado a queimá-lo na pasta onde ele estava.

O **cartão de acesso** (`keycard_*.bin`) abre o `cofre` de um host pelo
`leitor.dev` — `use <cartao> no leitor.dev` — sem combate e sem alarme. O cofre
também cede ao `hack`, com um ICE caro: o cartão é o atalho silencioso. Se a
rede sorteou um cofre, o mundo garante que existe um cartão nela.

O **backdoor.key** (`backdoor_*.key`, raro) funciona parecido, mas para
QUALQUER alvo hackeável — um nó da rede ou uma pasta trancada:
`use <arquivo> on <alvo>` resolve como se o duelo tivesse sido vencido, sem
ICE nenhum. Não funciona no CORE do setor (o clímax se ganha de verdade) — é
um atalho para as barreiras do caminho, não para o chefe.

### O jogo é infinito: setores

O jogo não tem fim — tem **setores** que descem para sempre. Cada setor é uma
rede nova; limpar o CORE dele avança para o próximo, mais fundo e mais duro.

O eixo infinito é o *número do setor*, não o tamanho da rede: o mapa ASCII trava
em 15 hosts (`MAX_NODES`), então a rede satura. O que continua escalando é
`effective_depth(depth, sector)`, que entra no ICE, no loot e no pagamento.
Rounds de duelo têm teto (um duelo de 15 códigos é longo, não difícil); passado
o teto, quem aperta é o tempo, a penalidade e o tamanho do código.

**O fluxo completo:**

```
  A MESA  ──conectar──►  SETOR N  ──limpar o CORE (boss)──►  paga CRN
    ▲                       │                                   │
    │                       └── LOCKDOWN falho (morte) ──┐      │
    └───────────────── volta à mesa ◄────────────────────┴──────┘
         (vitória: setor N+1  ·  morte: setor 1, rig mantido)
```

- **A mesa** (`DeskScreen`) é o hub: desconectado, sem Trace correndo. Vê o
  balanço, abre a loja, monta o rig, decide quando descer.
- **O setor** é a incursão: explorar, achar loot, minerar (com risco), invadir,
  chegar ao CORE.
- **O boss** é o CORE de cada setor (`make_boss`): ICE próprio, mais duro que
  qualquer nó, com persona que cicla (`NÚCLEO FRIO`, `SENTINELA-MÃE`, ...) e um
  verbo que alterna entre esconder o código e deixá-lo escapar.
- **Vencer** paga `sector_payout(setor)` (cresce mais que linear), você saca e
  avança um setor.
- **Morrer** (LOCKDOWN falho) congela a carteira e te joga de volta ao **setor
  1** — mas o **rig** é físico, fica na sua mesa. É o único ratchet, e é ele que
  faz os setores iniciais passarem voando na descida seguinte. `best_sector`
  guarda seu recorde.

### Modificadores de setor: cada incursão tem seu próprio trade-off

Todo `new_game()` sorteia um **modificador** (`world.SECTOR_MODIFIERS`) para a
incursão inteira — anunciado ao conectar, e consultável a qualquer momento com
`modifier`/`mod`. Cada um troca uma coisa boa por uma ruim (nenhum é de graça):

| Modificador | Efeito | Troca |
|---|---|---|
| Sinal Limpo | Trace ambiente 30% mais lento | pagamento do setor −10% |
| Alerta Máximo | ICE pune erros 30% mais forte | pagamento do setor +30% |
| Rede Fantasma | risco de descoberta da botnet pela metade | pagamento do setor −10% |
| ICE Amaciado | ICE pune erros 25% mais fraco | pagamento do setor −15% |

Os multiplicadores já resolvidos ficam no próprio `GameState`
(`mod_creep`/`mod_ice_penalty`/`mod_botnet_risk`/`mod_payout`) — quem consome
(`economy.creep_mult`, `economy.botnet_risk`, `combat.make_ice`/`make_boss`) só
lê um float, sem precisar importar `world.py`. Sorteado uma vez por setor
(determinístico pela seed), nunca muda no meio da incursão.

### Trace: só sobe — reduzir é sempre uma ação

Ficar parado não esfria nada: o Trace ambiente sobe sozinho o tempo todo
(`_trace_creep`, modulado pelo sinal do roteador), e a única forma de baixá-lo
de propósito é *fazer* alguma coisa — vencer o minigame de cifra, rodar um
script de disfarce, ou resolver o puzzle de código do setor. O jogo nunca
recompensa esperar; recompensa agir.

### Cifra: quebra de código por dedução (3x por setor)

`cipher`/`cifrar` abre um minigame de criptoanálise ao estilo Mastermind — bem
diferente do duelo de digitação do combate. Sem relógio: você tem um número
limitado de palpites (`CipherSession`, 8 por padrão) para deduzir um código
secreto de 4 dígitos. Cada palpite volta com feedback — quantos dígitos estão
certos **na posição certa** e quantos estão certos **na posição errada** — e
você refina a próxima tentativa a partir disso. Vencer alivia
`CIPHER_TRACE_RELIEF` (18) de Trace; esgotar as tentativas revela o código e
não paga nada. O alfabeto de dígitos possíveis cresce devagar com o setor (6 a
9 símbolos), então a dedução fica mais dura nas incursões mais fundas. Limitado
a `MAX_CIPHER_PER_SECTOR` (3) usos por incursão — não importa quantos hosts
você visite entre uma tentativa e outra.

### Script de disfarce: triangular o sinal fingindo ser outro usuário

Um item raro de loot — um arquivo `.bat` ou `.sh` (`masquerade_x7.bat`,
`impersonate_x2.sh`...) — que, ao rodar com `run <arquivo>`, sequestra por um
instante a sessão de outro usuário da máquina invadida e reduz o Trace na hora
(25 a 45, consumido no uso). `use` nele recusa e avisa para rodar com `run`,
igual ao minerador. Diferente da cifra: não exige nenhuma habilidade — só
precisa ser encontrado, então é sorte de exploração, não perícia.

### Scan trancado: achar antes de invadir

`scan` não vem destrancado de fábrica. Antes, comprometer um host revelava os
vizinhos de graça — dava para zerar uma rede inteira encadeando `hack` sem
nunca precisar de `scan`. Agora comprometer um nó não revela mais ninguém
sozinho, e `scan` fica bloqueado até você achar um dos dois caminhos (o jogo
garante que pelo menos um sempre existe):

- **`/home/admin`**, presente em todo host — hackeável, com um ICE mais caro;
- **`/etc/hosts`** (tabela de IP/MAC, ~70% de chance por host) ou `subnet.map`
  dentro do próprio `/home/admin` — só ler já destrava.

O **setor 0** (tutorial) já nasce com `scan_unlocked=True`, porque a rede fixa
dele não tem admin nem hosts file — sem isso o próprio tutorial travaria
tentando ensinar um comando que ele não libera.

### O código fragmentado: um enigma nos arquivos

Cada setor esconde um código de 3 grupos (`7QXK-M2NP-9RTZ`) partido em 3
fragmentos espalhados pela rede: o primeiro sempre embutido na cópia âncora de
`.history` em `/usr/guest`; os outros dois plantados em `/tmp` de dois hosts
diferentes, um raso e um fundo, para puxar exploração de verdade. O código só
aparece dentro de texto — nunca como nome de arquivo — então **não existe
autocompletar de Tab** para ele; tem que ser lido e digitado.

`decrypt <código>` (ou `decifrar`/`submit`) resolve o setor: paga um bônus alto
em CRN (`60 + 15 por setor`, bem mais que loot comum) e alivia **35 de Trace**
de uma vez — comparável ao scrambler. É opcional, uma vez por setor, e não
bloqueia nada: uma recompensa lateral para quem lê tudo que encontra.

### Botnet: minerar à distância, com risco

Além do rig na sua mesa, dá para plantar mineradores remotos em hosts já
**comprometidos**: `plant <host>` deixa um script rodando lá, rendendo CRN
sozinho a cada tick (`botnet_income_rate`, cresce com o setor) sem consumir
RAM nem esquentar o seu hardware. `botnet` lista o que está plantado e há
quanto tempo; `unplant <host>` puxa de volta, sem multa, mas também sem mais
renda dali.

O freio é o risco, não o preço: passados `BOTNET_GRACE_TICKS` (15 ticks) sem
ser puxado, cada script tem uma chance **crescente** por tick de ser achado e
apagado (até um teto de 35%/tick) — perde o script e leva 8 de Trace de
susto. `botnet` mostra essa contagem: um script além da graça aparece marcado
como **[!] QUENTE**, com o risco atual daquele tick — dá para decidir puxar
antes de perder, em vez de descobrir só quando já era. A capacidade (quantos
scripts de uma vez) escala com os núcleos da CPU do seu rig, então evoluir o
rig também evolui a botnet, sem precisar de uma categoria nova na loja — de
propósito não existe "rig minerador dedicado" à venda, isso tornaria o
dinheiro efetivamente infinito.

### Tutorial

Na primeira vez, o jogo abre no **setor 0** (`tutorial.py`): uma rede fixa, sem
ICE de verdade nem Trace correndo, que conduz passo a passo por `ls`, `cat`,
`cd`, `take`, `use`, `scan` e um `hack` real. Cada passo espera o comando certo.
`pular` sai a qualquer momento. É uma vez na vida (`settings.tutorial_done`), não
por partida.

Depois disso, **dicas contextuais** disparam na primeira vez que cada mecânica
aparece de verdade — o primeiro cadeado, o primeiro superaquecimento, o host com
a memória no talo, o leitor de cartão. Uma vez cada, e atravessam os setores.

### Sessão: boot, pausa e save

A run abre com o POST do **KRYOS/OS v4.2** (`screens.py`), o sistema fictício
desta VAX: teste de memória, spin-up do disco, barra de carga e login. Qualquer
tecla pula.

**Esc** abre o menu de pausa, que congela o jogo de verdade — Trace, mineração,
calor e até o relógio do ICE param enquanto ele está aberto. De lá dá para
salvar, carregar, alternar o alto contraste e trocar a dificuldade. `save`
(ou `salvar`) também grava pelo terminal.

O save (`savegame.py`) serializa o estado inteiro em `~/.coldboot/save.json` —
não só a seed, porque a partida acumula o que a seed não reconstrói: itens
consumidos, pastas destrancadas, nós comprometidos e o rig remontado. Salvar é
bloqueado no meio de um duelo (a sessão de combate não é serializada). As
preferências ficam à parte, em `~/.coldboot/settings.json`.

O arquivo é versionado e `migrate()` sobe saves antigos para o formato atual —
mudar o formato não pode custar a partida de quem já estava jogando. Saves de
versão *futura* (mais nova que o código) são recusados em vez de lidos torto.

### Acessibilidade e dificuldade

**Alto contraste** (menu de pausa): troca a paleta verde-fósforo por preto e
branco puros e engrossa o texto. Os cinzas sobre fundo quase-preto do tema
original são o principal problema de legibilidade, e somem no modo. A troca
repinta o que já está na tela, não só o texto seguinte (`theme.py` + `ui.py`).

**Dificuldade** (menu de pausa) — mexe nos dois minigames:

| Nível | Tempo | Código |
|---|---|---|
| Fácil | +80% | mais curto, com palavras legíveis (`SYS::kernel-frost`) |
| Normal | — | alfanumérico aleatório (`SYS::A3F9X2`) |
| Difícil | −30% | mais longo |

### Idioma: EN/PT

O jogo tem inglês como padrão, com português como tradução — troca no menu de
pausa (botão de idioma, ao lado do de contraste/dificuldade), com efeito
imediato. É um sistema de i18n próprio (`i18n.py`): um catálogo
`{chave: {"en": ..., "pt": ...}}` e uma função `i18n.t(chave, **kwargs)`
chamada em toda mensagem de UI — HUD, menus, tutorial, feedback de comando.
Chave ausente no catálogo aparece como `[chave]` na tela em vez de estourar
uma exceção, então um esquecimento fica óbvio ao jogar.

Nem tudo passa pelo i18n: o **lore procedural** — MOTD, `/etc/passwd`, logs,
e-mails, provocações da IA, nomes de usuário/corp/host, descrição dos itens,
e os nomes de ICE/boss (`procgen/grammar.py`, `procgen/loot.py`,
`combat.py`) — fica **sempre em inglês, fixo**, independente do idioma da UI.
A ideia: é "a língua da corporação que você invadiu", não a sua — o jogo
inteiro pode estar em português na tela, mas o e-mail que você lê dentro da
máquina invadida continua em inglês, porque foi escrito por gente daquela
corporação, não traduzido para você. Essa linha de corte é o que mantém o
catálogo do tamanho de "a interface do jogo", em vez de "o jogo inteiro
palavra por palavra".

## Comandos

`ls` · `cd <dir>` · `cat <arq>` · `pwd` · `scan` · `map` · `hack <alvo>` ·
`run <prog>` · `whoami` · `ps` · `inv` · `look`/`olhar` · `take`/`pegar` ·
`drop`/`largar` · `use`/`usar <x> [no <y>]` · `store`/`loja` · `comprar <id>` ·
`kill <proc>` · `save` · `desk`/`mesa` · `reboot` · `clear` · `exit` · `help` ·
`decrypt <código>`/`decifrar`/`submit` · `plant <host>`/`plantar` ·
`unplant <host>`/`desplantar` · `botnet` · `cipher`/`cifrar` ·
`modifier`/`mod`/`modificador`

`help` lista cada comando com uma explicação de uma linha, alinhadas na mesma
coluna.

Também entende linguagem natural: `olhar terminal`, `ler readme.txt`,
`ir para /var/log`, `usar keycard no leitor`.

**Teclas:** `Tab` completa · `→` aceita a sugestão apagada que aparece depois do
cursor · `↑`/`↓` repetem comandos anteriores · `Esc` abre o menu de pausa.

Objetivo de cada incursão: navegar a rede dissipando a névoa com `scan`/`hack` e
comprometer o nó **CORE** (o daemon COLD-BOOT) antes que o **Trace** chegue a
100% — o Trace só sobe sozinho, então baixá-lo de propósito exige `cipher`,
um script de disfarce achado como loot, ou resolver o puzzle de código do
setor. Pelo caminho, minerar CRN para comprar hardware (ou plantar minerador
remoto num host comprometido) — sabendo que minerar é justamente o que te
entrega. Depois, `reboot`, e de novo, com um rig melhor.

## Testes

```
python smoke_test.py            # verificação headless (Pilot): parser, comandos,
                                # combate, economia, save/load, boot e pausa
python screenshot.py 42 explore  # exporta preview_<cena>.svg da TUI
```

Cenas do `screenshot.py`: `explore` · `lockdown` · `boot` · `pause` · `contrast`.
Testes e previews usam pasta temporária: nunca escrevem no seu `~/.coldboot`.

## Publicar no itch.io

Um jogo de terminal vai para o itch.io como **download por plataforma**:

1. `pip install pyinstaller`
2. `pyinstaller --onefile --name coldboot --add-data "coldboot/game.tcss;coldboot" main.py`
   (no Linux/Mac troque `;` por `:` no `--add-data`)
3. Suba o executável de `dist/` para o itch.io (um por SO: Windows/Mac/Linux),
   marque a plataforma no upload e escreva "rode pelo terminal / duplo clique".

PyInstaller empacota para o SO em que roda (sem cross-compile) — para os três
executáveis, rode o passo 2 no Windows, no Mac e no Linux, ou dispare o
workflow `.github/workflows/build.yml` (matrix Windows/Mac/Linux, aba Actions
→ "Build itch.io executables" → Run workflow, ou automático em tag `v*`) e
baixe os três artefatos prontos da run.

## Próximos passos sugeridos

- Trilha de efeitos sonoros via `playsound` opcional.
- Mais modificadores de setor (`world.SECTOR_MODIFIERS`) — o sistema já suporta
  qualquer combinação de multiplicadores, só falta desenhar mais trade-offs.
- Achievements/estatísticas de meta-progressão (além de `best_sector`).
