# horipad-batery-monitor

Mostra a bateria do **HORIPAD Steam** direto na barra de tarefas do Windows 11, ao lado da área de notificação.

## Por quê

O controle não informa a bateria pelo Bluetooth padrão do Windows: a propriedade de bateria do dispositivo fica vazia. Por isso ela não aparece em Configurações nem em apps como o BatteryHub. O Steam lê a bateria pelo driver HIDAPI do [SDL](https://github.com/libsdl-org/SDL), e este script faz a mesma coisa com o SDL3.

## Como funciona

- Lê a bateria via `SDL_GetJoystickPowerInfo` e atualiza a partir dos eventos do SDL (controle conectou, desconectou ou bateria mudou), verificados a cada 1 s. O HORIPAD desliga e religa sozinho por inatividade, então isso importa.
- Desenha uma janela filha do `Shell_TrayWnd`, encostada à esquerda da área de notificação e de outros widgets que já estejam ali. A janela é *layered*, senão a camada XAML da barra do Windows 11 a cobre.
- Cores: branco normal · vermelho ≤ 20% · azul carregando · cinza desconectado.
- Clique direito: **Atualizar** / **Sair**.

Ajustes no topo do script: `PUMP_MS`, `LOW_PCT`, `WIDTH`, `GAP`.

## Instalação

Requer Python 3.11+ no Windows 11.

```powershell
pip install -r requirements.txt
pythonw horipad_battery.pyw
```

Na primeira execução, o PySDL3 baixa a DLL do SDL3 (~2 MB).

### Iniciar com o Windows

Cria um atalho na pasta Inicializar:

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Startup'))\Horipad Battery.lnk")
$s.TargetPath = (Get-Command pythonw).Source
$s.Arguments = "`"$PWD\horipad_battery.pyw`""
$s.WorkingDirectory = "$PWD"
$s.Save()
```

Para remover, apague `Horipad Battery.lnk` em `shell:startup`.

## Limitações

- Testado só com o HORIPAD Steam via Bluetooth (VID `0F0D`). Outros controles suportados pelo SDL devem funcionar se você trocar `NAME_MATCH`.
- A posição é recalculada a cada 2 s. Ainda não foi testado o que acontece quando o Explorer reinicia; se o widget sumir, rode o script de novo.
