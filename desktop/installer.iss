#ifndef AppVersion
#define AppVersion "0.2.0"
#endif

[Setup]
AppId={{59ACC534-B377-4A98-B6AB-55417EF5DE7B}
AppName=Benefit Design Stress Lab
AppVersion={#AppVersion}
AppPublisher=QBranch800
DefaultDirName={autopf}\Benefit Design Stress Lab
DefaultGroupName=Benefit Design Stress Lab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=BenefitDesignStressLab-Setup
#if FileExists(AddBackslash(SourcePath) + "icon.ico")
SetupIconFile=icon.ico
#endif
UninstallDisplayIcon={app}\Benefit Design Stress Lab.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Benefit Design Stress Lab\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Benefit Design Stress Lab"; Filename: "{app}\Benefit Design Stress Lab.exe"
Name: "{autodesktop}\Benefit Design Stress Lab"; Filename: "{app}\Benefit Design Stress Lab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Benefit Design Stress Lab.exe"; Description: "Launch Benefit Design Stress Lab"; Flags: nowait postinstall skipifsilent
