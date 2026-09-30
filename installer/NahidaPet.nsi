; ============================================================
;  纳西妲桌宠 Nahida Pet —— NSIS 安装包脚本
;  产物：dist\NahidaPet-Setup-1.0.0.exe
;  编译：build\..\nsis\makensis.exe NahidaPet.nsi
;  特性：免管理员权限（装到 %LOCALAPPDATA%\Programs）、
;        开始菜单 + 可选桌面快捷方式、可选开机自启、
;        标准卸载项（控制面板可卸载）、卸载时可选清理个人配置。
; ============================================================

Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; 工程根目录：由构建脚本以绝对路径传入；手工编译时请在 installer 目录下执行
!ifndef SRCROOT
  !define SRCROOT ".."
!endif

; ---------------- 产品信息 ----------------
!define PRODUCT_NAME      "纳西妲桌宠"
!define PRODUCT_NAME_EN   "Nahida Pet"
!define PRODUCT_VERSION   "1.0.1"
!define PRODUCT_PUBLISHER "Nahida Desktop Pet"
!define PRODUCT_EXE       "NahidaPet.exe"
!define PRODUCT_README    "使用说明.txt"
!define PRODUCT_UNINST    "Uninstall.exe"
!define UNINST_KEY        "Software\Microsoft\Windows\CurrentVersion\Uninstall\NahidaPet"
!define AUTORUN_KEY       "Software\Microsoft\Windows\CurrentVersion\Run"
!define AUTORUN_VALUE     "NahidaPet"

!define PAYLOAD            "${SRCROOT}\installer\build_dist\NahidaPet.exe"
!define ICON_FILE          "${SRCROOT}\assets\icon.ico"
!define README_FILE        "${SRCROOT}\installer\使用说明.txt"
!define LICENSE_FILE       "${SRCROOT}\installer\LICENSE.txt"
!define OUT_DIR            "${SRCROOT}\installer\dist"

; ---------------- 基本信息 ----------------
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
BrandingText "${PRODUCT_NAME_EN} ${PRODUCT_VERSION} · 安装向导"
!ifdef TESTBUILD
  OutFile "${OUT_DIR}\_selftest-setup.exe"
!else
  OutFile "${OUT_DIR}\NahidaPet-Setup-${PRODUCT_VERSION}.exe"
!endif
InstallDir "$LOCALAPPDATA\Programs\NahidaPet"
InstallDirRegKey HKCU "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel user            ; 全程 HKCU / 用户目录，不弹 UAC
SetCompressor /SOLID lzma
SetCompressorDictSize 48
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=2052 "ProductName"     "${PRODUCT_NAME} ${PRODUCT_NAME_EN}"
VIAddVersionKey /LANG=2052 "FileDescription" "${PRODUCT_NAME} 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion"     "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=2052 "ProductVersion"  "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=2052 "CompanyName"     "${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=2052 "LegalCopyright"  "仅供个人学习交流使用"

; ---------------- 界面 ----------------
!define MUI_ABORTWARNING
!define MUI_ICON   "${ICON_FILE}"
!define MUI_UNICON "${ICON_FILE}"

!define MUI_WELCOMEPAGE_TITLE "欢迎安装 ${PRODUCT_NAME} ${PRODUCT_VERSION}"
!define MUI_WELCOMEPAGE_TEXT "接下来，桌面上会多一位从须弥来的小客人。$\r$\n$\r$\n她会在你的桌面角落里发呆、打瞌睡，也会在你摸她头的时候脸红。右键点她，可以喂点心、讲故事、猜谜语，还能和你聊天（需要自己填一个 AI 接口的 API Key）。$\r$\n$\r$\n整个安装不需要管理员权限，也不会动你系统里的其它东西。$\r$\n$\r$\n点「下一步」开始吧。"

!define MUI_DIRECTORYPAGE_TEXT_TOP "把她安置在哪个文件夹？默认装在当前用户目录下，之后想挪走也很方便。"
!define MUI_COMPONENTSPAGE_TEXT_TOP "选择要一并完成的动作，主程序是必须安装的。"
!define MUI_INSTFILESPAGE_COLORS "3C7A3C D8ECD8"
!define MUI_FINISHPAGE_TITLE "纳西妲已经住进来啦"
!define MUI_FINISHPAGE_TEXT "安装完成。$\r$\n$\r$\n第一次运行后请留意右下角托盘区域——她就在桌面上，右键可以打开菜单。$\r$\n聊天功能需要先填 API Key：右键 -> AI 设置，选一个服务商粘贴 Key 即可。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "现在就让纳西妲出来（推荐）"
!define MUI_FINISHPAGE_LINK "查看使用说明"
!define MUI_FINISHPAGE_LINK_LOCATION "$INSTDIR\${PRODUCT_README}"

!define MUI_UNCONFIRMPAGE_TEXT_TOP "确认要送纳西妲回须弥吗？程序会从你的电脑上被移除。"
!define MUI_UNFINISHPAGE_NOAUTOCLOSE

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSE_FILE}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ---------------- 运行中的程序处理 ----------------
; 静默结束可能正在运行的桌宠；输出重定向到 nul，
; 避免用户在安装日志里看到「错误: 没有找到进程」这种吓人的提示。
Function KillRunningApp
  DetailPrint "检查是否有正在运行的纳西妲桌宠……"
  nsExec::Exec 'cmd /c taskkill /F /T /IM "${PRODUCT_EXE}" >nul 2>&1'
  Pop $0
  ${If} $0 = 0
    DetailPrint "发现正在运行的桌宠，已帮她退场，稍后重新见面。"
    Sleep 600
  ${EndIf}
  nsExec::Exec 'cmd /c taskkill /F /T /IM "纳西妲桌宠.exe" >nul 2>&1'
  Pop $0
  Sleep 300
