; Inno Setup Script for FPGA Studio (Spotify Dark Edition)
; Generates a professional Windows Setup Installer: FPGA_Studio_Setup_v4.2.exe

#define MyAppName "FPGA Studio"
#define MyAppVersion "4.2"
#define MyAppPublisher "FPGA Studio"
#define MyAppExeName "FPGA Studio.exe"
#define SourceDir "C:\Users\poswe\.gemini\antigravity\scratch\mips-fpga-plan\fpga_studio"

[Setup]
AppId={{5F8D3491-912A-4C2E-8E28-76A6C7B2F6E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir={#SourceDir}\installer_output
OutputBaseFilename=FPGA_Studio_Setup_v4.2
SetupIconFile={#SourceDir}\app_icon.ico
UninstallDisplayIcon={app}\app_icon.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main application binaries from dist\FPGA Studio
Source: "{#SourceDir}\dist\FPGA Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Built-in 32-bit FPGA CPUs (OpenMIPS & Synthesizable RISC-V RV32IM only — no user custom CPUs)
Source: "{#SourceDir}\custom_cpus\openmips\*"; DestDir: "{app}\custom_cpus\openmips"; Excludes: "cpu_manifest.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\custom_cpus\riscv\*"; DestDir: "{app}\custom_cpus\riscv"; Excludes: "cpu_manifest.json"; Flags: ignoreversion recursesubdirs createallsubdirs
; xPack GCC 15.2 toolchain & openFPGALoader (Direct JTAG In-App Flasher)
Source: "{#SourceDir}\toolchain\*"; DestDir: "{app}\toolchain"; Flags: ignoreversion recursesubdirs createallsubdirs
; Pre-bundled hardware CPU Bitstreams (OpenMIPS, RISC-V, Nexys A7 Demo - No Vivado needed!)
Source: "{#SourceDir}\bitstreams\*"; DestDir: "{app}\bitstreams"; Flags: ignoreversion recursesubdirs createallsubdirs
; Application icon
Source: "{#SourceDir}\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\app_icon.png"; DestDir: "{app}"; Flags: ignoreversion
; Fonts (if any)
Source: "{#SourceDir}\fonts\*"; DestDir: "{app}\fonts"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: WORKSPACE IS EXCLUDED AS REQUESTED! The application creates a clean workspace upon first launch.

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
