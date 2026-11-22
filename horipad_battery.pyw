"""Widget na barra de tarefas com a bateria do Horipad Steam (lida via SDL3, igual ao Steam).

Mesmo truque do BatteryHub: uma janela filha do Shell_TrayWnd, encostada à esquerda
da área de notificação (e de outros widgets que já estejam lá).
"""
import ctypes
import ctypes.wintypes as w
import os
import subprocess
import sys
import tkinter as tk

import sdl3

NAME_MATCH = b"HORIPAD"
PUMP_MS = 1_000       # leitura dos eventos do SDL (conectou/desconectou/bateria mudou)
PLACE_MS = 2_000      # reposiciona (explorer reiniciou, outro widget mudou de tamanho)
LOW_PCT = 20
WIDTH = 72
GAP = 2               # px entre o widget e o vizinho da direita
ICON = ""       # gamepad na Segoe Fluent Icons
KEY, KEY_RGB = "#010203", 0x030201  # cor de fundo que vira transparente (COLORREF = 0x00BBGGRR)

u32 = ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)


def rect(h):
    r = w.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def taskbar_anchor(own):
    """(hwnd da barra, x da borda esquerda do vizinho mais à esquerda na área direita, rect da barra)."""
    tb = u32.FindWindowW("Shell_TrayWnd", None)
    if not tb:
        return None
    tbr = rect(tb)
    mid = (tbr[0] + tbr[2]) // 2
    lefts = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, _):
        cls = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(h, cls, 64)
        r = rect(h)
        # vizinhos: área de notificação e widgets de terceiros (ex.: BatteryHub)
        if (h != own and u32.IsWindowVisible(h) and u32.GetParent(h) == tb
                and r[0] > mid and r[2] - r[0] < 600):
            lefts.append(r[0])
        return True

    u32.EnumChildWindows(tb, cb, 0)
    return tb, min(lefts, default=tbr[2]), tbr


class Widget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        self.icon = tk.Label(self.root, text=ICON, font=("Segoe Fluent Icons", 13), bg=KEY)
        self.text = tk.Label(self.root, text="--", font=("Segoe UI", 11), bg=KEY)
        self.icon.pack(side="left", padx=(6, 4))
        self.text.pack(side="left")

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Atualizar", command=self.refresh)
        menu.add_command(label="Sair", command=self.root.destroy)
        for wdg in (self.root, self.icon, self.text):
            wdg.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        self.root.update()
        self.hwnd = u32.GetAncestor(self.root.winfo_id(), 2)  # GA_ROOT
        u32.SetWindowLongW(self.hwnd, -16, 0x54000000)  # WS_CHILD|WS_VISIBLE|WS_CLIPSIBLINGS
        # layered: sem isso a camada XAML da barra cobre a janela; color key deixa o fundo transparente
        u32.SetWindowLongW(self.hwnd, -20, 0x08080000)  # WS_EX_NOACTIVATE|WS_EX_LAYERED
        u32.SetLayeredWindowAttributes(self.hwnd, KEY_RGB, 0, 1)  # LWA_COLORKEY
        self.parent = None
        self.handles = {}  # instance id -> SDL_Joystick*

        sdl3.SDL_SetHint(b"SDL_JOYSTICK_HIDAPI_STEAM_HORI", b"1")
        sdl3.SDL_Init(sdl3.SDL_INIT_JOYSTICK)  # dispara ADDED para quem já está conectado
        self.event = sdl3.SDL_Event()
        self.refresh()
        self.place()
        self.pump()

    def place(self):
        if self.parent and not u32.IsWindow(self.hwnd):
            # Explorer reiniciou e destruiu a janela junto com a barra antiga:
            # quando a nova barra existir, reabre o script do zero.
            if u32.FindWindowW("Shell_TrayWnd", None):
                subprocess.Popen([sys.executable, *sys.argv])
                os._exit(0)
            self.root.after(PLACE_MS, self.place)
            return
        a = taskbar_anchor(self.hwnd)
        if a:
            tb, right, tbr = a
            if self.parent != tb:  # primeira vez ou explorer reiniciou
                u32.SetParent(self.hwnd, tb)
                self.parent = tb
            h = tbr[3] - tbr[1]
            # coordenadas relativas à barra
            # HWND_TOP: acima da camada XAML da barra
            u32.SetWindowPos(self.hwnd, 0, right - tbr[0] - WIDTH - GAP, 0, WIDTH, h, 0x0040)  # SWP_SHOWWINDOW
        self.root.after(PLACE_MS, self.place)

    def pump(self):
        """Processa os eventos do SDL: o controle desliga/religa sozinho por inatividade."""
        changed = False
        while sdl3.SDL_PollEvent(ctypes.byref(self.event)):
            t, ev = self.event.type, self.event
            if t == sdl3.SDL_EVENT_JOYSTICK_ADDED:
                jid = ev.jdevice.which
                if NAME_MATCH in (sdl3.SDL_GetJoystickNameForID(jid) or b"").upper():
                    self.handles[jid] = sdl3.SDL_OpenJoystick(jid)
                    changed = True
            elif t == sdl3.SDL_EVENT_JOYSTICK_REMOVED:
                if (js := self.handles.pop(ev.jdevice.which, None)):
                    sdl3.SDL_CloseJoystick(js)
                    changed = True
            elif t == sdl3.SDL_EVENT_JOYSTICK_BATTERY_UPDATED:
                changed |= ev.jbattery.which in self.handles
        if changed:
            self.refresh()
        self.root.after(PUMP_MS, self.pump)

    def refresh(self):
        if not self.handles:
            label, color = "--", "#888888"
        else:
            pct = ctypes.c_int(-1)
            state = sdl3.SDL_GetJoystickPowerInfo(next(iter(self.handles.values())), ctypes.byref(pct))
            charging = state in (sdl3.SDL_POWERSTATE_CHARGING, sdl3.SDL_POWERSTATE_CHARGED)
            low = 0 <= pct.value <= LOW_PCT and not charging
            label = f"{pct.value}%" if pct.value >= 0 else "..."  # aguardando 1º relatório
            color = "#4aa3ff" if charging else "#ff5555" if low else "#ffffff"
        self.text.configure(text=label, fg=color)
        self.icon.configure(fg=color)

    def run(self):
        self.root.mainloop()
        sdl3.SDL_Quit()


if __name__ == "__main__":
    Widget().run()
