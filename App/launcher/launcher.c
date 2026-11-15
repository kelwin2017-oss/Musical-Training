/*
 * Musical Training — iniciador
 * Abre App\iniciar.bat a partir da pasta onde este .exe está.
 * Existe só para o app ter um ícone fixo que funciona em qualquer PC
 * (atalhos .lnk guardam caminhos absolutos e quebram ao baixar do GitHub).
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE h, HINSTANCE p, PWSTR cmd, int show) {
    wchar_t dir[MAX_PATH], app[MAX_PATH], bat[MAX_PATH];
    DWORD n = GetModuleFileNameW(NULL, dir, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return 1;
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) *slash = 0;

    swprintf(app, MAX_PATH, L"%ls\\App", dir);
    swprintf(bat, MAX_PATH, L"%ls\\iniciar.bat", app);

    if (GetFileAttributesW(bat) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
            L"Não encontrei a pasta App\\iniciar.bat ao lado deste programa.\n\n"
            L"Mantenha o \"Musical Training.exe\" na mesma pasta que a pasta \"App\".",
            L"Musical Training", MB_OK | MB_ICONERROR);
        return 2;
    }
    HINSTANCE r = ShellExecuteW(NULL, L"open", bat, NULL, app, SW_SHOWNORMAL);
    if ((INT_PTR)r <= 32) {
        MessageBoxW(NULL, L"Não consegui abrir o App\\iniciar.bat.", L"Musical Training", MB_OK | MB_ICONERROR);
        return 3;
    }
    return 0;
}
