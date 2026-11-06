# Football Betting Intelligence — versão 0.8.0

Site em português com Brasileirão e futebol internacional, resultados reais, classificação calculada e instalação como PWA no Android. Não executa apostas nem apresenta recomendação comercial de apostas. Inclui modelos experimentais separados para Brasileirão Série A, Premier League, La Liga e Bundesliga.

## Executar

Requer Node.js 24, sem dependências externas.

```sh
npm start
```

Abra http://localhost:3000. `npm test` executa a suíte. `npm run sync` consulta as fontes e atualiza as capturas versionadas. Em ambientes que exigem proxy HTTP, o Node 24 deve usar `NODE_USE_ENV_PROXY=1`, preservando os certificados e proxies fornecidos pelo ambiente.

`DATA_MODE=demo` ativa explicitamente seis partidas fictícias. O padrão é real. `DATA_DIR` define o diretório SQLite; o padrão é `runtime/`, ignorado pelo Git. Nenhuma chave é necessária para as integrações atuais.

## Cobertura

| Campeonato | Fonte |
| --- | --- |
| Brasileirão Série A e Série B | ESPN |
| Premier League, La Liga, Serie A italiana, Ligue 1 | ESPN |
| Liga Portugal, Eredivisie | ESPN |
| EFL Championship | ESPN |
| Champions League, Europa League, Copa Libertadores e Copa Sudamericana | ESPN |
| Bundesliga | OpenLigaDB |

A ESPN é acessada pelo endpoint público `https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard?dates={ano}&limit=1000`. Não é uma API contratada nem há vínculo com a ESPN, SLA ou garantia de disponibilidade, completude ou direitos de redistribuição comercial. Antes de explorar comercialmente, validar as condições do fornecedor e substituir por um feed licenciado se necessário. OpenLigaDB é uma base comunitária: https://www.openligadb.de/ e https://api.openligadb.de/index.html.

O sincronizador consulta o ano civil atual e anterior na ESPN; cada evento preserva sua temporada própria. Uma temporada europeia cruza dois anos. Assim, a temporada mais antiga pode estar incompleta, e datas futuras ainda não publicadas não aparecem. Respostas com 1.000 eventos são rejeitadas como possivelmente truncadas. Bundesliga consulta a temporada atual e anterior. O painel exibe origem, data de coleta e anos consultados; não anuncia resultados como disponíveis antes da coleta bem-sucedida.

Inclui partidas, equipes, datas, estado, estádio quando fornecido e placares finais. Estados ao vivo são apenas a fotografia da coleta, sem atualização contínua. Horários indefinidos aparecem como “a confirmar”. Adiamentos e cancelamentos não recebem um placar final. Escanteios e faltas são integrados quando a ESPN fornece contagens por equipe. A Bundesliga pela OpenLigaDB não fornece essas estatísticas. Cartões, xG e escalações não estão integrados; ausências permanecem sem valor.

Europa League, Copa Sudamericana e EFL Championship foram adicionadas à lista de coleta, mas ainda sem captura versionada: aparecem como “pendente” em `/api/v1/data-status` até a próxima execução de `npm run sync` ou do workflow de coleta. Não estão no piloto de probabilidades.

## Site e instalação no celular

O site é responsivo, com filtros por campeonato, temporada, período, situação e equipe, paginação e exportação CSV. Horários e filtros de data usam Brasília. O botão Atualizar relê o estado do servidor; não dispara uma coleta externa.

Publicado em HTTPS, pode ser instalado como PWA: no Chrome do Android, menu ⋮ → Instalar aplicativo / Adicionar à tela inicial. Quando disponível, o site mostra um botão Instalar. No iPhone: Safari → Compartilhar → Adicionar à Tela de Início. Não é necessário instalar pela Play Store.

A tela inicial segue um layout de app: barra superior com busca de equipe e menu lateral, faixa de datas (ontem e os próximos 6 dias, em Brasília), jogos agrupados por campeonato e abas inferiores no celular. Nos jogos agendados das quatro ligas do piloto, cada linha mostra as probabilidades experimentais de 1 / X / 2 (mandante, empate, visitante); nas demais, aparece “—”. São probabilidades do modelo, não odds de casas de apostas: o site não oferece apostas, “apostas do dia” ou recomendações. Os filtros ficam recolhidos em “Filtros”.

