; DriftLine — Inno Setup installer script
; Requires Inno Setup 6.x  →  https://jrsoftware.org/isinfo.php
;
; Run after PyInstaller:
;   pyinstaller build.spec
;   iscc installer\build.iss
;
; Output: installer\DriftLine_Setup.exe

#define AppName      "DriftLine"
#define AppVersion   "1.0.0"
#define AppPublisher "Laitrell Uy-Xayachak"
#define AppURL       "https://github.com/eyegetlucki/DriftLine"
#define AppExeName   "DriftLine.exe"
#define SourceDir    "..\dist\DriftLine"

[Setup]
AppId={{8F3A2E1B-4C7D-4F9A-B3E5-2D1A6C8F0E94}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
; Install to My Documents\DriftLine — always writable, no UAC required
DefaultDirName={userdocs}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; No UAC elevation needed (installs to user documents)
PrivilegesRequired=lowest
OutputDir=.
OutputBaseFilename=DriftLine_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
; Minimum OS: Windows 10
MinVersion=10.0
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut — checked by default, user can uncheck
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
; All PyInstaller output — copy everything in dist/DriftLine/
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; .env template — if user doesn't already have one
Source: "..\env.template"; DestDir: "{app}"; DestName: ".env.template"; Flags: ignoreversion

[Dirs]
; Create writable data directories on install
Name: "{app}\data"
Name: "{app}\data\sessions"
Name: "{app}\data\training"
Name: "{app}\models"

[Icons]
; Start Menu shortcut
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut — only created if user checked the task
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Open the .env.template after install so the user knows to fill in API keys
Filename: "notepad.exe"; Parameters: "{app}\.env.template"; \
    Description: "Open API key setup file"; \
    Flags: postinstall shellexec skipifsilent unchecked

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nDriftLine is a real-time AI voice co-driver for Assetto Corsa.%n%nAfter installation, copy your API keys into the .env file next to the exe.%n%nClick Next to continue.
FinishedHeadingLabel=DriftLine is installed.
FinishedLabel=After closing this window, open .env in the installation folder and paste in your ElevenLabs and Anthropic API keys. Then drop your trained model into the models/ folder and launch the app.%n%nLaunch DriftLine from your desktop or Start Menu.

[UninstallDelete]
; Clean up session data on uninstall (optional — comment out to keep data)
; Type: filesandordirs; Name: "{app}\data\sessions"
