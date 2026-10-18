; Inno Setup Script for MyRemotePC Commercial Installer
#define MyAppName "MyRemotePC"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MyRemotePC"
#define MyAppURL "https://github.com/kidkingstrange/myremotepc"
#define MyAppExeName "MyRemotePC.exe"

[Setup]
AppId={{D37E88D6-A782-4C72-8C49-E86B7C3782A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=dist\releases\v1.0.0
OutputBaseFilename=MyRemotePC-Setup-v1.0.0
SetupIconFile=static\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Automatically start MyRemotePC on Windows boot"; GroupDescription: "Windows Integration:"

[Files]
Source: "dist\MyRemotePC.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.example.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "open_viewer.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "share_over_internet.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "static\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: startupicon; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
