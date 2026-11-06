# Android — Football Intelligence

Aplicativo Android 8+ (API 26), com WebView do painel HTTPS hospedado no Render. Precisa de internet e preserva o modo de dados do servidor (real por padrão). Atualizações do site aparecem no aplicativo sem nova instalação; alterações no código Android exigem outro APK.

Permissão única: internet. Sem anúncios, rastreadores, acesso a arquivos, câmera ou localização. O conteúdo web executa JavaScript, limitado ao painel configurado; links HTTPS externos pedem confirmação para abrir no navegador. Não há ponte JavaScript nativa nem aceitação de certificados inválidos. Exportar CSV exige abrir o painel no navegador pelo botão da barra.

## Compilar

O workflow `.github/workflows/android.yml` usa Java 17, Gradle 8.11.1 e Android Gradle Plugin 8.10.1. Roda em alterações Android na main ou manualmente no GitHub Actions e guarda o APK em um artefato privado por 7 dias. A execução está sujeita às cotas do GitHub Actions da conta. Nenhum plano pago é configurado por este projeto.

Localmente, com Android SDK 35 e build-tools 35.0.0 já instalados e licenciados, execute `gradle assembleDebug lintDebug` nesta pasta. A saída é `app/build/outputs/apk/debug/app-debug.apk`.

O APK debug é para instalação de teste, não distribuição na Play Store. A chave debug do ambiente de compilação não é uma identidade de publicação estável; versões de builds diferentes podem exigir desinstalar a anterior. Antes de distribuir atualizações regulares, definir uma chave de release privada e durável fora do repositório.

Não foi feito teste em aparelho físico. Verificar no celular abertura, filtros, modo avião, retorno da conexão, navegação de volta e recortes da tela. O plano gratuito do Render pode demorar para iniciar após inatividade.


## Alternativa sem APK

O site versão 0.3 inclui instalação como PWA. No Chrome do Android, abra o site HTTPS e escolha Instalar aplicativo ou Adicionar à tela inicial. O PWA recebe as atualizações do site; requer internet para consultar partidas.
