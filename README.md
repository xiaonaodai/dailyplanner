# DailyPlanner

A lightweight Windows desktop planner that keeps your schedule visible in a floating sticky-note window. It shows the current task and its countdown, and reminds you when a time block ends.

## Screenshots



![Today's schedule](screenshots/planner.png)

## Features

- Create and edit time blocks, task descriptions, and end-of-task reminders.
- See the active task and remaining time at a glance.
- Customize the note and frame colors, and reposition or resize the interface.
- Use the notification-area icon to reopen the app or quit it.
- Switch the interface between English and Chinese.
- Install to a folder of your choice with a desktop shortcut.

## Download and install

1. Open the project’s **Releases** page on GitHub.
2. Download `DailyPlanner-Setup.exe`.
3. Choose English or Simplified Chinese in the installer, then choose an installation folder.
4. Launch **DailyPlanner** from the desktop shortcut or Start menu.

Closing the note window sends the app to the notification area. Click the tray icon to reopen it; right-click the icon for the menu.

## Build from source

### Requirements

- Windows 10 or later
- Python 3.12 or later
- Inno Setup 6

### Build the installer

Open PowerShell in the project folder and run:

```powershell
python -m pip install pyinstaller pystray pillow
.\package_app.ps1
ISCC.exe .\DailyPlanner.iss
```

The installer is created at `release\DailyPlanner-Setup.exe`. The `release` directory is generated output and is not required in the source repository or for end users who download the installer.

## Data and privacy

Schedules and preferences are stored locally in `%APPDATA%\DailyPlanner`. Uninstalling the app leaves this folder in place so personal plans are not deleted. The sample `schedule.json` and `settings.json` in this repository contain generic defaults; do not commit personal schedules or settings.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

---

# 今日计划

一款轻量的 Windows 桌面计划工具。它以悬浮便签的形式显示日程、当前任务和倒计时，并在时间段结束时提醒你。

![今日计划（中文界面）](screenshots/planner-zh.png)

## 功能

- 新建和编辑时间段、工作内容及结束提醒。
- 一眼查看当前任务和剩余时间。
- 自定义便签纸和边框颜色，调整组件布局及窗口大小位置。
- 通过右下角通知区域图标重新打开或退出程序。
- 在中文和 English 界面之间切换。
- 安装时可选择文件夹，并创建桌面快捷方式。

## 下载和安装

1. 打开 GitHub 项目的 **Releases** 页面。
2. 下载 `DailyPlanner-Setup.exe`。
3. 在安装程序中选择 English 或简体中文，再选择安装文件夹。
4. 从桌面快捷方式或开始菜单启动 **DailyPlanner**。

关闭便签窗口后，程序会收进右下角通知区域。点击托盘图标可重新打开，右键图标可显示菜单。

## 从源码构建

### 环境要求

- Windows 10 或更高版本
- Python 3.12 或更高版本
- Inno Setup 6

### 构建安装包

在项目文件夹中打开 PowerShell，运行：

```powershell
python -m pip install pyinstaller pystray pillow
.\package_app.ps1
ISCC.exe .\DailyPlanner.iss
```

安装包生成于 `release\DailyPlanner-Setup.exe`。`release` 是构建生成目录，不需要提交到源码仓库；普通用户下载安装包即可，无需安装 Python。

## 数据与隐私

计划和偏好设置保存在本机 `%APPDATA%\DailyPlanner`。卸载程序会保留此文件夹，避免误删个人计划。仓库中的 `schedule.json` 和 `settings.json` 仅包含通用默认值；请勿提交个人日程或设置。

## 许可证

本项目使用 MIT 许可证，详情见 [LICENSE](LICENSE)。


