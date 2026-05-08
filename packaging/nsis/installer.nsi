; packaging/nsis/installer.nsi
; Build: makensis packaging/nsis/installer.nsi
; (requires dist/ucbtool-gui and dist/ucbtool-cli produced by PyInstaller)

!define APPNAME "UCB Tool"
!define EXECUTABLE "ucbtool-gui.exe"
!define VERSION "0.1.0"

Name "${APPNAME} ${VERSION}"
OutFile "..\..\dist\ucbtool-setup.exe"
InstallDir "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey HKLM "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel admin

Page license
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

LicenseData "LICENSE.txt"

Section "Install"
  SetOutPath "$INSTDIR\gui"
  File /r "..\..\dist\ucbtool-gui\*"
  SetOutPath "$INSTDIR\cli"
  File /r "..\..\dist\ucbtool-cli\*"
  CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\gui\${EXECUTABLE}"
  WriteRegStr HKLM "Software\${APPNAME}" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Add CLI to PATH (user choice)
  EnVar::AddValue "Path" "$INSTDIR\cli"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$INSTDIR\gui"
  RMDir /r "$INSTDIR\cli"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "Software\${APPNAME}"
  EnVar::DeleteValue "Path" "$INSTDIR\cli"
SectionEnd
