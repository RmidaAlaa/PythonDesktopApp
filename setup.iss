; Script generated for AWG Kumulus Device Manager
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define MyAppName "AWG Kumulus Device Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AWG"
#define MyAppURL "https://www.awg.com"
#define MyAppExeName "AWG-Kumulus-Device-Manager.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{A1B2C3D4-E5F6-7890-1234-567890ABCDEF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; The "Required Components" page will be our custom page
DisableDirPage=no
DisableReadyPage=no
OutputBaseFilename=AWG-Kumulus-Installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Ensure admin rights for driver/prereq installation
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Application
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Prerequisites
; Visual C++ Redistributable
Source: "prerequisites\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: IsVCRedistNeeded

; Drivers
Source: "prerequisites\stlink\*"; DestDir: "{tmp}\stlink"; Flags: deleteafterinstall recursesubdirs createallsubdirs; Check: IsSTLinkNeeded
Source: "prerequisites\cp210x\*"; DestDir: "{tmp}\cp210x"; Flags: deleteafterinstall recursesubdirs createallsubdirs; Check: IsCP210xNeeded

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Install Prerequisites
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; Flags: waituntilterminated; Check: IsVCRedistNeeded; StatusMsg: "Installing Visual C++ Redistributable..."
Filename: "{tmp}\stlink\dpinst_amd64.exe"; Parameters: "/s"; Flags: waituntilterminated; Check: IsSTLinkNeeded; StatusMsg: "Installing ST-Link Drivers..."
Filename: "pnputil.exe"; Parameters: "/add-driver ""{tmp}\cp210x\silabser.inf"" /install"; Flags: waituntilterminated runhidden; Check: IsCP210xNeeded; StatusMsg: "Installing CP210x Drivers..."

; Launch Application
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DependencyPage: TWizardPage;
  CheckListBox: TNewCheckListBox;
  VCRedistNeeded: Boolean;
  STLinkNeeded: Boolean;
  CP210xNeeded: Boolean;
  VCRedistName: String;
  STLinkName: String;
  CP210xName: String;

procedure InitializeWizard;
var
  PageText: TNewStaticText;
begin
  VCRedistName := 'Visual C++ Redistributable 2015-2022';
  STLinkName := 'ST-Link USB Drivers';
  CP210xName := 'CP210x USB to UART Bridge';

  // Create the custom dependency page
  DependencyPage := CreateCustomPage(wpWelcome, 'Required Components', 'The following components are required for the application to function correctly.');
  
  PageText := TNewStaticText.Create(DependencyPage);
  PageText.Parent := DependencyPage.Surface;
  PageText.Caption := 'The installer has detected the following requirements. Click Next to install missing components automatically.';
  PageText.Left := 0;
  PageText.Top := 0;
  PageText.Width := DependencyPage.SurfaceWidth;
  PageText.Height := 40;
  PageText.WordWrap := True;

  CheckListBox := TNewCheckListBox.Create(DependencyPage);
  CheckListBox.Parent := DependencyPage.Surface;
  CheckListBox.Top := PageText.Top + PageText.Height + 10;
  CheckListBox.Left := 0;
  CheckListBox.Width := DependencyPage.SurfaceWidth;
  CheckListBox.Height := DependencyPage.SurfaceHeight - CheckListBox.Top;
  CheckListBox.Flat := True;
  CheckListBox.Color := clBtnFace;
  CheckListBox.BorderStyle := bsNone;
  CheckListBox.MinItemHeight := 24;
end;

// Check for Visual C++ Redistributable (x64)
function IsVCRedistNeeded: Boolean;
var
  RegKey: String;
  Version: Cardinal;
begin
  // Registry key for VC Redist 2015-2022 (x64)
  RegKey := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  if RegQueryDWordValue(HKEY_LOCAL_MACHINE, RegKey, 'Installed', Version) and (Version = 1) then
  begin
    Result := False;
  end
  else
  begin
    Result := True;
  end;
end;

// Check for ST-Link Drivers (Heuristic: Check for driver file or registry)
function IsSTLinkNeeded: Boolean;
begin
  // Simple check: Look for a known file or assume needed if not sure
  // For production, check: HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{...GUID...}
  // Here we assume it's needed if we can't find it.
  Result := not FileExists(ExpandConstant('{sys}\drivers\stlink_winusb.sys')); 
end;

// Check for CP210x Drivers
function IsCP210xNeeded: Boolean;
begin
  Result := not FileExists(ExpandConstant('{sys}\drivers\silabser.sys'));
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Index: Integer;
begin
  if CurPageID = DependencyPage.ID then
  begin
    CheckListBox.Clear;
    
    // Check status
    VCRedistNeeded := IsVCRedistNeeded();
    STLinkNeeded := IsSTLinkNeeded();
    CP210xNeeded := IsCP210xNeeded();

    // Add items with status
    if VCRedistNeeded then
      Index := CheckListBox.AddCheckBox(VCRedistName + ' (Missing)', '', 0, False, True, False, True, nil)
    else
      Index := CheckListBox.AddCheckBox(VCRedistName + ' (Installed)', '', 0, True, True, False, True, nil);
      
    if STLinkNeeded then
      Index := CheckListBox.AddCheckBox(STLinkName + ' (Missing)', '', 0, False, True, False, True, nil)
    else
      Index := CheckListBox.AddCheckBox(STLinkName + ' (Installed)', '', 0, True, True, False, True, nil);

    if CP210xNeeded then
      Index := CheckListBox.AddCheckBox(CP210xName + ' (Missing)', '', 0, False, True, False, True, nil)
    else
      Index := CheckListBox.AddCheckBox(CP210xName + ' (Installed)', '', 0, True, True, False, True, nil);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
end;