Os escudos dos times vêm das próprias fontes (`team.logo` da ESPN e `teamIconUrl` do OpenLigaDB) e são carregados direto dos servidores delas (`a.espncdn.com` e `upload.wikimedia.org`), sem cópia no repositório. Só endereços HTTPS desses dois hosts são aceitos, e a política de segurança do site libera imagens somente deles. Se uma imagem não carregar ou não existir, aparecem as iniciais do time. Os escudos são marcas dos clubes, sem licença de uso comercial pela ESPN ou pelo projeto; para uso comercial, é preciso licenciar. Não ficam disponíveis offline.

Manifesto, ícones PNG e service worker estão incluídos. O cache guarda apenas a interface. As APIs não são armazenadas offline: sem rede, aparece uma mensagem de indisponibilidade, sem apresentar um placar antigo como atual. A instalação depende do navegador e de suas regras de elegibilidade. Não foi validada em um aparelho físico.

Há também o projeto de APK Android WebView, apontando para `https://football-betting-intelligence.onrender.com/`. Veja [android/README.md](android/README.md). O APK depende desse site publicado; código Android não embute uma cópia da base de resultados.

## Probabilidades: piloto com quatro ligas

`GET /api/v1/predictions` retorna probabilidades experimentais de vitória da casa, empate e vitória visitante para partidas agendadas nos próximos 7 dias, com horário confirmado e coleta de até 24 horas. O piloto cobre somente Brasileirão Série A (`bra.1`), Premier League (`eng.1`), La Liga (`esp.1`) e Bundesliga (`bl1`). Cada liga tem pesos, histórico, versão e avaliação próprios; resultados de uma não entram no treino de outra. As demais competições continuam disponíveis para consulta, sem previsões.

O endpoint usa `?competition=eng.1`, `esp.1` ou `bl1` para selecionar outra liga. Sem parâmetro, preserva o Brasileirão Série A como padrão. Competições fora do piloto retornam HTTP 400. A seção de probabilidades começa com os quatro campeonatos recolhidos. Ao abrir um campeonato, os jogos são consultados e agrupados por data de Brasília; ao abrir uma data e uma partida, aparecem as probabilidades compactas. Análise e avaliação ficam em áreas recolhidas. Os filtros de partidas são independentes dessa navegação.

O modelo aprende os pesos de uma regressão logística multiclasse (softmax), com atualização sequencial e regularização L2, sem API de IA paga ou dependências externas.

Usa desempenho recente (últimos 10 jogos, pesos decrescentes e suavização), gols marcados/sofridos, desempenho em casa/fora e Elo atualizado com resultados anteriores. Exige pelo menos 160 partidas no treino e 8 jogos anteriores por equipe. Não usa escalações, notícias, lesões, suspensões ou odds e não compara valor de apostas.

O corte de treino é o início do dia UTC. Resultados só entram após uma margem de 6 horas desde o início da partida e nunca são usados nas previsões de seu próprio dia. A avaliação walk-forward reconstrói os mesmos cortes por dia, compara Brier, log loss e acerto com as frequências anteriores de resultados, e fornece os registros e faixas de calibração. É uma simulação retrospectiva com dados atualmente corrigidos pelo fornecedor; não reconstrói a disponibilidade histórica exata nem comprova ganho futuro.

As previsões para jogos futuros são registradas antes do início, com versão, probabilidades, corte de treino, indicadores e hash dos dados. O registro para a mesma partida, horário, versão e hash é imutável. A avaliação prospectiva usa a última previsão preservada antes do início, uma por partida; mudanças no horário impedem associar o registro antigo ao novo jogo. As probabilidades não são anexadas retroativamente aos resultados históricos.

