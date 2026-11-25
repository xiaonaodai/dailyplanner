"""Alpha-composited planner text. Mouse input belongs to the Tk window above it."""
import ctypes as c
from ctypes import wintypes as w
from functools import lru_cache
from pathlib import Path
import os
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageDraw, ImageFont

u, g = c.windll.user32, c.windll.gdi32
H = c.c_void_p
def api(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, args
    return fn

create = api(u, "CreateWindowExW", H, w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,H,H,H,H)
dc_create = api(g, "CreateCompatibleDC", H, H)
dib_create = api(g,"CreateDIBSection",H,H,H,w.UINT,c.POINTER(H),H,w.DWORD)
select = api(g,"SelectObject",H,H,H)
delete = api(g,"DeleteObject",w.BOOL,H)
delete_dc = api(g,"DeleteDC",w.BOOL,H)
present = api(u,"UpdateLayeredWindow",w.BOOL,H,H,H,H,H,H,w.DWORD,H,w.DWORD)
place = api(u,"SetWindowPos",w.BOOL,H,H,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT)
previous = api(u,"GetWindow",H,H,w.UINT)
destroy = api(u,"DestroyWindow",w.BOOL,H)
show = api(u,"ShowWindow",w.BOOL,H,c.c_int)

@lru_cache(maxsize=64)
def font(size, bold, family=""):
    directory = Path(os.environ["WINDIR"]) / "Fonts"
    file = ("segoeuib.ttf" if bold else "segoeui.ttf") if family.lower() == "segoe ui" else ("msyhbd.ttc" if bold else "msyh.ttc")
    return ImageFont.truetype(str(directory / file), size)

@lru_cache(maxsize=128)
def wrapped_lines(value, face, width):
    lines = []
    for paragraph in value.split("\n"):
        start = 0
        while start < len(paragraph):
            # Find the longest prefix that fits, including unspaced Chinese text.
            low, high = 1, min(len(paragraph) - start, 2)
            while high < len(paragraph) - start and face.getlength(paragraph[start:start+high]) <= width:
                high = min(len(paragraph) - start, high * 2)
            while low < high:
                mid = (low + high + 1) // 2
                if face.getlength(paragraph[start:start+mid]) <= width:
                    low = mid
                else:
                    high = mid - 1
            end = start + low
            if end < len(paragraph) and paragraph[end-1].isascii() and paragraph[end].isalnum():
                space = paragraph.rfind(" ", start, end)
                if space > start:
                    end = space + 1
            lines.append(paragraph[start:end])
            start = end
        if not paragraph:
            lines.append("")
    return lines


class GlassText:
    def __init__(self):
        self.hwnd = create(0x80000 | 0x20 | 0x80 | 0x08000000, "STATIC", "", 0x80000000,
                           0,0,1,1,None,None,None,None)
        if not self.hwnd:
            raise OSError("Cannot create text surface")
        self.signature = None
        self.bounds = None

    def close(self):
        if self.hwnd:
            destroy(self.hwnd)
            self.hwnd = None

    def update(self, app):
        root = app.root
        x, y = root.winfo_rootx(), root.winfo_rooty()
        width, height = root.winfo_width(), root.winfo_height()
        if not root.winfo_ismapped() or min(width,height) < 2:
            show(self.hwnd, 0)
            return False
        records = []
        def visit(parent, clip):
            for widget in parent.winfo_children():
                if isinstance(widget, tk.Toplevel) or not widget.winfo_ismapped():
                    continue
                l, t = widget.winfo_rootx()-x, widget.winfo_rooty()-y
                r, b = l+widget.winfo_width(), t+widget.winfo_height()
                bounds = max(l,clip[0]),max(t,clip[1]),min(r,clip[2]),min(b,clip[3])
                if bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:
                    continue
                if isinstance(widget,(tk.Label,tk.Button,tk.Checkbutton)):
                    value = str(widget.cget("text"))
                    checked = bool(app.pin.get()) if widget is app.pin_button else None
                    if value:
                        attrs = root.tk.splitlist(root.tk.call("font","actual",widget.cget("font")))
                        attrs = dict(zip(attrs[::2],attrs[1::2]))
                        size = int(attrs["-size"])
                        pixels = round(root.winfo_fpixels("1p")*size) if size>0 else -size
                        records.append((bounds, value, max(1,pixels), str(attrs["-weight"])=="bold",
                                        tuple(v//257 for v in widget.winfo_rgb(widget.cget("fg"))),str(widget.cget("anchor")),
                                        widget.winfo_pixels(widget.cget("padx")), str(attrs["-family"]), checked,
                                        widget.winfo_pixels(widget.cget("wraplength")), (l,t,r,b)))
                elif widget is app.dial:
                    records.append((bounds,"dial",app.remaining,round(app.last_fraction,3)))
                elif isinstance(widget,tk.Frame) and b-t <= 2:
                    records.append((bounds,"line"))
                visit(widget,bounds)
        visit(root,(0,0,width,height))
        sig = (width,height,tuple(records))
        if sig != self.signature:
            img = Image.new("RGBA",(width,height))
            draw = ImageDraw.Draw(img)
            for item in records:
                (l,t,r,b),value = item[:2]
                if len(item)==2:
                    draw.line((l,t,r,t),fill="#89929b")
                elif len(item)==4:
                    box = (l+12,t+12,l+164,t+164)
                    draw.ellipse(box,outline="#90989d",width=5)
                    if item[3]>0:
                        draw.arc(box,270,270+360*item[3],fill="#a66b1c",width=5)
                    for label,offset,pt,bold in ((item[2],71,14,True),("剩余" if app.language=="zh" else "Left",108,9,False)):
                        draw.text((l+88,t+offset),label,font=font(round(root.winfo_fpixels("1p")*pt),bold),fill="#20252b",anchor="mm")
                else:
                    f = font(item[2],item[3],item[7] if value.isascii() or all(ch in "0123456789: –" for ch in value) else "")
                    align = item[5]
                    surface = Image.new("RGBA",(r-l,b-t))
                    ctx = ImageDraw.Draw(surface)
                    anchor = "lm" if "w" in align else "rm" if "e" in align else "mm"
                    px = item[6] if anchor=="lm" else r-l-item[6] if anchor=="rm" else (r-l)//2
                    if item[9] > 0:
                        left, top, right, bottom = item[10]
                        width_limit = max(1, min(item[9], right-left-2*item[6]))
                        lines = wrapped_lines(value, f, width_limit)
                        line_height = sum(f.getmetrics())
                        first_y = top-t + max(line_height/2, (bottom-top-(len(lines)-1)*line_height)/2)
                        for index, line in enumerate(lines):
                            cy = first_y + index*line_height
                            if -line_height < cy < b-t+line_height:
                                ctx.text((px,cy),line,font=f,fill=item[4],anchor=anchor)
                        img.alpha_composite(surface,(l,t))
                        continue
                    if item[8] is not None:
                        side = max(9, round(item[2] * 0.63))
                        gap = max(4, side // 3)
                        group_width = side + gap + ctx.textlength(value, font=f)
                        left = max(0, round((r-l-group_width)/2))
                        top = ((b-t)-side)//2
                        ctx.rectangle((left,top,left+side-1,top+side-1),outline=item[4])
                        if item[8]:
                            ctx.line([(left+side//5,top+side//2),
                                      (left+2*side//5,top+3*side//4),
                                      (left+4*side//5,top+side//4)],
                                     fill=item[4],width=max(2,side//6))
                        px, anchor = left+side+gap, "lm"
                    if value.startswith("\u2713"):
                        # Draw the status or selection mark independently of font coverage.
                        value = value[1:]
                        side = max(8, round(item[2] * 0.7))
                        span = side + ctx.textlength(value, font=f)
                        left = round(px - {"lm": 0, "mm": span / 2, "rm": span}[anchor])
                        mid = (b-t)//2
                        ctx.line([(left, mid), (left+side//3, mid+side//3),
                                  (left+side-1, mid-side//3)],
                                 fill=item[4], width=max(2, side//7))
                        px, anchor = left + side, "lm"
                    ctx.text((px,(b-t)//2),value,font=f,fill=item[4],anchor=anchor)
                    img.alpha_composite(surface,(l,t))
            self._present(img,x,y)
            self.signature = sig
        self.sync_position(app)
        return True

    def sync_position(self, app):
        root = app.root
        bounds = (root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height())
        moved = bounds != self.bounds
        parent = app._main_window_handle()
        if moved or previous(self.hwnd,3) != parent or not u.IsWindowVisible(self.hwnd):
            place(self.hwnd, parent, *bounds, 0x10|0x40|0x200)
            self.bounds = bounds
        helper = app.acrylic_helper_hwnd
        if helper and (moved or previous(helper,3) != self.hwnd):
            x, y, width, height = bounds
            place(helper, self.hwnd, x+6, y+6, max(1,width-12), max(1,height-12), 0x10|0x200)

    def _present(self,img,x,y):
        width,height = img.size
        header = (c.c_int32*10)(40,width,-height,0x200001)
        bits = H()
        dc = dc_create(None)
        bmp = dib_create(dc,c.byref(header),0,c.byref(bits),None,0)
        if not bmp:
            delete_dc(dc)
            raise OSError("Cannot allocate text bitmap")
        old = select(dc,bmp)
        try:
            red, green, blue, alpha = img.convert("RGBa").split()
            raw = Image.merge("RGBA",(blue,green,red,alpha)).tobytes()
            c.memmove(bits,raw,len(raw))
            blend = (c.c_ubyte*4)(0,0,255,1)
            if not present(self.hwnd,None,c.byref(w.POINT(x,y)),c.byref(w.SIZE(width,height)),dc,
                           c.byref(w.POINT()),0,c.byref(blend),2):
                raise OSError("Cannot composite text")
        finally:
            select(dc,old)
            delete(bmp)
            delete_dc(dc)
