# Controle LG (APK)

App Android que controla TVs LG webOS pela rede Wi-Fi local. Nada é instalado na TV.

Uso: celular e TV na mesma rede, digite o IP da TV (Rede > Conexão Wi-Fi > Avançado), toque em Conectar e aceite o aviso na TV.

Abas: Controle (setas, OK, voltar, início, menu, números, cores, volume, canal, mudo, mídia, apps), Mouse (touchpad com clique e rolagem), Teclado (texto na TV), Mais (volume exato, entradas HDMI, lista de apps, tela off/on, mensagem). Botão Ligar usa Wake-on-LAN.

Limites: usa a porta 3000 (ws), então TVs que só aceitam 3001 (wss) não funcionam. Testado só contra uma TV simulada, não em TV real.

Compilar: workflow `.github/workflows/lg-remote.yml` (artefato `controle-lg-apk`) ou `gradle assembleDebug` aqui com Android SDK 35.
