using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace AcrylicBackdropHost
{
    internal sealed class BackdropHostForm : Form
    {
        private const int WM_APP = 0x8000;
        internal const int WM_SET_GLASS_PARAMETERS = WM_APP + 0x42;
        private const int WS_EX_TOOLWINDOW = 0x80;
        private const int WS_EX_NOACTIVATE = 0x08000000;
        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint SWP_SHOWWINDOW = 0x0040;
        private const uint SWP_NOOWNERZORDER = 0x0200;

        private readonly IntPtr clientHwnd;
        [DllImport("user32.dll")]
        private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
        private IntPtr parentHwnd => GetAncestor(clientHwnd, 2);
        private readonly Timer trackingTimer = new Timer { Interval = 50 };
        [DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hwnd);
        [DllImport("user32.dll")]
        private static extern IntPtr GetWindow(IntPtr hwnd, uint command);
        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref uint value, int size);
        [StructLayout(LayoutKind.Sequential)]
        private struct AccentPolicy { public int State, Flags; public uint Color; public int Animation; }
        [StructLayout(LayoutKind.Sequential)]
        private struct AttributeData { public int Attribute; public IntPtr Data; public int Size; }
        [StructLayout(LayoutKind.Sequential)]
        private struct Margins { public int Left, Right, Top, Bottom; }
        [DllImport("user32.dll")]
        private static extern bool SetWindowCompositionAttribute(IntPtr hwnd, ref AttributeData data);
        [DllImport("dwmapi.dll")]
        private static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref Margins margins);

        private void ApplyMaterial(float translucency)
        {
            var margins = new Margins { Left = -1, Right = -1, Top = -1, Bottom = -1 };
            DwmExtendFrameIntoClientArea(Handle, ref margins);
            uint border = 0xFFFFFFFE;
            uint corners = 2; // DWMWCP_ROUND on the borderless material window.
            DwmSetWindowAttribute(Handle, 34, ref border, 4);
            DwmSetWindowAttribute(Handle, 33, ref corners, 4);
            bool micaMode = translucency < 100;
            var policy = new AccentPolicy {
                State = micaMode ? 4 : 3,
                Flags = micaMode ? 2 : 0,
                Color = micaMode ? (3u << 24) | 0x00E6E8EA : 0u };
            IntPtr memory = Marshal.AllocHGlobal(Marshal.SizeOf(policy));
            try {
                Marshal.StructureToPtr(policy, memory, false);
                var data = new AttributeData { Attribute = 19, Data = memory, Size = Marshal.SizeOf(policy) };
                if (!SetWindowCompositionAttribute(Handle, ref data))
                    throw new InvalidOperationException("Windows could not enable the acrylic backdrop.");
            } finally { Marshal.FreeHGlobal(memory); }
        }

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(IntPtr hwnd, IntPtr hwndInsertAfter,
            int x, int y, int width, int height, uint flags);

        [DllImport("user32.dll")]
        private static extern bool IsWindow(IntPtr hwnd);

        public BackdropHostForm(IntPtr parent, float translucency)
        {
            clientHwnd = parent;
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            TopMost = true;
            BackColor = System.Drawing.Color.Black;
            Text = $"DailyPlanner-Acrylic-{parent.ToInt64():X}";
            if (!GetWindowRect(clientHwnd, out RECT initial))
                throw new InvalidOperationException("Planner window has closed.");
            Bounds = Rectangle.FromLTRB(initial.Left + 6, initial.Top + 6, initial.Right - 6, initial.Bottom - 6);

            ApplyMaterial(translucency);

            trackingTimer.Tick += (sender, e) => {
                if (!IsWindow(parentHwnd)) { Close(); return; }
                if (!IsWindowVisible(parentHwnd)) {

                    Hide();
                    return;
                }
                if (!Visible) Show();
                PlaceBehindParent();

            };
            trackingTimer.Start();
        }

        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            PlaceBehindParent();
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            trackingTimer.Stop();
            trackingTimer.Dispose();

            base.OnFormClosed(e);
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams parameters = base.CreateParams;
                parameters.ExStyle |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
                return parameters;
            }
        }

        protected override bool ShowWithoutActivation => true;

        protected override void WndProc(ref Message message)
        {
            if (message.Msg == WM_SET_GLASS_PARAMETERS)
            {
                float translucency = Math.Max(0.0f, Math.Min(100.0f, message.LParam.ToInt32()));
                ApplyMaterial(translucency);
                message.Result = IntPtr.Zero;
                return;
            }

            base.WndProc(ref message);
        }

        public void PlaceBehindParent()
        {
            if (!IsWindow(parentHwnd))
            {
                Close();
                return;
            }

            if (GetWindowRect(clientHwnd, out RECT rect))
            {
                var bounds = Rectangle.FromLTRB(rect.Left + 6, rect.Top + 6, rect.Right - 6, rect.Bottom - 6);
                if (Bounds == bounds) return;
                SetWindowPos(Handle, parentHwnd, bounds.X, bounds.Y, bounds.Width, bounds.Height,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_NOOWNERZORDER | 0x0004); // SWP_NOZORDER
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    }
}
