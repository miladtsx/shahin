; NSIS installer script for packaging dist\Shahin (Shahin.exe + _internal)
; Requires NSIS (tested with MUI2)

!include "MUI2.nsh"

!define APP_NAME "Shahin"
!define APP_VERSION "1.0.0"
!define DIST_DIR "dist\Shahin"
!define EXE_NAME "Shahin.exe"

; Set installer icon
!define MUI_ICON "${DIST_DIR}\_internal\icon\icon.ico"

Name "${APP_NAME}"
OutFile "dist\\${APP_NAME}-Installer.exe"
InstallDir "$LOCALAPPDATA\\${APP_NAME}"
InstallDirRegKey HKCU "Software\\${APP_NAME}" "InstallDir"
RequestExecutionLevel user

VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_NAME}"
VIAddVersionKey "LegalCopyright" "© ${APP_NAME}"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE_NAME}"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Section "Shahin Application" SEC_APP
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "/oname=${EXE_NAME}" "${DIST_DIR}\\${EXE_NAME}"

  ; copy icon into install dir
  File "/oname=icon.ico" "${DIST_DIR}\_internal\\icon\\icon.ico"

  SetOutPath "$INSTDIR\\_internal"
  File /r "${DIST_DIR}\\_internal\\*"

  CreateShortCut "$SMPROGRAMS\\${APP_NAME}.lnk" "$INSTDIR\\${EXE_NAME}" "" "$INSTDIR\\icon.ico" 0
  CreateShortCut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${EXE_NAME}" "" "$INSTDIR\\icon.ico" 0

  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKCU "Software\\${APP_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "UninstallString" "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
SectionEnd

Section "AutoStart on login" SEC_AUTOSTART
  CreateShortCut "$SMSTARTUP\\${APP_NAME}.lnk" "$INSTDIR\\${EXE_NAME}" "" "$INSTDIR\\icon.ico" 0
SectionEnd

Section "Uninstall"
  Delete "$SMSTARTUP\\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\\${APP_NAME}.lnk"
  Delete "$DESKTOP\\${APP_NAME}.lnk"

  RMDir /r "$INSTDIR\\_internal"
  Delete "$INSTDIR\\${EXE_NAME}"
  Delete "$INSTDIR\\Uninstall.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "Software\\${APP_NAME}"
  DeleteRegKey HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}"
SectionEnd
