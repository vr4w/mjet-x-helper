#define MyAppName "MJET-X Helper"
#define MyAppVersion "1.1.3"
#define MyAppPublisher "AE / Marvin Schoeffel"
#define MyAppExeName "MJETXHelper.exe"

[Setup]
AppId={{7D17B773-CA8D-4C6C-9C52-A34BE5856512}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\MJET-X Helper
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_dist
OutputBaseFilename=MJETXHelper_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Symbol auf dem Desktop erstellen"; GroupDescription: "Verknüpfungen:"; Flags: unchecked
Name: "startup"; Description: "MJET-X Helper automatisch mit Windows starten"; GroupDescription: "Autostart:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "data\reference_colors.json"; DestDir: "{app}\data"; Flags: ignoreversion
Source: "assets\mprint_logo.svg"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "helper_config.example.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent
