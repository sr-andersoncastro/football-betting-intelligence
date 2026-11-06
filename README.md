# Football Betting Intelligence — versão 0.2

Base de análise esportiva com partidas reais da Bundesliga, interface em português e histórico auditável. Não contém recomendação ou execução de apostas.

## Executar

Requer Node.js 24 (node:sqlite). Sem dependências externas.

```
npm start
```

Abra http://localhost:3000. `npm test` executa os testes. `npm run sync` atualiza a captura versionada de duas temporadas. O modo fictício só é ativado explicitamente por DATA_MODE=demo; o padrão é real.

## Dados reais e cobertura

Fonte comunitária: [OpenLigaDB](https://www.openligadb.de/), [documentação](https://api.openligadb.de/index.html). A integração usa /getmatchdata/bl1/{temporada}. Não exige chave. A comunidade pode corrigir resultados; não é feed profissional nem cobertura ao vivo.

Integrado: Bundesliga, temporada atual e anterior, partidas, equipes, datas UTC e resultado final por resultTypeID=2. O painel informa temporada, fonte, coleta e hash SHA-256. Resultados parciais nunca viram placares finais. Ausências são null, nunca zero inventado.

Pendente: Brasileirão A e B, Premier League, La Liga e Champions League. Não há cobertura integrada de escanteios, cartões, xG ou escalações. Não há modelo treinado nem previsões reais; Brier e log loss ficam sem resultado até existirem previsões válidas.

## Histórico e persistência

SQLite armazena capturas brutas, SHA-256, horário de coleta, origem, partidas normalizadas e logs. Cada correção cria nova captura; uma semente antiga não sobrescreve um estado mais recente. Capturas brutas preservam a resposta original; a versão no arquivo data/openliga.json usa gzip/base64 e é validada antes da ingestão.

O servidor abre a captura versionada ao iniciar, tenta atualizar a temporada atual e consulta novamente a cada seis horas enquanto está ativo. Falhas mantêm os últimos dados e geram log; não há substituição silenciosa por demonstração. A interface é uma fotografia da consulta; recarregue para obter os dados atualizados.

**Render Free usa disco efêmero:** SQLite não sobrevive necessariamente a reinícios/publicações. A captura versionada é a recuperação mínima. O workflow Football data snapshots busca as duas temporadas às 06:17 e 18:17 UTC (03:17 e 15:17 de Brasília), testa e registra a captura no histórico Git, sujeito a habilitação, atrasos e cotas do GitHub Actions. Falhas de push (por exemplo, mudanças concorrentes) encerram a execução sem forçar sobrescrita. O workflow não garante disponibilidade contínua e o Render pode dormir. As execuções programadas ainda precisam de confirmação em produção.

Para um histórico operacional completo e persistente, próximo passo: PostgreSQL externo e migrações. DATA_DIR permite usar um disco persistente quando houver; por padrão usa runtime/, ignorado pelo Git.

## API somente de leitura

- GET /api/v1/health: versão e modo.
- GET /api/v1/fixtures: partidas normalizadas.
- GET /api/v1/data-status: cobertura, capturas recentes, integridade, falhas e defasagem (>24h).
- GET /api/v1/evaluation: métricas de previsões previamente registradas, se existirem.

Horários no painel: America/Sao_Paulo. Exportação CSV inclui origem, temporada e horário de coleta. Lista paginada de 50 em 50; CSV contém toda a seleção.

## Validação

Testes cobrem seleção do resultado final independente da ordem, ausências, erros HTTP, integridade de captura, correções, restauração SQLite, validação probabilística e HTTP. Ainda não há validação de modelo preditivo nem teste em aparelho Android. O aplicativo Android existente carrega o painel hospedado; veja android/README.md.

## Infraestrutura

Dockerfile com Node 24 incluído; Docker não foi executado neste ambiente. No Render: runtime Node, build npm install, start npm start, raiz vazia. .node-version e engines fixam Node 24. Nenhuma contratação nem credencial externa é necessária para esta fonte.

## Próximos marcos

1. Validar um fornecedor para Brasil A/B e campos adicionais.
2. Migrar capturas e histórico operacional para PostgreSQL persistente.
3. Desenvolver baselines de análise esportiva, treino com corte temporal, avaliação walk-forward e calibração.
4. Validar prospectivamente os modelos antes de apresentar previsões reais.

Não coloque senhas ou chaves no repositório. A API serve somente uma lista fixa de arquivos, não expõe SQLite ou respostas brutas e aceita apenas GET. Não há informações pessoais nem operações administrativas na aplicação.
