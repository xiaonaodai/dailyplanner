import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, colorchooser
from datetime import datetime
import json
import os
import shutil
import threading
import ctypes.wintypes


APP_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "DailyPlanner")
os.makedirs(USER_DATA_DIR, exist_ok=True)
for data_name in ("schedule.json", "settings.json"):
    user_data_path = os.path.join(USER_DATA_DIR, data_name)
    bundled_data_path = os.path.join(APP_DIR, data_name)
    if not os.path.exists(user_data_path) and os.path.exists(bundled_data_path):
        try:
            shutil.copy2(bundled_data_path, user_data_path)
        except OSError:
            pass
DATA_FILE = os.path.join(USER_DATA_DIR, "schedule.json")
SETTINGS_FILE = os.path.join(USER_DATA_DIR, "settings.json")
LANGUAGE_FILE = os.path.join(USER_DATA_DIR, "installer_language.txt")
DEFAULTS = [
    {"start": "09:00", "end": "10:30", "task": "专注工作", "next": "休息 10 分钟"},
    {"start": "10:40", "end": "12:00", "task": "继续工作", "next": "午休时间"},
    {"start": "13:30", "end": "15:00", "task": "下午计划", "next": "休息 10 分钟"},
]

PAPER = "#FFF9D8"
TOP = "#FFF2BD"
INK = "#393528"
MUTED = "#81754E"
ACCENT = "#A66B1C"
LINE = "#E8DCA7"
EDGE = "#D8C98D"
ACTIVE = "#FFF4C9"
WHITE = "#FFFCED"
FONT = "Microsoft YaHei UI"


