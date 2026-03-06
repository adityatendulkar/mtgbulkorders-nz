[Setup]
AppName=Card Optimiser
AppVersion=1.0.0
DefaultDirName={autopf}\Card Optimiser
DefaultGroupName=Card Optimiser
OutputDir=dist
OutputBaseFilename=CardOptimiserSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\CardOptimiser.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Card Optimiser"; Filename: "{app}\CardOptimiser.exe"
Name: "{autodesktop}\Card Optimiser"; Filename: "{app}\CardOptimiser.exe"

[Run]
Filename: "{app}\CardOptimiser.exe"; Description: "Launch Card Optimiser"; Flags: nowait postinstall skipifsilent
