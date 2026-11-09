# Corrida Certa

Serviço de acessibilidade que lê o card de corrida do app de motorista da **Uber** (`com.ubercab.driver`) e da **99** (`com.app99.driver`) e mostra um cartão por cima com **R$/km** e **R$/hora**.

- Valor ÷ (km de busca + km da viagem) = R$/km
- Valor ÷ (min de busca + min da viagem) × 60 = R$/hora
- Cartão verde (ambos acima do mínimo), laranja (um abaixo) ou vermelho (ambos abaixo). Mínimos configuráveis no app.
- Cards de "Pacote de viagens" são calculados e marcados como pacote.

## Por que a versão 0.2 não funcionava
1. Não havia overlay: o resultado só era gravado num banco interno.
2. Não calculava R$/hora (os minutos eram ignorados).
3. Faltava `flagIncludeNotImportantViews`, então o Android podia esconder o texto do card.
4. O parser exigia exatamente 2 trechos no formato `N min (X km)` e ignorava `contentDescription`.

## Instalar
O GitHub Actions (`.github/workflows/corrida-certa.yml`) compila o APK; baixe em Actions > execução > Artifacts. No celular: instale, abra o app, toque em "Ativar serviço de acessibilidade" e ligue **Corrida Certa**. No Android 13+, APK instalado fora da Play Store pede antes "Permitir configurações restritas" (Info do app > ⋮).

## Diagnóstico
Se um card não for lido, abra o app: a seção "Última leitura" mostra o texto bruto capturado. Mande esse texto para ajustar o parser em `OfferParser.java`.

Testes do parser: `gradle testDebugUnitTest` nesta pasta. Não foi testado em aparelho.