def mix_color(first, second, amount):
    a = tuple(int(first[i:i+2], 16) for i in (1, 3, 5))
    b = tuple(int(second[i:i+2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b))


def set_palette(base, frame_color=None):
    global PAPER, TOP, INK, MUTED, ACCENT, LINE, EDGE, ACTIVE, WHITE
    PAPER = base.upper()
    rgb = tuple(int(PAPER[i:i+2], 16) for i in (1, 3, 5))
    luminance = sum(channel * weight for channel, weight in zip(rgb, (0.2126, 0.7152, 0.0722))) / 255
    shade = "#000000" if luminance > 0.52 else "#FFFFFF"
    TOP = frame_color.upper() if frame_color else PAPER
    EDGE = frame_color.upper() if frame_color else PAPER
    LINE = mix_color(PAPER, shade, 0.12)
    ACTIVE = PAPER
    WHITE = mix_color(PAPER, "#FFFFFF", 0.20)
    INK = "#292929" if luminance > 0.40 else "#FFF9E8"
    MUTED = mix_color(INK, PAPER, 0.38)
    ACCENT = "#986019" if luminance > 0.40 else "#FFE09A"

def parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


class TimeWheel(tk.Canvas):
    def __init__(self, parent, value, maximum):
        super().__init__(parent, width=58, height=112, bg=WHITE, highlightthickness=0,
                         cursor="hand2", takefocus=True)
        self.value = value
        self.maximum = maximum
        self.drag_y = None
        self.drag_moved = False
        self.drag_remainder = 0
        self.draw()
        self.bind("<ButtonPress-1>", self.press)
        self.bind("<B1-Motion>", self.move)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<MouseWheel>", self.mousewheel)
        self.bind("<Button-4>", lambda event: self.step(1))
        self.bind("<Button-5>", lambda event: self.step(-1))
        self.bind("<Up>", lambda event: self.step(1))
        self.bind("<Down>", lambda event: self.step(-1))

    def get(self):
        return self.value

    def step(self, amount):
        if not amount:
            return
        self.value = (self.value + amount) % (self.maximum + 1)
        self.draw()

    def draw(self):
        self.delete("all")
        self.create_rectangle(1, 37, 57, 75, fill=PAPER, outline=LINE, width=1)
        previous = (self.value - 1) % (self.maximum + 1)
        following = (self.value + 1) % (self.maximum + 1)
        self.create_text(29, 19, text=f"{previous:02d}", fill=MUTED,
                         font=("Segoe UI", 10))
        self.create_text(29, 56, text=f"{self.value:02d}", fill=INK,
                         font=("Segoe UI", 20, "bold"))
        self.create_text(29, 93, text=f"{following:02d}", fill=MUTED,
                         font=("Segoe UI", 10))

    def press(self, event):
        self.drag_y = event.y
        self.press_y = event.y
        self.drag_moved = False
        self.drag_remainder = 0

    def move(self, event):
        if self.drag_y is None:
            return
        if abs(event.y - self.press_y) > 4:
            self.drag_moved = True
        delta = self.drag_y - event.y
        self.drag_remainder += delta
        steps = int(self.drag_remainder / 20)
        if steps:
            self.step(steps)
            self.drag_remainder -= steps * 20
        self.drag_y = event.y

    def release(self, event):
        released_inside = (0 <= event.x < self.winfo_width() and
                           0 <= event.y < self.winfo_height())
        if released_inside and not self.drag_moved:
            if event.y < 37:
                self.step(-1)
            elif event.y > 75:
                self.step(1)
        self.drag_y = None
        self.drag_moved = False

    def mousewheel(self, event):
        if event.delta:
            self.step(1 if event.delta > 0 else -1)

class TimerNote:
    def __init__(self, root):
        self.root = root
        self.root.title("今日计划")
        self.root.overrideredirect(True)
        self.root.configure(bg=PAPER)
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = min(760, max(600, screen_w - 80)), min(860, max(700, screen_h - 100))
        x, y = max(0, (screen_w - width) // 2), max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(600, 700)
        self.saved_window_geometry = None
        self._settings_after = None
        self.settings_file = SETTINGS_FILE
        self.base_color = "#FFF2B8"
        self.frame_color = None
        self.language = "zh"
        self.language_var = tk.StringVar(master=self.root, value="zh")
        self.layout_defaults = {
            "clock": [0.05, 0.0, 0.90, 0.06],
            "summary": [0.04, 0.09, 0.55, 0.38],
            "dial": [0.60, 0.09, 0.34, 0.38],
            "listbox": [0.05, 0.49, 0.90, 0.51],
        }
        self.layout = {name: values.copy() for name, values in self.layout_defaults.items()}
        self.layout_mode = False
        self.layout_bindings = []
        self.layout_drag = None
        try:
            with open(self.settings_file, "r", encoding="utf-8") as file:
                saved = json.load(file)
            paper = saved.get("paper_color", self.base_color)
            frame = saved.get("frame_color")
            if isinstance(paper, str) and len(paper) == 7 and paper.startswith("#"):
                int(paper[1:], 16)
                self.base_color = paper
            if isinstance(frame, str) and len(frame) == 7 and frame.startswith("#"):
                int(frame[1:], 16)
                self.frame_color = frame
            if saved.get("language") in ("zh", "en"):
                self.language = saved["language"]
                self.language_var.set(self.language)
            try:
                with open(LANGUAGE_FILE, "r", encoding="utf-8") as language_file:
                    install_language = language_file.read().strip()
                if install_language in ("zh", "en"):
                    self.language = install_language
                    self.language_var.set(install_language)
            except OSError:
                pass
            saved_window = saved.get("window_geometry")
            if isinstance(saved_window, list) and len(saved_window) == 4:
                try:
                    saved_x, saved_y, saved_width, saved_height = map(int, saved_window)
                    if saved_width >= 600 and saved_height >= 700:
                        self.saved_window_geometry = [saved_x, saved_y, saved_width, saved_height]
                except (TypeError, ValueError):
                    pass
            saved_layout = saved.get("layout", {})
            if isinstance(saved_layout, dict):
                for name, rect in saved_layout.items():
                    if name not in self.layout or not isinstance(rect, list) or len(rect) != 4:
                        continue
                    try:
                        x, y, width, height = map(float, rect)
                    except (TypeError, ValueError):
                        continue
                    width = min(width, {"clock": 0.90, "summary": 0.64, "dial": 0.34, "listbox": 0.90}[name])
                    x = min(x, 1.0 - width)
                    if (0 <= x < 1 and 0 <= y < 1 and width > 0 and 0 < height <= 1
                            and y + height <= 1.001):
                        self.layout[name] = [x, y, width, height]
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        if self.saved_window_geometry:
            saved_x, saved_y, saved_width, saved_height = self.saved_window_geometry
            width = min(saved_width, screen_w)
            height = min(saved_height, screen_h)
            x = min(max(0, saved_x), max(0, screen_w - width))
            y = min(max(0, saved_y), max(0, screen_h - height))
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        set_palette(self.base_color, self.frame_color)
        self.root.attributes("-topmost", True)
        self.plans = self.load()
        self.selected_plans = set()
        self.selection_mode = False
        self.pin = tk.BooleanVar(value=True)
        self.notified = set()
        self.last_tick = datetime.now()
        self.rendered_minute = None
        self.toast = None
        self.dial_items = None
        self.ring_photo = None
        self.ring_fallback_items = None
        self.last_ring_visual = None
        self.last_fraction = 0
        self.list_signature = None
        self.list_rows = []
        self.palette_window = None
        self.palette_swatches = {}
        self._picker_active = False
        self._picker_mouse_was_down = True
        self.picker_target = "paper"
        self.last_fraction = 0
        self._mouse_hook = None
        self._keyboard_hook = None
        self._mouse_hook_callback = None
        self._keyboard_hook_callback = None
        self._tray_icon = None
        self._tray_icon_added = False
        self.build()
        self.refresh()
        if self.language != "zh":
            self.set_language(self.language)

    def load(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, list):
                return sorted(data, key=lambda item: item["start"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return [item.copy() for item in DEFAULTS]

    def save(self):
        self.plans.sort(key=lambda item: item["start"])
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as file:
                json.dump(self.plans, file, ensure_ascii=False, indent=2)
        except OSError as error:
            messagebox.showerror("保存失败", f"计划文件无法写入：{error}", parent=self.root)
            return False
        self.list_signature = None
        self.rendered_minute = None
        self.draw_list()
        return True
    def build(self):
        self.time_font_regular = tkfont.Font(self.root, family="Segoe UI", size=10)
        self.time_font_bold = tkfont.Font(self.root, family="Segoe UI", size=10, weight="bold")
        time_sample = "00:00 – 00:00"
        self.time_column_width = max(self.time_font_regular.measure(time_sample),
                                     self.time_font_bold.measure(time_sample)) + 8
        self.shell = tk.Frame(self.root, bg=PAPER, highlightthickness=1 if self.frame_color else 0, highlightbackground=EDGE)
        self.shell.pack(fill="both", expand=True)

        self.header_slot = tk.Frame(self.shell, bg=PAPER, height=72)
        self.header_slot.pack(fill="x")
        self.header_slot.pack_propagate(False)
        self.header = tk.Frame(self.header_slot, bg=TOP, height=72)
        self.header.place(x=0, y=0, relwidth=1, height=72)
        self.header_visible = True
        self.chrome_progress = 1.0
        self.chrome_animation = None
        self.title_label = tk.Label(self.header, text="今日计划", bg=TOP, fg=INK,
                                    font=(FONT, 11, "bold"), padx=16)
        self.title_label.pack(side="left", fill="y")
        self.close_button = tk.Button(self.header, text="×", command=self.close_app,
                                      bg=TOP, fg=MUTED, activebackground="#EBDD9C",
                                      relief="flat", bd=0, font=("Segoe UI", 14), width=3)
        self.close_button.pack(side="right", fill="y")
        self.pin_button = tk.Checkbutton(self.header, text="悬浮", variable=self.pin,
                                         command=lambda: self.root.attributes("-topmost", self.pin.get()),
                                         bg=TOP, fg=MUTED, activebackground=TOP, selectcolor=TOP,
                                         bd=0, font=(FONT, 9))
        self.pin_button.pack(side="right", padx=(0, 5))
        self.settings_button = tk.Button(self.header, text="•••", command=self.show_settings_menu,
                                         bg=TOP, fg=MUTED, activebackground="#EBDD9C",
                                         relief="flat", bd=0, font=("Segoe UI", 12), width=4)
        self.settings_button.pack(side="right", fill="y")
        for widget in (self.header, self.title_label):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)

        content = tk.Frame(self.shell, bg=PAPER)
        self.content = content
        content.pack(fill="both", expand=True, padx=17, pady=(14, 10))
        self.clock = tk.Label(content, text="", bg=PAPER, fg=MUTED,
                              font=(FONT, 9), anchor="w")
        self.clock.place(relx=self.layout["clock"][0], rely=self.layout["clock"][1], relwidth=self.layout["clock"][2], relheight=self.layout["clock"][3])

        self.summary = tk.Frame(content, bg=PAPER)
        self.summary.place(relx=self.layout["summary"][0], rely=self.layout["summary"][1], relwidth=self.layout["summary"][2], relheight=self.layout["summary"][3])
        self.state = tk.Label(self.summary, text="", bg=PAPER, fg=ACCENT,
                              font=(FONT, 9), anchor="w")
        self.state.pack(anchor="w")
        self.task = tk.Label(self.summary, text="", bg=PAPER, fg=INK,
                             font=(FONT, 16, "bold"), wraplength=320, justify="left", anchor="w")
        self.task.pack(anchor="w", pady=(6, 10))
        self.period = tk.Label(self.summary, text="", bg=PAPER, fg=MUTED,
                               font=(FONT, 9), anchor="w")
        self.period.pack(anchor="w", pady=(2, 4))
        self.dial = tk.Canvas(content, width=176, height=176, bg=PAPER, highlightthickness=0)
        self.dial.place(relx=self.layout["dial"][0], rely=self.layout["dial"][1], width=176, height=176)
        self.summary.bind("<Configure>", lambda event: self.task.configure(wraplength=max(120, event.width - 8)))

        self.listbox = tk.Frame(content, bg=PAPER)
        self.listbox.place(relx=self.layout["listbox"][0], rely=self.layout["listbox"][1], relwidth=self.layout["listbox"][2], relheight=self.layout["listbox"][3])
        self.layout_targets = {"clock": self.clock, "summary": self.summary, "dial": self.dial, "listbox": self.listbox}
        self.layout_styles = {}

        self.footer_slot = tk.Frame(self.shell, bg=PAPER, height=76)
        self.footer_slot.pack(fill="x", side="bottom")
        self.footer_slot.pack_propagate(False)
        self.footer = tk.Frame(self.footer_slot, bg=TOP, height=76)
        self.footer.place(x=0, y=0, relwidth=1, height=76)
        self.add_button = tk.Button(self.footer, text="＋ 添加时间段", command=self.edit,
                                    bg=TOP, fg=INK, activebackground=LINE, relief="flat", bd=0,
                                    font=(FONT, 11), padx=18)
        self.add_button.pack(side="left", fill="y")
        self.layout_button = tk.Button(self.footer, text="编辑布局", command=self.toggle_layout_mode,
                                       bg=TOP, fg=INK, activebackground=LINE, relief="flat", bd=0,
                                       font=(FONT, 10), padx=14)
        self.layout_reset_button = tk.Button(self.footer, text="恢复默认", command=self.reset_layout,
                                             bg=TOP, fg=MUTED, activebackground=LINE, relief="flat", bd=0,
                                             font=(FONT, 9), padx=10)
        self.layout_reset_button.pack(side="left", fill="y")
        self.layout_reset_button.pack_forget()
        self.palette_button = tk.Button(self.footer, text="调色盘", command=self.open_color_palette,
                                        bg=TOP, fg=INK, activebackground=LINE, relief="flat", bd=0,
                                        font=(FONT, 10), padx=16)
        self.delete_button = tk.Button(self.footer, text="删除 (0)", command=self.delete_selected,
                                       bg=TOP, fg=MUTED, activebackground=LINE, relief="flat", bd=0,
                                       font=(FONT, 10), padx=16, state="disabled")
        self.selection_button = tk.Button(self.footer, text="选择", command=self.toggle_selection_mode,
                                          bg=TOP, fg=MUTED, activebackground=LINE, relief="flat", bd=0,
                                          font=(FONT, 10), padx=16)
        self.selection_button.pack(side="right", fill="y")
        self.draw_list()
        self.install_resize_handles()
        self.root.bind_all("<Enter>", self.on_mouse_enter, add="+")
        self.root.bind_all("<Leave>", self.on_mouse_leave, add="+")
        self.root.bind("<Configure>", self.queue_rounded_region, add="+")
        self.root.after(180, self.apply_rounded_region)
        self.root.after(1000, self.hide_chrome)
        self.root.after(500, self.install_tray_icon)

    def show_settings_menu(self):
        menu = tk.Menu(self.root, tearoff=False, font=(FONT, 9))
        menu.add_command(label=("保存布局" if self.layout_mode else "编辑布局") if self.language == "zh"
                         else ("Save layout" if self.layout_mode else "Edit layout"),
                         command=self.toggle_layout_mode)
        menu.add_command(label="调色盘" if self.language == "zh" else "Color palette",
                         command=self.open_color_palette)
        language_menu = tk.Menu(menu, tearoff=False, font=(FONT, 9))
        language_menu.add_radiobutton(label="中文", value="zh", variable=self.language_var,
                                      command=lambda: self.set_language("zh"))
        language_menu.add_radiobutton(label="English", value="en", variable=self.language_var,
                                      command=lambda: self.set_language("en"))
        menu.add_cascade(label="语言 / Language", menu=language_menu)
        try:
            menu.tk_popup(self.settings_button.winfo_rootx(),
                          self.settings_button.winfo_rooty() + self.settings_button.winfo_height())
        finally:
            menu.grab_release()

    def set_language(self, language):
        self.language = language
        self.language_var.set(language)
        title = ("拖动高亮区，完成后保存" if language == "zh" else "Drag a highlighted area, then save") \
            if self.layout_mode else ("今日计划" if language == "zh" else "Today's Plan")
        self.title_label.configure(text=title)
        self.pin_button.configure(text="悬浮" if language == "zh" else "Float")
        self.layout_button.configure(text="保存布局" if self.layout_mode and language == "zh"
                                     else "Save layout" if self.layout_mode
                                     else "编辑布局" if language == "zh" else "Edit layout")
        self.layout_reset_button.configure(text="恢复默认" if language == "zh" else "Reset layout")
        self.palette_button.configure(text="调色盘" if language == "zh" else "Color palette")
        self.selection_button.configure(text=("取消" if self.selection_mode else "选择")
                                         if language == "zh" else ("Cancel" if self.selection_mode else "Select"))
        self.add_button.configure(text="＋ 添加时间段" if language == "zh" else "＋ Add time block")
        self.dial.itemconfigure(self.dial_items[2], text="剩余" if language == "zh" else "left")
        if self._tray_icon is not None:
            self._tray_icon.title = "今日计划" if language == "zh" else "Today's Plan"
        self._update_delete_button()
        self.list_signature = None
        self.rendered_minute = None
        self._save_settings()
        self.refresh()

    def walk_widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.walk_widgets(child)

    def apply_color(self, color, target="paper"):
        try:
            if len(color) != 7 or not color.startswith("#"):
                return
            int(color[1:], 16)
        except (TypeError, ValueError):
            return
        old = {name: globals()[name] for name in ("PAPER", "TOP", "INK", "MUTED", "ACCENT", "LINE", "EDGE", "ACTIVE", "WHITE")}
        if target == "paper":
            self.base_color = color.upper()
        else:
            self.frame_color = color.upper()
        set_palette(self.base_color, self.frame_color)
        new = {name: globals()[name] for name in old}
        color_map = {old[name].lower(): new[name] for name in old}
        for widget in [self.root, *self.walk_widgets(self.root)]:
            for option in ("background", "activebackground", "selectcolor", "highlightbackground",
                           "foreground", "activeforeground"):
                try:
                    replacement = color_map.get(str(widget.cget(option)).lower())
                    if replacement:
                        widget.configure(**{option: replacement})
                except tk.TclError:
                    pass
        self.root.configure(bg=PAPER)
        self.shell.configure(bg=PAPER, highlightthickness=1 if self.frame_color else 0, highlightbackground=EDGE)
        self.header_slot.configure(bg=PAPER)
        self.footer_slot.configure(bg=PAPER)
        self.header.configure(bg=TOP)
        self.footer.configure(bg=TOP)
        self.dial.configure(bg=PAPER)
        self.dial.delete("all")
        self.dial_items = None
        self.ring_photo = None
        self.ring_fallback_items = None
        self.last_ring_visual = None
        self._save_settings()
        self.list_signature = None
        self.rendered_minute = None
        self.draw_list()
        self.ring(self.last_fraction)
        self.refresh_palette_swatches()

    def _save_settings(self):
        try:
            geometry = [self.root.winfo_x(), self.root.winfo_y(),
                        self.root.winfo_width(), self.root.winfo_height()]
            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump({"paper_color": self.base_color, "frame_color": self.frame_color,
                           "language": self.language,
                           "layout": self.layout, "window_geometry": geometry},
                          file, ensure_ascii=False, indent=2)
            with open(LANGUAGE_FILE, "w", encoding="utf-8") as file:
                file.write(self.language)
        except (OSError, tk.TclError) as error:
            messagebox.showerror("设置未保存", str(error), parent=self.root)

    def _schedule_settings_save(self):
        if self._settings_after:
            try:
                self.root.after_cancel(self._settings_after)
            except tk.TclError:
                pass
        self._settings_after = self.root.after(350, self._save_settings)

    def _save_layout_settings(self):
        self._save_settings()
    def _place_layout(self):
        for name, widget in self.layout_targets.items():
            x, y, width, height = self.layout[name]
            if name == "dial":
                widget.place(relx=x, rely=y, width=176, height=176)
            else:
                widget.place(relx=x, rely=y, relwidth=width, relheight=height)

    def reset_layout(self):
        self.layout = {name: values.copy() for name, values in self.layout_defaults.items()}
        self._place_layout()
        self._schedule_settings_save()

    def toggle_layout_mode(self):
        if not self.layout_mode:
            self.layout_mode = True
            self.title_label.configure(text="拖动高亮区，完成后保存" if self.language == "zh"
                                       else "Drag a highlighted area, then save")
            self.layout_button.configure(text="保存布局" if self.language == "zh" else "Save layout")
            self.layout_reset_button.pack(side="left", fill="y")
            self.layout_styles = {}
            self.show_chrome()
            for name, widget in self.layout_targets.items():
                self.layout_styles[name] = (widget.cget("highlightthickness"),
                                            widget.cget("highlightbackground"),
                                            widget.cget("cursor"))
                widget.configure(highlightthickness=2, highlightbackground=ACCENT, cursor="fleur")
                candidates = [widget, *self.walk_widgets(widget)]
                for candidate in candidates:
                    press_id = candidate.bind(
                        "<ButtonPress-1>", lambda event, key=name: self._layout_drag_start(event, key), add="+")
                    motion_id = candidate.bind("<B1-Motion>", self._layout_drag_motion, add="+")
                    release_id = candidate.bind("<ButtonRelease-1>", self._finish_layout_drag, add="+")
                    self.layout_bindings.extend(((candidate, "<ButtonPress-1>", press_id),
                                                 (candidate, "<B1-Motion>", motion_id),
                                                 (candidate, "<ButtonRelease-1>", release_id)))
            return

        self.layout_mode = False
        self.layout_drag = None
        for widget, sequence, func_id in self.layout_bindings:
            try:
                widget.unbind(sequence, func_id)
            except tk.TclError:
                pass
        self.layout_bindings.clear()
        for name, widget in self.layout_targets.items():
            thickness, outline, cursor = self.layout_styles.get(name, (0, PAPER, ""))
            widget.configure(highlightthickness=thickness, highlightbackground=outline, cursor=cursor)
        self.title_label.configure(text="今日计划" if self.language == "zh" else "Today's Plan")
        self.layout_button.configure(text="编辑布局" if self.language == "zh" else "Edit layout")
        self.layout_reset_button.pack_forget()
        self._save_layout_settings()

    def _layout_drag_start(self, event, name):
        if not self.layout_mode:
            return None
        self.layout_drag = (name, event.x_root, event.y_root, self.layout[name].copy())
        return "break"

    def _finish_layout_drag(self, event=None):
        if self.layout_mode and self.layout_drag:
            self.layout_drag = None
            self._schedule_settings_save()

    def _layout_drag_motion(self, event):
        if not self.layout_mode or not self.layout_drag:
            return None
        name, start_x, start_y, original = self.layout_drag
        width = max(1, self.content.winfo_width())
        height = max(1, self.content.winfo_height())
        widget = self.layout_targets[name]
        item_width = max(original[2], widget.winfo_width() / width)
        item_height = max(original[3], widget.winfo_height() / height)
        x = min(max(0.0, original[0] + (event.x_root - start_x) / width), 1.0 - item_width)
        y = min(max(0.0, original[1] + (event.y_root - start_y) / height), 1.0 - item_height)
        self.layout[name] = [x, y, original[2], original[3]]
        self.layout_targets[name].place_configure(relx=x, rely=y)
        return "break"

    def open_color_palette(self):
        if self.palette_window and self.palette_window.winfo_exists():
            self.palette_window.deiconify()
            self.palette_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.palette_window = win
        win.title("便签调色盘" if self.language == "zh" else "Note colors")
        win.configure(bg=PAPER)
        win.resizable(True, True)
        win.transient(self.root)
        win.geometry("700x250")
        win.minsize(660, 230)
        tk.Label(win, text="便签颜色" if self.language == "zh" else "Note colors", bg=PAPER, fg=INK,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.palette_swatches = {}
        labels = (("paper", "纸面"), ("frame", "边框 / 上下工具栏")) if self.language == "zh" \
            else (("paper", "Paper"), ("frame", "Border / toolbars"))
        for target, label in labels:
            row = tk.Frame(win, bg=PAPER)
            row.pack(fill="x", padx=16, pady=5)
            tk.Label(row, text=label, width=19, anchor="w", bg=PAPER, fg=INK,
                     font=(FONT, 9)).pack(side="left")
            swatch = tk.Label(row, text="   ", relief="solid", bd=1, width=5, bg=WHITE)
            swatch.pack(side="left", padx=(0, 8))
            tk.Button(row, text="调色盘" if self.language == "zh" else "Choose color",
                      command=lambda t=target: self.choose_color(t),
                      bg=TOP, fg=INK, relief="flat", padx=9).pack(side="left", padx=(0, 6))
            tk.Button(row, text="吸色笔" if self.language == "zh" else "Eyedropper",
                      command=lambda t=target: self.start_color_picker(t),
                      bg=TOP, fg=INK, relief="flat", padx=9).pack(side="left")
            self.palette_swatches[target] = swatch
        tk.Label(win, text="吸色时窗口会暂时隐藏；点击屏幕颜色取色，按 Esc 取消。" if self.language == "zh"
                 else "The app hides while sampling. Click a screen color; press Esc to cancel.",
                 bg=PAPER, fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=16, pady=(7, 0))
        self.refresh_palette_swatches()
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        x = max(0, min(x, win.winfo_screenwidth() - win.winfo_width()))
        y = max(0, min(y, win.winfo_screenheight() - win.winfo_height()))
        win.geometry(f"+{x}+{y}")

    def choose_color(self, target):
        current = PAPER if target == "paper" else (self.frame_color or TOP)
        selected = colorchooser.askcolor(color=current,
                                         title="选择颜色" if self.language == "zh" else "Choose a color",
                                         parent=self.palette_window)[1]
        if selected:
            self.apply_color(selected, target)

    def refresh_palette_swatches(self):
        for target, swatch in getattr(self, "palette_swatches", {}).items():
            try:
                swatch.configure(bg=PAPER if target == "paper" else (self.frame_color or TOP))
            except tk.TclError:
                pass

    def start_color_picker(self, target):
        if os.name != "nt":
            messagebox.showinfo("吸色笔", "屏幕吸色功能目前仅支持 Windows。")
            return
        self.picker_target = target
        self._picker_active = True
        self._picker_mouse_was_down = True
        if self.palette_window and self.palette_window.winfo_exists():
            self.palette_window.withdraw()
        self.root.withdraw()
        self._poll_color_picker()

    def _poll_color_picker(self):
        if not self._picker_active:
            return
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        class Point(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        user32.GetCursorPos.restype = ctypes.c_bool
        user32.GetCursorPos.argtypes = [ctypes.POINTER(Point)]
        user32.GetDC.restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.GetPixel.restype = ctypes.c_uint
        gdi32.GetPixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

        if user32.GetAsyncKeyState(0x1B) & 0x8000:
            self.finish_color_picker(None)
            return
        mouse_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        if mouse_down and not self._picker_mouse_was_down:
            point = Point()
            if user32.GetCursorPos(ctypes.byref(point)):
                dc = user32.GetDC(None)
                pixel = gdi32.GetPixel(dc, point.x, point.y)
                user32.ReleaseDC(None, dc)
                if pixel != 0xFFFFFFFF:
                    color = f"#{pixel & 255:02X}{(pixel >> 8) & 255:02X}{(pixel >> 16) & 255:02X}"
                    self.finish_color_picker(color)
                    return
            self.finish_color_picker(None)
            return
        self._picker_mouse_was_down = mouse_down
        self.root.after(25, self._poll_color_picker)
    def finish_color_picker(self, color):
        self._picker_active = False
        target = self.picker_target
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.pin.get())
        if color:
            self.apply_color(color, target)
        if self.palette_window and self.palette_window.winfo_exists():
            self.palette_window.deiconify()
            self.palette_window.lift()
            self.refresh_palette_swatches()

    def install_resize_handles(self):
        self.resize_origin = None
        self.root.bind_all("<ButtonPress-1>", self.begin_resize_if_edge, add="+")
        self.root.bind_all("<B1-Motion>", self.resize_if_active, add="+")
        self.root.bind_all("<ButtonRelease-1>", self.end_resize, add="+")
        self.root.bind_all("<Motion>", self.update_resize_cursor, add="+")

    def resize_edges_at(self, event):
        x = event.x_root - self.root.winfo_rootx()
        y = event.y_root - self.root.winfo_rooty()
        width, height = self.root.winfo_width(), self.root.winfo_height()
        margin = 10
        edges = ""
        if x < margin:
            edges += "left"
        elif x >= width - margin:
            edges += "right"
        if y < margin:
            edges += "top"
        elif y >= height - margin:
            edges += "bottom"
        return edges

    def begin_resize_if_edge(self, event):
        if str(event.widget.winfo_toplevel()) != str(self.root):
            return None
        if self.layout_mode:
            return None
        edges = self.resize_edges_at(event)
        if not edges:
            return None
        self.begin_resize(event, edges)
        return "break"

    def resize_if_active(self, event):
        if self.resize_origin is None:
            return None
        self.resize_window(event)
        return "break"

    def end_resize(self, event=None):
        was_resizing = self.resize_origin is not None
        self.resize_origin = None
        self.root.configure(cursor="")
        if was_resizing:
            self._schedule_settings_save()
            self.root.after_idle(self.apply_rounded_region)

    def update_resize_cursor(self, event):
        if str(event.widget.winfo_toplevel()) != str(self.root):
            return
        if self.layout_mode or self.resize_origin:
            return
        edges = self.resize_edges_at(event)
        if "left" in edges or "right" in edges:
            cursor = "sb_h_double_arrow"
        elif "top" in edges or "bottom" in edges:
            cursor = "sb_v_double_arrow"
        else:
            cursor = ""
        try:
            self.root.configure(cursor=cursor)
        except tk.TclError:
            pass
    def begin_resize(self, event, edges):
        self.resize_origin = (self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(),
                              self.root.winfo_height(), event.x_root, event.y_root, edges)

    def resize_window(self, event):
        x, y, width, height, pointer_x, pointer_y, edges = self.resize_origin
        dx, dy = event.x_root - pointer_x, event.y_root - pointer_y
        min_width, min_height = 600, 700
        if "right" in edges:
            width = max(min_width, width + dx)
        if "bottom" in edges:
            height = max(min_height, height + dy)
        if "left" in edges:
            new_width = max(min_width, width - dx)
            x += width - new_width
            width = new_width
        if "top" in edges:
            new_height = max(min_height, height - dy)
            y += height - new_height
            height = new_height
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self._schedule_settings_save()

    def queue_rounded_region(self, event=None):
        if event and event.widget is not self.root:
            return
        self._schedule_settings_save()
        if self.resize_origin is not None:
            return
        if getattr(self, "_rounded_after", None):
            try:
                self.root.after_cancel(self._rounded_after)
            except tk.TclError:
                pass
        self._rounded_after = self.root.after_idle(self.apply_rounded_region)

    def apply_rounded_region(self):
        if os.name != "nt" or not self.root.winfo_exists() or not self.root.winfo_ismapped():
            return
        hwnd = self.root.winfo_id()
        try:
            width = max(1, self.root.winfo_width())
            height = max(1, self.root.winfo_height())
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
            gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                  ctypes.c_int, ctypes.c_int, ctypes.c_int]
            user32.SetWindowRgn.restype = ctypes.c_int
            user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
            region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, 36, 36)
            user32.GetParent.restype = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]
            top_hwnd = user32.GetParent(hwnd) or hwnd
            if region and not user32.SetWindowRgn(top_hwnd, region, True):
                gdi32.DeleteObject(region)

            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute.restype = ctypes.c_long
            dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                  ctypes.c_void_p, ctypes.c_uint]
            preference = ctypes.c_int(2)
            dwm.DwmSetWindowAttribute(top_hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
            border_color = ctypes.c_uint(
                (int(self.base_color[5:7], 16) << 16)
                | (int(self.base_color[3:5], 16) << 8)
                | int(self.base_color[1:3], 16)
            )
            dwm.DwmSetWindowAttribute(top_hwnd, 34, ctypes.byref(border_color), ctypes.sizeof(border_color))
        except (AttributeError, OSError):
            pass
    def _cursor_inside(self):
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        left, top = self.root.winfo_rootx(), self.root.winfo_rooty()
        return left <= pointer_x < left + self.root.winfo_width() and top <= pointer_y < top + self.root.winfo_height()

    def on_mouse_enter(self, event=None):
        if self._cursor_inside():
            self.show_chrome()

    def on_mouse_leave(self, event=None):
        self.root.after(180, self.hide_chrome)

    def show_chrome(self):
        if self.header_visible and self.chrome_progress >= 1:
            return
        self.header_visible = True
        if self.chrome_animation:
            self.root.after_cancel(self.chrome_animation)
            self.chrome_animation = None
        self._animate_chrome(1.0)

    def hide_chrome(self):
        if self.layout_mode or self._cursor_inside() or not self.header_visible:
            return
        self.header_visible = False
        if self.chrome_animation:
            self.root.after_cancel(self.chrome_animation)
            self.chrome_animation = None
        self._animate_chrome(0.0)

    def _animate_chrome(self, target):
        delta = target - self.chrome_progress
        if abs(delta) < 0.08:
            self.chrome_progress = target
        else:
            self.chrome_progress += 0.10 if delta > 0 else -0.10
        progress = self.chrome_progress
        self.header.place_configure(y=round(-72 * (1 - progress)), height=72)
        self.footer.place_configure(y=round(76 * (1 - progress)), height=76)
        if self.chrome_progress != target:
            self.chrome_animation = self.root.after(16, lambda: self._animate_chrome(target))
        else:
            self.chrome_animation = None
    def install_tray_icon(self):
        if os.name != "nt" or self._tray_icon_added:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw

            icon_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(icon_image)
            draw.rounded_rectangle((2, 2, 61, 61), radius=14,
                                   fill="#FFF7D1", outline="#986019", width=2)
            draw.ellipse((13, 13, 51, 51), outline="#E0D9B8", width=5)
            draw.arc((13, 13, 51, 51), start=270, end=30, fill="#986019", width=5)

            def show_action(icon, item):
                self.root.after(0, self.restore_from_tray)

            def quit_action(icon, item):
                self.root.after(0, self.quit_app)

            menu = pystray.Menu(
                pystray.MenuItem("显示今日计划" if self.language == "zh" else "Show today's plan",
                                 show_action, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出" if self.language == "zh" else "Quit", quit_action),
            )
            icon = pystray.Icon("today_planner", icon_image,
                                "今日计划" if self.language == "zh" else "Today's Plan", menu)
            self._tray_icon = icon
            self._tray_icon_added = True

            def run_icon():
                try:
                    icon.run(setup=lambda current: setattr(current, "visible", True))
                except Exception:
                    self._tray_icon_added = False

            threading.Thread(target=run_icon, daemon=True).start()
        except Exception:
            self._tray_icon_added = False

    def restore_from_tray(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.attributes("-topmost", self.pin.get())
        self.root.focus_force()
        self.root.after_idle(self.apply_rounded_region)

    def close_app(self):
        if not self._tray_icon_added:
            self.install_tray_icon()
        if self._tray_icon_added:
            self.root.withdraw()
            self._save_settings()
        else:
            messagebox.showwarning("托盘不可用" if self.language == "zh" else "Tray unavailable",
                                  "系统托盘初始化失败，窗口仍保持打开。" if self.language == "zh"
                                  else "The tray icon could not be created, so the window will stay open.",
                                  parent=self.root)

    def quit_app(self):
        if self._settings_after:
            try:
                self.root.after_cancel(self._settings_after)
            except tk.TclError:
                pass
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self._save_settings()
        self.root.destroy()

    def start_drag(self, event):
        if self.resize_edges_at(event):
            return
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def drag(self, event):
        if self.resize_origin is not None:
            return
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")
        self._schedule_settings_save()

    def draw_list(self):
        if not hasattr(self, "listbox"):
            return
        signature = tuple((p["start"], p["end"], p["task"]) for p in self.plans)
        if signature != self.list_signature:
            for child in self.listbox.winfo_children():
                child.destroy()
            self.list_rows = []
            for index, plan in enumerate(self.plans):
                row = tk.Frame(self.listbox, bg=PAPER, cursor="hand2")
                row.pack(fill="x")
                marker = tk.Label(row, text="", width=2, bg=PAPER, fg=ACCENT,
                                  font=(FONT, 10), cursor="hand2")
                marker.pack(side="left", padx=(1, 4))
                time_slot = tk.Frame(row, bg=PAPER, width=self.time_column_width)
                time_slot.pack(side="left", fill="y")
                time_slot.pack_propagate(False)
                time_label = tk.Label(time_slot, text="", anchor="w", bg=PAPER, fg=MUTED,
                                      font=self.time_font_regular)
                time_label.pack(side="left", fill="both", expand=True, pady=12)
                name = tk.Label(row, text=plan["task"], anchor="w", bg=PAPER, fg=INK,
                                font=(FONT, 10), wraplength=360, padx=20)
                name.pack(side="left", fill="x", expand=True, pady=12)
                separator = tk.Frame(self.listbox, bg=LINE, height=1)
                if index < len(self.plans) - 1:
                    separator.pack(fill="x", padx=(32, 4))
                for widget in (row, marker, time_slot, time_label, name):
                    widget.bind("<Button-1>", lambda event, idx=index: self.handle_plan_click(idx, event))
                self.list_rows.append((row, marker, time_slot, time_label, name, separator))
            self.list_signature = signature
        now = datetime.now().strftime("%H:%M")
        for index, (plan, widgets) in enumerate(zip(self.plans, self.list_rows)):
            row, marker, time_slot, time_label, name, separator = widgets
            active = plan["start"] <= now < plan["end"]
            background = ACTIVE if active else PAPER
            for widget in (row, marker, time_slot, time_label, name):
                widget.configure(bg=background)
            selected = index in self.selected_plans
            row.configure(highlightthickness=0)
            marker_text = "✓" if selected else ("○" if self.selection_mode else ("●" if active else ""))
            marker.configure(text=marker_text, fg=ACCENT)
            time_label.configure(text=f'{plan["start"]} – {plan["end"]}',
                                 fg=ACCENT if active else MUTED,
                                 font=self.time_font_bold if active else self.time_font_regular)
            name.configure(font=(FONT, 10, "bold" if active else "normal"), fg=INK)
            separator.configure(bg=LINE)
        self.rendered_minute = now
        self._update_delete_button()
    def handle_plan_click(self, index, event=None):
        if self.layout_mode:
            return self._layout_drag_start(event, "listbox")
        if self.selection_mode:
            if index in self.selected_plans:
                self.selected_plans.remove(index)
            else:
                self.selected_plans.add(index)
            self.draw_list()
            return "break"
        self.edit(index)

    def toggle_selection_mode(self):
        self.selection_mode = not self.selection_mode
        self.selected_plans.clear()
        self.selection_button.configure(
            text=("取消" if self.selection_mode else "选择") if self.language == "zh"
            else ("Cancel" if self.selection_mode else "Select"))
        if self.selection_mode:
            self.delete_button.pack(side="right", fill="y")
        else:
            self.delete_button.pack_forget()
        self.draw_list()

    def _update_delete_button(self):
        if not hasattr(self, "delete_button"):
            return
        count = len(self.selected_plans)
        self.delete_button.configure(
            text=(f"删除 ({count})" if self.language == "zh" else f"Delete ({count})"),
            state="normal" if self.selection_mode and count else "disabled",
            fg=ACCENT if count else MUTED)

    def delete_selected(self):
        indices = sorted((i for i in self.selected_plans if 0 <= i < len(self.plans)), reverse=True)
        if not self.selection_mode or not indices:
            return
        confirm_title = "确认删除" if self.language == "zh" else "Confirm deletion"
        selected_rows = [self.plans[i] for i in reversed(indices)]
        entries = "\n".join(f'{p["start"]} – {p["end"]}  {p["task"]}' for p in selected_rows)
        confirm_text = (f'确定删除以下 {len(indices)} 条时间段吗？\n\n{entries}'
                        if self.language == "zh" else
                        f'Delete these {len(indices)} time block(s)?\n\n{entries}')
        if not messagebox.askyesno(
                confirm_title, confirm_text,
                parent=self.root):
            return
        for index in indices:
            del self.plans[index]
        self.selected_plans.clear()
        self.selection_mode = False
        self.selection_button.configure(text="选择" if self.language == "zh" else "Select")
        self.delete_button.pack_forget()
        self.save()

    def edit(self, index=None):
        old = self.plans[index] if index is not None else {
            "start": "09:00", "end": "10:00", "task": "", "next": "休息时间"
        }
        win = tk.Toplevel(self.root)
        win.title(("编辑时间段" if index is not None else "添加时间段") if self.language == "zh"
                  else ("Edit time block" if index is not None else "Add time block"))
        win.configure(bg=PAPER)
        win.resizable(True, True)
        win.transient(self.root)
        win.grab_set()
        width, height = 820, 620
        win.geometry(f"{width}x{height}")
        win.minsize(760, 580)
        start_h, start_m = map(int, old.get("start", "09:00").split(":"))
        end_h, end_m = map(int, old.get("end", "10:00").split(":"))

        body = tk.Frame(win, bg=PAPER)
        body.pack(fill="both", expand=True, padx=(34, 32), pady=(24, 16))
        times = tk.Frame(body, bg=PAPER)
        times.pack(side="left", fill="y", padx=(12, 52), pady=8)

        def pair(hour, minute):
            group = tk.Frame(times, bg=PAPER)
            group.pack(side="left")
            hour_wheel = TimeWheel(group, hour, 23)
            hour_wheel.pack(side="left")
            tk.Label(group, text=":", bg=PAPER, fg=INK, font=("Segoe UI", 21, "bold")).pack(side="left", padx=2)
            minute_wheel = TimeWheel(group, minute, 59)
            minute_wheel.pack(side="left")
            return hour_wheel, minute_wheel

        sh, sm = pair(start_h, start_m)
        tk.Label(times, text="-", bg=PAPER, fg=INK, font=("Segoe UI", 20)).pack(side="left", padx=10)
        eh, em = pair(end_h, end_m)

        content = tk.Frame(body, bg=PAPER)
        content.pack(side="left", fill="both", expand=True)
        tk.Label(content, text="工作内容" if self.language == "zh" else "Work",
                 bg=PAPER, fg=INK,
                 font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 6))
        def rounded_text(parent, height, font):
            box = tk.Canvas(parent, bg=PAPER, height=height, highlightthickness=0)
            shape = box.create_polygon(12, 1, 120, 1, 139, 8, 139, 60, 132, 74, 12, 74, 1, 64, 1, 12,
                                       smooth=True, splinesteps=24, fill=WHITE, outline="#FFFFFF", width=2)
            text = tk.Text(box, height=1, wrap="word", font=font, bg=WHITE, fg=INK,
                           relief="flat", bd=0, padx=8, pady=6, highlightthickness=0)
            item = box.create_window(9, 9, anchor="nw", window=text)
            def resize_box(event):
                w, h = max(30, event.width), max(30, event.height)
                radius = min(12, w // 3, h // 3)
                box.coords(shape, radius, 1, w-radius, 1, w-1, radius, w-1, h-radius,
                           w-radius, h-1, radius, h-1, 1, h-radius, 1, radius)
                box.coords(item, 9, 9)
                box.itemconfigure(item, width=max(1, w-18), height=max(1, h-18))
            box.bind("<Configure>", resize_box)
            return box, text

        task_box, task = rounded_text(content, 150, (FONT, 12))
        task_box.pack(fill="both", expand=True)
        task.insert("1.0", old.get("task", ""))
        tk.Label(content, text="结束后提醒" if self.language == "zh" else "After this block",
                 bg=PAPER, fg=INK,
                 font=(FONT, 11, "bold")).pack(anchor="w", pady=(14, 6))
        next_box, next_text = rounded_text(content, 150, (FONT, 11))
        next_box.pack(fill="both", expand=True)
        next_text.insert("1.0", old.get("next", ""))

        actions = tk.Frame(win, bg=PAPER)
        actions.pack(fill="x", padx=32, pady=(0, 16))
        tk.Button(actions, text="取消" if self.language == "zh" else "Cancel",
                  command=win.destroy, bg=TOP, fg=INK,
                  relief="flat", padx=20, pady=8).pack(side="right", padx=(8, 0))

        def commit():
            start = f"{sh.get():02d}:{sm.get():02d}"
            end = f"{eh.get():02d}:{em.get():02d}"
            task_value = task.get("1.0", "end-1c").strip()
            next_value = next_text.get("1.0", "end-1c").strip()
            errors = []
            if not task_value:
                errors.append("工作内容还没有填写。" if self.language == "zh" else "Please enter the work description.")
            if not next_value:
                errors.append("结束后提醒还没有填写。" if self.language == "zh" else "Please enter the reminder text.")
            if parse_time(end) <= parse_time(start):
                errors.append("结束时间必须晚于开始时间；目前不支持跨午夜的时间段。"
                              if self.language == "zh" else "The end time must be later than the start time; overnight blocks aren't supported yet.")
            if errors:
                messagebox.showerror("无法保存" if self.language == "zh" else "Can't save",
                                     "\n".join(errors), parent=win)
                if not task_value:
                    task.focus_set()
                elif not next_value:
                    next_text.focus_set()
                else:
                    eh.focus_set()
                return
            item = {"start": start, "end": end, "task": task_value, "next": next_value}
            if index is None:
                self.plans.append(item)
            else:
                self.plans[index] = item
            if not self.save():
                return
            self.draw_list()
            win.destroy()

        tk.Button(actions, text="保存" if self.language == "zh" else "Save",
                  command=commit, bg=ACCENT, fg="white",
                  relief="flat", padx=24, pady=8).pack(side="right")
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.lift()
        win.focus_force()
    def ring(self, fraction):
        fraction = max(0.0, min(1.0, fraction))
        if self.dial_items is None:
            image = self.dial.create_image(0, 0, anchor="nw")
            timer = self.dial.create_text(88, 71, text="", font=("Segoe UI", 14, "bold"), fill=INK)
            label = self.dial.create_text(88, 108, text="剩余", font=(FONT, 9), fill=MUTED)
            self.dial_items = (image, timer, label)
        image, timer, label = self.dial_items
        self.last_fraction = fraction
        visual_fraction = fraction
        visual_key = (self.task.cget("text"), self.remaining.split(":", 1)[0])
        if visual_key != self.last_ring_visual:
            try:
                from PIL import Image, ImageDraw, ImageTk

                scale = 3
                bounds = (12 * scale, 12 * scale, 164 * scale, 164 * scale)
                raster = Image.new("RGBA", (176 * scale, 176 * scale), (0, 0, 0, 0))
                draw = ImageDraw.Draw(raster)
                draw.ellipse(bounds, outline=LINE, width=5 * scale)
                if visual_fraction > 0:
                    draw.arc(bounds, start=270, end=270 + 360 * visual_fraction,
                             fill=ACCENT, width=5 * scale)
                raster = raster.resize((176, 176), Image.Resampling.LANCZOS)
                self.ring_photo = ImageTk.PhotoImage(raster, master=self.root)
                self.dial.itemconfigure(image, image=self.ring_photo)
            except ImportError:
                if self.ring_fallback_items is None:
                    track = self.dial.create_oval(12, 12, 164, 164, outline=LINE, width=5)
                    arc = self.dial.create_arc(12, 12, 164, 164, start=90, extent=0,
                                               style="arc", outline=ACCENT, width=5)
                    self.ring_fallback_items = (track, arc)
                    self.dial.tag_raise(timer)
                    self.dial.tag_raise(label)
                self.dial.itemconfigure(self.ring_fallback_items[1], extent=-360 * visual_fraction)
            self.last_ring_visual = visual_key
        self.dial.itemconfigure(timer, text=self.remaining)

    def refresh(self):
        now = datetime.now()
        minute = now.strftime("%H:%M")
        for plan in self.plans:
            end_at = datetime.combine(now.date(), parse_time(plan["end"]))
            key = (now.date().isoformat(), plan["end"], plan["task"])
            if self.last_tick < end_at <= now and key not in self.notified:
                self.notified.add(key)
                self.notify(plan)
        self.last_tick = now
        weekdays = ("一二三四五六日" if self.language == "zh"
                    else ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[now.weekday()])
        clock_text = (f'{now:%Y年%m月%d日}  星期{weekdays[now.weekday()]}  {now:%H:%M:%S}'
                      if self.language == "zh" else f'{now:%Y-%m-%d}  {weekdays}  {now:%H:%M:%S}')
        self.clock.config(text=clock_text)
        if self.rendered_minute != minute:
            self.draw_list()
        active = next((p for p in self.plans if p["start"] <= minute < p["end"]), None)
        if active:
            end = datetime.combine(now.date(), parse_time(active["end"]))
            seconds = max(0, int((end - now).total_seconds()))
            self.remaining = f"{seconds // 60:02d}:{seconds % 60:02d}"
            duration = max(1, int((parse_time(active["end"]).hour * 60 + parse_time(active["end"]).minute -
                                   parse_time(active["start"]).hour * 60 - parse_time(active["start"]).minute) * 60))
            fraction = seconds / duration
            self.state.config(text="● 正在进行" if self.language == "zh" else "● In progress", fg=ACCENT)
            self.task.config(text=active["task"])
            self.period.config(text=f'{active["start"]} – {active["end"]}')
        else:
            upcoming = next((p for p in self.plans if p["start"] > minute), None)
            if upcoming:
                self.state.config(text="○ 等待下一段" if self.language == "zh" else "○ Up next", fg=MUTED)
                self.task.config(text=upcoming["task"])
                self.period.config(text=f'{upcoming["start"]} – {upcoming["end"]}')
            else:
                self.state.config(text="✓ 今日计划已完成" if self.language == "zh" else "✓ Today's plan is complete",
                                  fg=MUTED)
                self.task.config(text="可以安心休息" if self.language == "zh" else "Enjoy your break")
                self.period.config(text="辛苦了，今天做得很好" if self.language == "zh" else "Nice work today")
            self.remaining = "--:--"
            fraction = 0
        self.ring(fraction)
        self.root.after(1000, self.refresh)

    def notify(self, plan):
        self.sound()
        if self.toast and self.toast.winfo_exists():
            self.toast.destroy()
        toast = tk.Toplevel(self.root)
        self.toast = toast
        toast.withdraw()
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#D9DADD")

        width = 480
        card_color = "#FFFFFF"
        header_color = "#F3F3F5"
        button_color = "#F3F3F5"
        card = tk.Frame(toast, bg=card_color, highlightthickness=1,
                        highlightbackground="#E2E3E6")
        card.pack(fill="both", expand=True, padx=1, pady=1)

        header = tk.Frame(card, bg=header_color, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        mark = tk.Canvas(header, width=26, height=26, bg=header_color,
                         highlightthickness=0)
        mark.create_oval(3, 3, 23, 23, outline="#A66B1C", width=2)
        mark.create_arc(3, 3, 23, 23, start=270, extent=250,
                        outline="#A66B1C", width=2)
        mark.pack(side="left", padx=(16, 8), pady=10)
        tk.Label(header, text="今日计划" if self.language == "zh" else "DailyPlanner",
                 bg=header_color, fg="#36363A",
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        tk.Button(header, text="×", command=toast.destroy,
                  bg=header_color, fg="#73747A", activebackground="#E8E8EA",
                  activeforeground="#36363A", relief="flat", bd=0,
                  font=("Segoe UI", 16), cursor="arrow").pack(side="right", padx=(2, 12))

        content = tk.Frame(card, bg=card_color, padx=20, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="时间到了" if self.language == "zh" else "Time's up",
                 bg=card_color, fg="#986019", font=(FONT, 10, "bold")) \
            .pack(anchor="w", pady=(0, 4))
        task_message = (f'「{plan["task"]}」时间结束' if self.language == "zh"
                        else f'Time for “{plan["task"]}” is over')
        tk.Label(content, text=task_message, bg=card_color, fg="#252529",
                 font=(FONT, 10, "bold"), justify="left", anchor="w",
                 wraplength=width - 48).pack(fill="x", anchor="w")
        next_message = (f'接下来：{plan["next"]}' if self.language == "zh"
                        else f'Next: {plan["next"]}')
        tk.Label(content, text=next_message, bg=card_color, fg="#72737A",
                 font=(FONT, 9), justify="left", anchor="w",
                 wraplength=width - 48).pack(fill="x", anchor="w", pady=(8, 0))
        actions = tk.Frame(content, bg=card_color)
        actions.pack(fill="x", pady=(16, 0))
        tk.Button(actions, text="知道了" if self.language == "zh" else "Got it",
                  command=toast.destroy, bg=button_color, fg="#45464B",
                  activebackground="#E8E8EA", activeforeground="#252529",
                  relief="flat", bd=0, padx=16, pady=7,
                  font=(FONT, 9), cursor="hand2").pack(side="right")

        toast.geometry(f"{width}x220+0+0")
        toast.update_idletasks()
        left, top, right, bottom = 0, 0, toast.winfo_screenwidth(), toast.winfo_screenheight()
        try:
            work_area = ctypes.wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(work_area), 0):
                left, top = work_area.left, work_area.top
                right, bottom = work_area.right, work_area.bottom
        except (AttributeError, OSError):
            pass
        available_height = max(200, bottom - top - 24)
        height = min(available_height, max(240, card.winfo_reqheight() + 16))
        x = max(left + 12, right - width - 16)
        y = max(top + 12, bottom - height - 16)
        toast.geometry(f"{width}x{height}+{x}+{y}")
        toast.deiconify()
        toast.update_idletasks()
        try:
            hwnd = toast.winfo_id()
            user32 = ctypes.windll.user32
            user32.GetParent.restype = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]
            hwnd = user32.GetParent(hwnd) or hwnd
            preference = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
        except (AttributeError, OSError):
            pass
        toast.after(14000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def _play_sound_asset(self, filename):
        if os.name != "nt":
            return
        try:
            import winsound
            sound_path = os.path.join(APP_DIR, "assets", "sounds", filename)
            winsound.PlaySound(sound_path, winsound.SND_FILENAME |
                               winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except (OSError, RuntimeError):
            pass

    def sound(self):
        self._play_sound_asset("soft-click.wav")

if __name__ == "__main__":
    root = tk.Tk()
    TimerNote(root)
    root.mainloop()

















