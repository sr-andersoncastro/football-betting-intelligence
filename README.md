# Football Betting Intelligence

Primeira versão funcional de um laboratório de análise esportiva. Interface em português para computador e celular, com dados **inteiramente sintéticos**. Não contém recomendações de apostas, comparação de odds, gestão de banca ou execução de transações.

## Executar

Requer Node.js 22 ou superior. Sem bibliotecas externas ou instalação de dependências.

```sh
npm start
```

Abra http://localhost:3000. Para testar: `npm test`.

No PowerShell, uma porta alternativa pode ser definida com `$env:PORT=3001` antes de iniciar. O aplicativo lê a variável do processo, não carrega arquivos `.env` automaticamente.

## O que funciona

- Painel responsivo de partidas e estatísticas de gols, escanteios e cartões.
- Filtros por campeonato, situação e equipe.
- Exportação CSV da seleção.
- Avaliação de previsões sintéticas 1X2 com Brier multiclasse (soma, intervalo 0–2) e log loss natural.
- Registro da versão e horário de cada previsão; validação impede previsões registradas no início ou após a partida.
- API somente de leitura, sem credenciais e sem escrita remota.

### Rotas

`GET /api/v1/health`, `/api/v1/fixtures`, `/api/v1/evaluation`.

## Estrutura

`server.mjs`: servidor e rotas; `lib.mjs`: validação e avaliação; `public/`: interface; `data/demo.json`: conjunto fictício; `test/`: testes de integridade, métricas e HTTP.

## Arquitetura e próximos marcos

Esta entrega é uma base Node.js demonstrativa, não a implementação Python/FastAPI/PostgreSQL descrita no planejamento original. A escolha permite executar e verificar o primeiro painel no ambiente disponível, sem serviços pagos ou chaves. Não há sincronização de dados reais nem banco persistente de produção nesta versão.

1. Definir fornecedor e verificar a cobertura atual de cada campeonato, licença de uso e cotas antes da integração. Não há promessa de cobertura gratuita de Série B ou de dados ao vivo.
2. Implementar aquisição no servidor e normalização de identificadores, fusos horários, estatísticas e eventos; manter fonte, horário de captura e payload original para auditoria. Chaves ficam exclusivamente no servidor.
3. Adicionar PostgreSQL e migrações para competições, equipes, partidas, estatísticas, execuções de coleta, versões de modelos e previsões. Nunca substituir um resultado real por dados demonstrativos silenciosamente.
4. Construir modelos de análise esportiva com divisão cronológica dos dados, comparação com baselines, calibração e validação prospectiva. Registrar o corte dos dados de treinamento além do horário da previsão; o horário sozinho não demonstra ausência de vazamento.
5. Preparar hospedagem HTTPS e autenticação antes de armazenar informações pessoais ou liberar operações administrativas. O servidor atual expõe apenas a demonstração pública, sem autenticação.
6. Avaliar aplicativo Android após a versão web hospedada e testada. Nenhum APK foi gerado.

O arquivo Dockerfile permite empacotar esta demonstração. A imagem requer download e foi incluída para uso futuro; sua execução depende de Docker instalado. Não há publicação automática, contratação de serviços, APIs externas ou contas novas.

## Limites da avaliação

Os indicadores usam três exemplos fictícios e **não são evidência de capacidade preditiva**. Não há modelo treinado, backtest walk-forward, estimativa de confiança, sistema em tempo real ou previsão de partidas reais. Datas e nomes são ilustrativos. O painel mostra horários de Brasília.

## Segurança

Não coloque senhas ou chaves no repositório. As rotas aceitam apenas GET, servem uma lista fixa de arquivos e aplicam uma política de conteúdo restrita. Importações futuras devem passar pela validação de esquema e ser auditadas. O CSV é exportado localmente no navegador.
