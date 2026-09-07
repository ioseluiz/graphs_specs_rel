; SpecRel — Inno Setup script
; Instala en %APPDATA%\SpecRel sin requerir permisos de administrador.
; Recibe la versión desde CI: ISCC /DAppVersion=1.2.3 setup.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppName=SpecRel
AppVersion={#AppVersion}
AppPublisher=Autoridad del Canal de Panamá
DefaultDirName={userappdata}\SpecRel
DefaultGroupName=SpecRel
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=SpecRel_Setup_{#AppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SpecRel.exe
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\SpecRel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SpecRel"; Filename: "{app}\SpecRel.exe"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\SpecRel"; Filename: "{app}\SpecRel.exe"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Registry]
; Asociación de la extensión .specrel (por usuario)
Root: HKCU; Subkey: "Software\Classes\.specrel"; ValueType: string; ValueName: ""; ValueData: "SpecRel.Project"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\SpecRel.Project"; ValueType: string; ValueName: ""; ValueData: "Proyecto SpecRel"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SpecRel.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\assets\icon.ico"
Root: HKCU; Subkey: "Software\Classes\SpecRel.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SpecRel.exe"" ""%1"""

[Run]
Filename: "{app}\SpecRel.exe"; Description: "Iniciar SpecRel"; Flags: nowait postinstall skipifsilent
