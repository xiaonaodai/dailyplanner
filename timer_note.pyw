import traceback
from pathlib import Path
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

import tkinter as tk
from tkinter import messagebox


def report_error(error_text, root=None):
    log_path = Path(__file__).with_name("timer_note_error.log")
    try:
        log_path.write_text(error_text, encoding="utf-8")
    except OSError:
        log_path = None
    try:
        if root is not None and root.winfo_exists():
            root.withdraw()
        message = error_text[-5000:]
        if log_path:
            message += f"\n\n完整错误日志：{log_path}"
        messagebox.showerror("今日计划启动失败", message, parent=root)
    except tk.TclError:
        pass


root = None
try:
    root = tk.Tk()
    root.report_callback_exception = lambda exc, value, tb: report_error(
        "".join(traceback.format_exception(exc, value, tb)), root)
    from timer_note import TimerNote

    TimerNote(root)
    root.mainloop()
except Exception:
    report_error(traceback.format_exc(), root)
finally:
    if root is not None:
        try:
            root.destroy()
        except tk.TclError:
            pass
