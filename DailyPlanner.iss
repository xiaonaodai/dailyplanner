#define MyAppName "DailyPlanner"
#define MyAppVersion "1.1.1"
#define MyAppExeName "DailyPlanner.exe"

[Setup]
AppId={{9D471F5A-8A42-4D7D-B23B-D3A8BC895BAD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
SetupIconFile=dailyplanner.ico
AppPublisher=Daily Planner
DefaultDirName={localappdata}\Programs\DailyPlanner
DefaultGroupName={cm:AppShortcutName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=release
OutputBaseFilename=DailyPlanner-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[CustomMessages]
english.AppShortcutName=DailyPlanner
chinesesimp.AppShortcutName=浠婃棩璁″垝
english.LaunchDescription=Launch DailyPlanner
chinesesimp.LaunchDescription=鍚姩浠婃棩璁″垝

[Files]
Source: "release\DailyPlanner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{cm:AppShortcutName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{cm:AppShortcutName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchDescription}"; Flags: postinstall nowait skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  LanguageFile: string;
  LanguageValue: string;
begin
  if CurStep = ssPostInstall then
  begin
    LanguageFile := ExpandConstant('{userappdata}\DailyPlanner\installer_language.txt');
    ForceDirectories(ExtractFileDir(LanguageFile));
    if ActiveLanguage = 'english' then
      LanguageValue := 'en'
    else
      LanguageValue := 'zh';
    if not SaveStringToFile(LanguageFile, LanguageValue, False) then
      RaiseException('Could not save the selected app language.');
  end;
end;

