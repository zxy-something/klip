# Klip

Gravador de tela para Windows inspirado no OBS: monte cenas com fontes de vídeo e grave em MP4.

## Recursos

- Fontes de tela, janela, câmera, imagem e texto
- Cenas com posicionamento e dimensionamento das fontes
- Microfone e áudio do sistema, com medidor de nível e mute
- Gravação em MP4, com resolução, FPS e qualidade configuráveis
- Atalho **F9** para iniciar/parar a gravação

## Instalação

### Chocolatey

```powershell
choco install klip
```

### Portátil

Baixe `Klip.exe` em [Releases](https://github.com/zxy-something/klip/releases) e execute. Não precisa instalar.

Requisitos: Windows 10/11 (64 bits).

## Compilar do código

```powershell
python -m pip install -r requirements.txt pyinstaller
build.bat
```

O executável é gerado em `dist\Klip.exe`.

## Licença

[MIT](LICENSE)