FunctionEnd

Function un.KillRunningApp
  nsExec::Exec 'cmd /c taskkill /F /T /IM "${PRODUCT_EXE}" >nul 2>&1'
  Pop $0
  ${If} $0 = 0
    DetailPrint "发现正在运行的桌宠，已帮她退场。"
    Sleep 600
  ${EndIf}
  nsExec::Exec 'cmd /c taskkill /F /T /IM "纳西妲桌宠.exe" >nul 2>&1'
  Pop $0
  Sleep 300
FunctionEnd

; ============================================================
;  安装
; ============================================================
Section "主程序（必需）" SEC_MAIN
  SectionIn RO
  SetOutPath "$INSTDIR"
  SetOverwrite on

  Call KillRunningApp

  File "/oname=${PRODUCT_EXE}" "${PAYLOAD}"
  File "/oname=${PRODUCT_README}" "${README_FILE}"
  File "/oname=LICENSE.txt" "${LICENSE_FILE}"

!ifndef TESTBUILD   ; 自检构建：只解包，不写快捷方式与注册表
  ; 卸载程序
  WriteUninstaller "$INSTDIR\${PRODUCT_UNINST}"

  ; 开始菜单（固定创建，便于找回）
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0 SW_SHOWNORMAL "" "在桌面上养一只草神"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_README}.lnk" "$INSTDIR\${PRODUCT_README}" "" "$INSTDIR\${PRODUCT_EXE}" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_UNINST}"

  ; 记录安装信息（控制面板/设置里可卸载）
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayName"     "${PRODUCT_NAME} (${PRODUCT_NAME_EN})"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayVersion"  "${PRODUCT_VERSION}"
  WriteRegStr   HKCU "${UNINST_KEY}" "Publisher"       "${PRODUCT_PUBLISHER}"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${PRODUCT_EXE},0"
  WriteRegStr   HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\${PRODUCT_UNINST}"'
  WriteRegStr   HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\${PRODUCT_UNINST}" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
!endif
SectionEnd

Section "创建桌面快捷方式" SEC_DESKTOP
!ifndef TESTBUILD
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0 SW_SHOWNORMAL "" "在桌面上养一只草神"
!endif
SectionEnd

Section /o "开机自动启动" SEC_AUTORUN
!ifndef TESTBUILD
  WriteRegStr HKCU "${AUTORUN_KEY}" "${AUTORUN_VALUE}" '"$INSTDIR\${PRODUCT_EXE}"'
!endif
SectionEnd

Section -Post
!ifndef TESTBUILD
  ; 统计占用体积写入注册表
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"
!endif
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_MAIN}    "纳西妲桌宠主程序，以及开始菜单里的快捷方式。（必需）"
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} "在桌面上放一个纳西妲的图标，双击就能叫她出来。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_AUTORUN} "开机后自动让纳西妲出现在桌面上（写入当前用户启动项，可随时注销）。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ============================================================
;  卸载
; ============================================================
Section "Uninstall"
  Call un.KillRunningApp

  Delete "$INSTDIR\${PRODUCT_EXE}"
  Delete "$INSTDIR\${PRODUCT_README}"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\${PRODUCT_UNINST}"

  ; 仅当确实是我们的安装目录时才连目录一起删除，避免误删
  IfFileExists "$INSTDIR\${PRODUCT_EXE}" 0 no_rmdir
  RMDir /r "$INSTDIR"
  Goto rmdir_done
no_rmdir:
  RMDir "$INSTDIR"
rmdir_done:

  ; 兜底：若仍有残留（卸载器自身未退出 / 主程序被占用没能删掉），
  ; 交给一个分离的延迟进程在卸载器退出后清理，避免留下空壳目录。
  ; 注意先 cd 到 %TEMP%：Windows 不允许删除进程当前的工作目录。
  IfFileExists "$INSTDIR\*.*" 0 cleanup_done
  ExecShell "" "cmd.exe" '/c cd /d "%TEMP%" & ping -n 3 127.0.0.1 >nul & rmdir /s /q "$INSTDIR"' SW_HIDE
cleanup_done:

  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_README}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ${PRODUCT_NAME}.lnk"
  RMDir  "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"

  DeleteRegValue HKCU "${AUTORUN_KEY}" "${AUTORUN_VALUE}"
  DeleteRegKey   HKCU "${UNINST_KEY}"

  ; 个人配置（AI Key 等）单独询问，默认保留
  IfFileExists "$PROFILE\.nahida_pet\*.*" 0 skip_cfg
  MessageBox MB_YESNO|MB_ICONQUESTION "是否一并删除她的记忆（个人配置与 AI Key）？$\r$\n$\r$\n路径：$PROFILE\.nahida_pet$\r$\n选择「否」则保留，以后重装还能接着聊。" /SD IDNO IDYES del_cfg IDNO skip_cfg
del_cfg:
  RMDir /r "$PROFILE\.nahida_pet"
skip_cfg:
SectionEnd