`npm run predict` preserva as previsões da captura versionada em `data/predictions.json`. O workflow de coleta executa essa etapa e versiona os registros para sobreviverem ao disco efêmero do Render. Falhas ou atrasos no workflow podem deixar registros recentes somente no SQLite local. Nenhum serviço pago é provisionado.

O modelo permanece experimental. Não há garantia de maior acerto; uma melhora no erro das probabilidades não equivale necessariamente a melhora em acertar o resultado mais provável. O painel mostra as métricas do modelo e da referência sem prometer lucro.

## Classificação

Calculada por liga e temporada a partir dos resultados finais disponíveis. Exibe jogos, vitórias, empates, derrotas, gols, saldo, pontos e aproveitamento. Usa somente os filtros de campeonato e temporada. Copas exibem partidas e resultados, sem uma tabela única que misture fases e mata-mata.

Vitória vale 3 pontos. Desempates: saldo, gols marcados e nome. Não é classificação oficial: não considera punições, divisão por fases ou critérios completos de cada competição. Temporadas parcialmente cobertas geram tabelas parciais, conforme informado na interface.

## Histórico e atualização

SQLite preserva a resposta original, SHA-256, fonte, horário e partidas normalizadas. Capturas são isoladas por fornecedor, competição e período; atualizar uma liga não apaga outra. A migração da versão anterior adiciona o escopo sem apagar o histórico. Capturas antigas não substituem dados recentes, mesmo com fusos e frações de segundo diferentes.

O servidor carrega `data/openliga.json` e `data/espn.json`, com respostas gzip/base64 verificadas pelo hash. Ao iniciar e a cada seis horas, tenta atualizar as fontes. Falhas por liga são registradas e os dados anteriores permanecem disponíveis. O endpoint de cobertura informa defasagem por competição (>24h); datas de coleta não indicam garantia de correção dos resultados.

O workflow Football data snapshots consulta as fontes às 06:17 e 18:17 UTC, testa e versiona as capturas. Falhas parciais preservam as capturas anteriores, publicam os sucessos após os testes e deixam o workflow com falha visível. GitHub Actions está sujeito a habilitação, atrasos e cotas. Não há push forçado.

## Hospedagem

Use Node 24, build `npm install`, start `npm start`, health check `/api/v1/health`. `render.yaml` descreve um serviço gratuito; não cria nem contrata um serviço por si só. O Dockerfile inclui os módulos e dados necessários, mas a imagem não foi compilada neste ambiente.

**Render gratuito usa disco efêmero:** SQLite local pode ser perdido em reinícios ou publicações; capturas versionadas restauram a base mínima. Para histórico operacional durável, configure `DATA_DIR` em um disco persistente ou migre para um banco externo. Não há configuração de serviço pago neste projeto.

## API somente de leitura

- `GET /api/v1/health`: versão e modo.
- `GET /api/v1/predictions`: modelo selecionado do piloto, previsões, teste temporal e avaliação prospectiva.
- `GET /api/v1/fixtures`: partidas e origem de cada registro.
- `GET /api/v1/standings`: classificação calculada por liga/temporada, com regras explícitas.
- `GET /api/v1/data-status`: cobertura por competição, períodos, defasagem, capturas e logs.
- `GET /api/v1/evaluation`: métricas apenas de previsões previamente registradas; sem modelo, os resultados são nulos.

A lista de arquivos públicos é fixa. SQLite, capturas brutas e credenciais não são expostos. APIs aceitam apenas GET. Não coloque senhas ou chaves no repositório.

## Validação e limites

`npm test` cobre as duas fontes, estados de partidas, placares finais, isolamento entre ligas, migração SQLite, correções, integridade, persistência, classificação, probabilidades e rotas HTTP, incluindo manifesto e ícones. Application tests roda em pushes para main e pull requests.

A interface, a instalação no Android e o APK ainda exigem verificação em navegador/aparelho real. Os modelos do piloto ainda exigem validação prospectiva. Próximas extensões: feed com contrato e cobertura garantida, tabelas oficiais por fase, persistência externa e modelos com avaliação temporal prospectiva.

## Medição de desempenho do piloto

