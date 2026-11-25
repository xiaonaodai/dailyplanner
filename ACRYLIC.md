# DailyPlanner | Windows acrylic implementation

[中文版](#今日计划的-windows-亚克力实现) · Engineering Post-Mortem & Architecture Guide

> [!NOTE]
> **Why this document exists:**
> Implementing native Windows 11 rounded frosted glass (Acrylic / Mica) in Python Tkinter is notoriously painful. Most online demos break immediately when transitioning from a toy prototype into a real application: transparent color keys leak mouse clicks right into the desktop, transparent text loses its subpixel anti-aliasing and turns into fuzzy white silhouettes, and adding rounded corners causes DWM to paint the entire client area solid white.
> 
> Rather than hiding the struggle, this document serves as an honest engineering log of how DailyPlanner evolved from an opaque yellow sticky note into an interactive, multi-layered frosted glass window—and why the final **"Three-Layer Sandwich Architecture"** solved all the fundamental limitations of Tkinter on modern Windows.

## How we got here

The original reference was a music player over a photo of trees and blue sky. Through its window you could tell where the green turned blue, but you could no longer pick out the leaves. The song titles stayed sharp. It took several attempts to get all three properties into one usable planner window. These are the turning points we can trace from the screenshots, reports and tests.

1. **The yellow note became a white note.** With acrylic enabled, the user's yellow paper still covered the backdrop. Giving glass its own neutral color removed the yellow cast, but a translucent white sheet over a wallpaper still looked milky. Lowering the opacity of the whole Tk window faded the countdown along with the paper. We kept the classic palette and started treating glass and foreground text as separate rendering problems.
2. **The first convincing result was a title bar.** We tried a separate `acrylic_preview.pyw` so experiments could run outside the planner. One preview exposed the lettering in the window behind it so clearly that both sets of text overlapped. Later, while testing Windhawk, the palette's title bar picked up green from the wallpaper on one side and the pale note on the other. Its body was still white and the planner was still yellow. That screenshot gave us a precise target for the *client area*, where Tk painted its own controls.
3. **The slider had a cliff at 100.** Most adjustments to light transmission and blur looked alike. The useful comparison was between 99, which looked soft and pale, and 100, which let much more background color through. During subsequent revisions the two choices appeared reversed, and at one point both looked like Mica. We kept the two recognizable appearances as named presets. Checking the selected radio button alone had missed these regressions. Putting *the same colored background* behind both presets made them obvious.
4. **Removing the gray blocks broke the mouse.** Gray task rows and toolbar buttons were ugly, but their entire rectangles responded. Once their background pixels were removed, clicking a letter worked while clicking beside it could select the desktop. Three tiny menu dots made this painfully easy to reproduce. Restoring the gray surfaces brought the hit areas back, at the cost of covering the glass. This is why the final design retains real Tk controls for input and draws their visible contents on a separate surface. Testing included opening the palette *over* the note, where a click had previously gone to the wrong window.
5. **We got round corners and lost both materials.** Before experimenting, we archived the accepted square-corner build. A first native-frame trial compiled, launched in both modes and returned the requested DWM corner preference. On the user's desktop the corners really were round, but both panels were white. We restored the accepted host and tested the next change with fine red and blue stripes. Even that test initially misidentified the lower corners as square because it compared pixels in the bottom shadow with pixels above the window. Using a nearby reference in the same shadow showed the curve. The borderless host then passed both the four-corner check and the color check in each preset.
6. **A good still image hid several interaction bugs.** A short task looked fine while a long one lost its second line. A menu worked in Chinese while its English editing title pushed the three dots out of reach. A list could move up and sideways while its empty lower half prevented a downward drag. Finally, the three windows lined up at rest but briefly separated in motion. Each report added a specific test: resize with long text, save through the English menu, drag a *single-row* list down from its default position, then drag the whole panel over a patterned background. Those cases explain the event and geometry handling below.

An early build also failed at startup because `TimerNote.build` bound `<Configure>` to a missing `_sync_glass_bounds_event` method. Another revision displayed text at roughly half the earlier size while the window stayed almost the same size. The traceback identified the first failure directly. The side-by-side screenshot established the scale regression in the second case, but did not establish a specific DPI cause. Both experiences are why the source launcher and the visible result are checked separately.


## Window ownership and coordinates

The main panel consists of three top-level Windows windows arranged in a synchronized "sandwich" architecture. Each has its own OS window handle (`HWND`):

```text
┌─────────────────────────────────────────────────────────────────┐
│ 1. Input Layer (Top)       - Tkinter Window (Opacity: 0.01)     │
│    • Captures mouse clicks, button hits & window drags          │
│    • Visually transparent, but full control padding stays solid │
├─────────────────────────────────────────────────────────────────┤
│ 2. Visual Layer (Middle)   - Python GlassText (WS_EX_LAYERED)   │
│    • Premultiplied RGBA bitmap via UpdateLayeredWindow          │
│    • Draws pin-sharp text, countdown ring & vector checkmarks   │
│    • Click-through (WS_EX_TRANSPARENT), purely visual           │
├─────────────────────────────────────────────────────────────────┤
│ 3. Backdrop Layer (Bottom) - C# WinForms Host (DWM API)         │
│    • Native Windows 11 rounded corners (DWMWCP_ROUND)           │
│    • Hardware-accelerated Acrylic (State 3) & Mica (State 4)    │
│    • Synchronously tracks parent coordinates & z-order          │
└─────────────────────────────────────────────────────────────────┘
```

| Stacking order | Owner | Responsibility |
| --- | --- | --- |
| Front | Tk main window | Receives mouse events for buttons, rows and dragging. The color key is cleared. After the first successful text render, whole-window opacity drops to 0.01, keeping control padding hittable. |
| Middle | Python, `GlassText` | Reads Tk widget geometry, clips it to visible parent bounds and draws text, checkmarks and the dial into an RGBA image. `_present` premultiplies the color channels by alpha and submits BGRA pixels with `UpdateLayeredWindow`. This window passes mouse input through. |
| Back | C#, `BackdropHostForm` | A borderless WinForms window supplies the blurred desktop background. It tracks the main window and stays below the text. |

For a Tk client rectangle `(x, y, w, h)` in screen coordinates, the text window uses the same rectangle. The backdrop uses `(x+6, y+6, w−12, h−12)` at normal panel sizes. Inside the text bitmap, a label starts at its screen position minus the Tk client origin. To reposition a button, change the Tk layout so the image and the hit target move together. Pinning changes the topmost state of all three windows. See [timer_note.py](timer_note.py) and [glass_text.py](glass_text.py).

## Material selection and lifecycle

Enabling glass asks `_sync_acrylic_helper_parameters` to find or launch the host for this Tk client handle. Startup passes the preset on the command line. Subsequent changes send `WM_APP + 0x42`; the host reads the preset from `lParam` and calls `ApplyMaterial`. That method extends the frame into the client area and passes an accent policy to `SetWindowCompositionAttribute` using attribute 19.

| UI preset | Saved value | Argument | Accent state | Flags | Color |
| --- | --- | ---: | ---: | ---: | --- |
| Mica | `mica` | 99 | 4 | 2 | `0x03E6E8EA` |
| High transparency | `high_transparency` | 100 | 3 | 0 | `0` |

“Mica” is DailyPlanner’s name for the paler preset. In this host, an argument below 100 selects state 4; 100 selects state 3. This branch explains the visible jump at the end of the old slider. The protocol still carries a blur argument, but this implementation does not use it to set a Gaussian radius. Classic paper and frame colors are stored separately. Turning glass off cancels the scheduled text updates, closes the text window and requests that the backdrop host close. See [Program.cs](native/AcrylicBackdropHost/Program.cs) and [BackdropHostForm.cs](native/AcrylicBackdropHost/BackdropHostForm.cs).

## Movement, resizing and editing

- **Move the panel.** Tk emits `<Configure>`. Once the text layer is ready, `_on_main_window_configure` calls `GlassText.sync_position` to position text and backdrop using the new client rectangle. Text refresh runs separately at roughly 100 ms intervals. Waiting for that refresh to move the text used to leave it behind the pointer. The host also checks its position every 50 ms; its corrective move uses `SWP_NOZORDER` so it cannot jump in front of the lettering.
- **Resize the panel.** A size change can require new widget geometry, text wrapping and a new rounded input region. Moving without resizing reuses that region. The Tk window uses a manually rounded region. The borderless material host requests DWM attribute 33 with value 2 (`DWMWCP_ROUND`) and has no manual region. A trial that added native caption and resize-frame styles produced rounded but white panels.
- **Move a component.** In layout editing, a dedicated Tk binding tag precedes the widget’s usual bindings. A component drag consumes the event before the whole-window handler runs. Newly created task rows receive the tag as well. The list starts at relative height coordinate 0.49 and normally extends another 0.51 to the bottom. During a downward drag, `_layout_drag_motion` lets the list shrink and keeps room for the first row. The saved rectangle includes the adjusted height. The English header reads *Editing* to keep *Save layout* accessible in the menu.

## Text rendering and regression checks

Tk can wrap a label while the independently drawn glass text still clips at the right edge. `wrapped_lines` measures substrings using the actual Pillow font, fits them to the label’s wrap length and inner width, and preserves explicit line breaks. It handles unspaced Chinese and long English words. The final draw is clipped to the visible control area. Completion and selection ticks are drawn as strokes to avoid missing glyphs. The pin checkbox uses the saved UI state when drawing its tick.

| Reproduce | What to check |
| --- | --- |
| Move the panel between red and blue striped backgrounds. | Both presets pick up the background color and soften its stripes. Compare the lower corners against nearby background in the same shadow. A successful DWM attribute call alone does not establish the visible result. |
| Click between menu dots, then open the palette over the main panel. | The menu padding should accept clicks and the dialog should receive its own input. Earlier color-key holes allowed clicks through to the desktop and left pale antialiasing fringes. |
| Resize a long task from a 650 px to an 800 px window. | In the recorded test, the Chinese heading changed from four lines to three and the English list item from five to three. Inspect both controls. |
| Drag a task row down in editing mode, save, then leave editing and move the panel. | The list moved down 65 px and back up 20 px without moving the window in the layout test. During the whole-panel test, 25 sampled positions per preset matched the expected rectangles. Position sampling checks alignment; rapid dragging over a patterned background checks visible flicker. |

## Rebuild and diagnose

Exit the tray instance first. After restoring project dependencies, run this command from the repository root, then launch [timer_note.pyw](timer_note.pyw). The source loader checks `rounded-glass` before `anchored`. Compiling only to the default output path can leave the old host active.

```powershell
dotnet build native/AcrylicBackdropHost/AcrylicBackdropHost.csproj -c Release --no-restore -o native/AcrylicBackdropHost/rounded-glass
```

For missing text, check `%APPDATA%\DailyPlanner\glass_text_error.log`. For a host startup exception, check `acrylic_backend_error.log` in the same directory. The local pre-corner backup is `backups/Timer-before-round-corners-20261124-171618.zip`. The refreshed 1.1.0 installer includes the wrapping, layout editing and window movement fixes described here.

---

# 今日计划的 Windows 亚克力实现

> [!NOTE]
> **写在前面：**
> 在 Python Tkinter 里面做 Windows 11 原生圆角毛玻璃（亚克力 / 云母），是一部充满挫折的“踩坑血泪史”。
> 
> 网上的教程大多只停留在几行代码的 Demo 阶段，一旦进入真实桌面软件开发，各种致命问题就会接踵而至：用透明色键抠图导致鼠标直接穿透点到桌面上、文字半透明导致边缘泛起刺眼的白色杂色毛边、好不容易加上圆角窗口又直接变成死白色……
> 
> 本文档不讲空洞的理论，而是毫无保留地公开我们在开发《今日计划》过程中的真实调试记录，以及最终如何用**独创的“三层三明治架构”**彻底攻克 Tkinter 底层限制的完整工业级方案。希望能帮到每一个在 Windows 桌面美化和 Python GUI 领域探索的开发者。

源码记录，2026-11-25。

## 我们是怎样一路试过来的

最初的参照是一张播放器截图。窗口压在树和蓝天上，隔着它仍能看出哪里是绿、哪里是蓝，却看不清每一片叶子；窗口里的歌名又很清楚。后来每当我们以为“这次够透明了”，把便签往有文字或花纹的地方一拖，就会发现还差哪一项。下面按几个改变实现方向的节点，记录当时看到的现象和取舍。

1. **先是黄纸，后来成了白纸。** 打开亚克力以后，用户自己吸取的黄色纸面还盖在背景上。给玻璃单独设一套中性色，黄色终于消失了，可窗口看起来又像蒙了一层白纸。把整窗透明度往下调，倒计时和标题也跟着变淡。这一步让我们保留了普通模式的配色，同时把“背景有多透”和“文字有多清楚”当成两个绘制问题处理。
2. **第一个让人满意的效果，只出现在标题栏。** 我们先做了独立的 `acrylic_preview.pyw`。有一版预览确实透了，后面背景窗口里的字却清楚到能和便签文字叠在一起读。后来试 Windhawk，调色盘标题栏左边透出壁纸的绿，右边透出便签的浅黄，恰好就是想要的效果。偏偏标题栏下面还是白的，后面的主面板还是黄的。这张图帮我们缩小了问题范围：系统能把标题栏做成玻璃，接下来要解决的是 Tk 自己绘制的内容区。
3. **滑块从 99 到 100，像突然换了一扇窗。** 大部分时候，拖透光度和模糊程度都看不出多少变化；偏偏最后一格变化很大。99 柔和、偏浅，100 明显更透。后来调整时还出现过两档效果反过来，以及明明选中“高透”却两档都像云母。最终留下“云母”和“高透”两个选项。验证时，把同一块有颜色的背景放到窗后，来回切换两次，比看单选框勾在哪边更能发现问题。
4. **灰块消失了，鼠标也漏过去了。** 原本灰色的列表和按钮虽然突兀，整块都能点。把背景像素抠掉以后，点在字的笔画上有效，点在笔画旁边却可能选中桌面。尤其是三个点菜单，要瞄准其中一个小点才能打开。把灰色点击面放回去，操作恢复了，玻璃又被盖住。这就是最终保留整块 Tk 控件接鼠标、另用一层画可见文字的来由。测试还要把调色盘盖在便签上再点一次，因为曾经连调色盘里的按钮都接不到点击。
5. **四角真圆了，两种玻璃也真白了。** 试圆角前，我们先备份了已经认可的方角版本。第一次改原生边框，编译通过，两档都能启动，读回来的 DWM 圆角属性也正确。用户一发截图就能看出遗漏：两种材质都成了白底。于是先恢复旧背景程序，再用红蓝细条纹做对照。连测量本身都走过一次弯路：拿窗口上方的颜色对比下方两个角，把窗底阴影误判成了方边。改用下边缘附近、同一阴影里的像素作参照，才看清弧线。最后保留无边框背景程序，让云母、高透各自同时通过四角和透色两项检查。
6. **静止时看着对，用起来还有问题。** 短任务显示正常，换成长工作内容就丢了第二行；中文菜单能保存布局，换成英文，长标题把三个点挤出了窗口；列表可以往上、往左右拖，偏偏下面一大片空白让它无法下移。最后，三层窗口静止时严丝合缝，一拖动又会闪。这几次反馈分别留下了具体的复验动作：输入长任务再缩放、用英文菜单保存、从默认位置把只有一行任务的列表往下拖，以及把整窗快速拖过花纹背景。下文里的事件优先级和坐标同步，都是从这些实际操作里改出来的。

中途还出现过一次双击完全打不开：`TimerNote.build` 给 `<Configure>` 绑定了一个不存在的 `_sync_glass_bounds_event` 方法，启动回溯直接指出了它。另一次窗口大小几乎不变，字却比旧版小了约一半。左右对照图能确认字号确实退化，当时的证据还不足以断定是哪一项 DPI 设置造成的。这两件事也提醒我们，能从源码入口启动、显示尺寸正确，是两项要分别检查的结果。


## 窗口分层与坐标

主面板由三个独立的 Windows 窗口叠成一个精准同步的“三明治架构”，每个窗口都有自己的系统句柄（`HWND`）：

```text
┌─────────────────────────────────────────────────────────────────┐
│ 1. 顶层：鼠标输入层  - Tkinter 主窗口 (不透明度 0.01)            │
│    • 负责接收所有点击、拖动、按钮 hover 与窗口缩放              │
│    • 视觉上完全透明，但保留了控件完整的鼠标响应面积             │
├─────────────────────────────────────────────────────────────────┤
│ 2. 中层：高清绘制层  - Python GlassText 分层窗口 (WS_EX_LAYERED) │
│    • 使用 Pillow 预乘 Alpha 绘制超清文字、倒计时环与对勾图标    │
│    • 彻底解决 Tkinter 文字透明边缘泛白刺眼的难题                │
│    • 开启鼠标完全穿透 (WS_EX_TRANSPARENT)，只负责视觉呈现        │
├─────────────────────────────────────────────────────────────────┤
│ 3. 底层：毛玻璃背景层 - C# WinForms 宿主 (DWM API)              │
│    • 负责调用系统级 DWM 硬件加速渲染云母 (Mica) 与高透亚克力    │
│    • 实现真正的 Windows 11 系统级圆角 (DWMWCP_ROUND)            │
│    • 毫秒级跟随主窗口移动，绝不发生错位或遮挡                   │
└─────────────────────────────────────────────────────────────────┘
```

| 从前到后 | 实现 | 职责 |
| --- | --- | --- |
| 输入层 | Tk 主窗口 | 接收按钮、任务行和拖动事件。清除透明色键。文字层首次绘制成功后，将 Tk 整窗不透明度设为 0.01，按钮文字周围的留白仍能接收点击。 |
| 文字层 | Python 的 `GlassText` | 读取控件坐标，按父控件的可见范围裁剪，在 RGBA 位图上画字、对勾和倒计时环。`_present` 将颜色通道乘以透明度，按 BGRA 顺序交给 `UpdateLayeredWindow` 显示。这层允许鼠标穿过。 |
| 背景层 | C# 的 `BackdropHostForm` | 无边框 WinForms 窗口负责显示经过模糊处理的窗后内容。它跟随主窗口，位于文字层下方。 |

设 Tk 客户区的屏幕矩形为 `(x, y, w, h)`。文字层直接使用该矩形；正常面板尺寸下，背景层使用 `(x+6, y+6, w−12, h−12)`，即四边各收进 6 像素。画到位图上时，要用“标签的屏幕坐标减去客户区原点”得到局部坐标。因此，调整关闭叉号应该改 Tk 按钮的布局，点击区域和可见图标才会一起移动。勾选“悬浮”时，三个窗口一同改变置顶状态。实现见 [timer_note.py](timer_note.py) 和 [glass_text.py](glass_text.py)。

## 材质切换与窗口生命周期

开启亚克力后，`_sync_acrylic_helper_parameters` 按 Tk 客户区句柄查找对应的背景程序，需要时启动它。首次启动通过命令行传入预设，运行中切换则发送 `WM_APP + 0x42` 消息。背景程序从 `lParam` 读取预设并调用 `ApplyMaterial`，把系统边框效果扩展到客户区，再通过 `SetWindowCompositionAttribute` 的属性 19 设置材质参数。

| 界面选项 | 保存值 | 传入值 | Accent 状态 | 标志 | 颜色 |
| --- | --- | ---: | ---: | ---: | --- |
| 云母 | `mica` | 99 | 4 | 2 | `0x03E6E8EA` |
| 高透 | `high_transparency` | 100 | 3 | 0 | `0` |

“云母”是项目给偏浅、柔和的预设起的名字。传入值小于 100 时走状态 4，达到 100 时切到状态 3。这解释了旧滑块为什么在最后一格突然变样。协议里仍有模糊参数，当前实现没有用它设置高斯模糊半径。传统模式单独保存纸面色和边框色。关闭亚克力时，程序取消文字刷新任务、关闭文字窗口，并通知背景窗口退出。实现见 [Program.cs](native/AcrylicBackdropHost/Program.cs) 和 [BackdropHostForm.cs](native/AcrylicBackdropHost/BackdropHostForm.cs)。

## 整窗移动、缩放与布局编辑

- **拖整张便签。** Tk 发出 `<Configure>` 事件。文字层就绪后，`_on_main_window_configure` 调用 `GlassText.sync_position`，用同一份新坐标定位文字层和背景层。文字内容本身约每 100 毫秒刷新一次。旧实现等到刷新才移动文字，所以拖快时文字会滞后。背景程序还会每 50 毫秒校正位置；校正时使用 `SWP_NOZORDER`，保留窗口叠放顺序，避免背景短暂盖到文字上。
- **缩放便签。** 尺寸变化可能需要重排控件、重新换行，并重建输入窗口的圆角区域。只平移时复用已有区域。Tk 输入层使用手工裁出的圆角，背景层则保留无边框样式，移除手工区域，设置 DWM 属性 33 为 2（`DWMWCP_ROUND`）。曾有一版同时加了系统标题栏和缩放边框，结果圆角出现了，两种材质却都变白了。
- **拖单个组件。** 编辑状态下，Tk 会优先执行组件的布局拖动绑定。组件处理完事件就停止传播，整窗拖动不会接手。重新生成的任务行同样带这个绑定。列表默认从内容区高度的 49% 开始，占用剩余 51%。以前限制整个矩形不能越界，哪怕只有一条任务也无法下移。现在 `_layout_drag_motion` 允许下移时收缩列表高度，并为首行保留空间；保存布局时同时保存新位置和高度。英文标题缩短为 *Editing*，避免挤掉带有 *Save layout* 的菜单。

## 文字绘制与回归验证

Tk 标签会换行，但亚克力模式下可见的字由 Pillow 再画一遍。旧实现把整段画成一行，到右边界就被截断。`wrapped_lines` 使用实际绘制的字体量宽，按标签的换行宽度和扣除内边距后的可用宽度排版，并保留手动换行。连续中文和没有空格的英文长词也可以拆行。最终只绘制控件可见范围内的部分。完成状态和选中行的勾号由线段绘制，避免字体缺字；悬浮复选框则按当前勾选状态绘制。

| 复现操作 | 验证内容 |
| --- | --- |
| 把便签从红色细条纹背景移到蓝色细条纹背景。 | 两种预设都应随底色变化，窗后条纹应模糊。检查下方圆角时，取紧邻下边缘、处于同一阴影内的背景作参照。只读到 DWM 设置成功，还无法判断视觉结果。 |
| 点菜单三个点之间的空隙，再让调色盘覆盖主面板。 | 菜单留白应可点击，调色盘应能收到自己的点击。旧的颜色键方案会把鼠标漏到桌面，抗锯齿混色像素也可能在字边留下一圈白。 |
| 输入长任务，把窗口从 650 像素拉宽到 800 像素。 | 当时实测，中文标题从四行变三行，英文列表项从五行变三行。标题和列表项需要分别检查。 |
| 在编辑模式下往下拖任务行，保存后退出编辑，再拖整张便签。 | 布局测试里，列表下移 65 像素、回移 20 像素，主窗口坐标保持不变。整窗移动测试则对每种材质各取样 25 次，文字和背景均符合预期坐标。坐标取样验证对齐，快速拖过花纹背景可进一步检查肉眼可见的闪烁。 |

## 重新构建与故障定位

先从托盘退出旧实例。还原项目依赖后，在仓库根目录运行下面的命令，再打开 [timer_note.pyw](timer_note.pyw)。源码启动器优先查找 `rounded-glass`，其次才是 `anchored`。如果只编译到默认输出目录，启动时可能仍然加载旧背景程序。

```powershell
dotnet build native/AcrylicBackdropHost/AcrylicBackdropHost.csproj -c Release --no-restore -o native/AcrylicBackdropHost/rounded-glass
```

文字消失时查 `%APPDATA%\DailyPlanner\glass_text_error.log`，背景程序启动异常时查同目录的 `acrylic_backend_error.log`。圆角试验前的本地备份为 `backups/Timer-before-round-corners-20261124-171618.zip`。重新生成的 1.1.0 安装包已包含本文记录的换行、布局编辑和整窗移动修复。

