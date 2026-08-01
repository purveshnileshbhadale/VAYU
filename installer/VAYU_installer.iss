; VAYU Installer for Windows
; Requires Inno Setup 6+ (https://jrsoftware.org/isdl.php)

#define MyAppName "VAYU"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Purvesh Nilesh Bhadale"
#define MyAppURL "https://website-seven-neon-48.vercel.app"
#define MyAppExeName "VAYU.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=VAYU_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\vayu.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "autostart"; Description: "&Launch VAYU on Windows startup"; GroupDescription: "Startup options:"

[Files]
Source: "..\dist\VAYU\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch VAYU now"; Flags: postinstall nowait skipifsilent shellexec
Filename: "reg"; Parameters: "add HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v VAYU /t REG_SZ /d ""{app}\{#MyAppExeName} --minimized"" /f"; Flags: runhidden; Tasks: autostart

[UninstallRun]
Filename: "reg"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v VAYU /f"; Flags: runhidden

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if IsTaskSelected('autostart') then
    begin
      Log('Auto-start registry entry added');
    end;
  end;
end;