Execute `npm run benchmark` para comparar o cálculo de uma e quatro ligas em 10 execuções locais, com memória RSS e pico do processo. O script carrega as capturas e usa o mesmo código dos modelos. As probabilidades ficam calculadas em memória: consultas não treinam novamente, exceto no primeiro acesso após virar o dia UTC.

Medição local em 06/11/2026 com Node 24.22.1 e 6.903 partidas: mediana de 6,03 ms para uma liga e 19,17 ms para quatro; RSS após os cálculos de 226,59 MB, pico de 271,05 MB no processo completo. A medição é do ambiente de desenvolvimento, não da RAM do Render, e não é teste de carga concorrente. O plano gratuito oferece 512 MB de RAM; nenhuma configuração paga foi ativada. Tempos de rede e limites da hospedagem devem ser acompanhados em produção antes de ampliar o piloto.

## Probabilidades de gols

Cada partida com histórico suficiente inclui modelos binários leves para mais de 1,5, 2,5 e 3,5 gols e ambas as equipes marcarem. O treino é separado por liga e usa gols recentes das equipes e dos adversários, com ponderação e suavização. Os mesmos cortes temporais de dia UTC e margem de 6 horas impedem usar resultados do próprio dia. São exigidos 160 jogos observados e 8 por equipe. Os limites de totais respeitam probabilidades monotônicas.

Os modelos têm avaliação histórica contra frequências anteriores e avaliação prospectiva separada por mercado, sem duplicar jogos ou usar registros posteriores ao início. Brier binário varia de 0 a 1, diferente do Brier multiclasse do resultado. Registros com mercados adicionais são preservados no arquivo de previsões, sem alterar registros antigos. Modelos experimentais, sem comprovação de ganho futuro.

## Escanteios: segunda etapa

O parser ESPN preserva `homeCorners`, `awayCorners` e o total apenas quando ambos os valores são informados para um jogo encerrado. Ausências, parciais, valores inválidos e campos duplicados não viram zero. Um zero explícito é preservado. A migração reprocessa a evidência original mais recente de cada período ESPN, sem substituir dados recentes por sementes antigas.

Os modelos binários de escanteios estimam totais acima de 8,5, 9,5 e 10,5, separados por liga, com o mesmo corte temporal e limites mínimos de histórico usados nos gols. Usam escanteios recentes conquistados e cedidos por equipe e por mando. A Bundesliga permanece indisponível para esse mercado. A avaliação histórica e prospectiva é independente por limite e mercado.

## Faltas: terceira etapa

A integração ESPN preserva `homeFouls`, `awayFouls` e o total a partir de `foulsCommitted` para jogos encerrados. Ausência, ambiguidade e dados inválidos permanecem nulos; um zero informado é preservado. A migração reprocessa as capturas ESPN mais recentes sem alterar a evidência original.

Modelos binários estimam totais acima de 24,5, 29,5 e 34,5 faltas. O histórico e os parâmetros são separados por liga e por mercado. Há os mesmos limites mínimos, suavização, corte temporal, ordenação dos totais e avaliações independentes das etapas anteriores. A Bundesliga permanece indisponível para escanteios e faltas. Não se inferem essas estatísticas a partir de gols.

Após as três etapas, o benchmark local em 06/11/2026 teve mediana de 73,82 ms para calcular as quatro ligas, RSS de 279,22 MB após os cálculos e pico de 338,82 MB incluindo inicialização/migração. É medição local, não pico de produção nem teste de carga concorrente. Cada etapa foi publicada e verificada antes da seguinte, mantendo o plano gratuito.

## Resumo com até cinco cenários

O resumo por partida, também acessível pelo botão flutuante, mostra até cinco estimativas em ordem decrescente: resultado mais provável, um total de gols, ambas marcam, um total de escanteios e um total de faltas. Limites aninhados de uma mesma família não se repetem; os lados opostos não aparecem juntos. São exibidas menos opções quando os dados não estão disponíveis. Não se multiplicam probabilidades correlacionadas e não há comparação com odds ou promessa de acerto. O resumo reutiliza os cálculos publicados, sem novo modelo ou serviço.
