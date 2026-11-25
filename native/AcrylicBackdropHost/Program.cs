using System;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace AcrylicBackdropHost
{
    internal static class Program
    {
        [DllImport("user32.dll")]
        private static extern bool SetProcessDpiAwarenessContext(IntPtr value);

        [STAThread]
        private static void Main(string[] args)
        {
            SetProcessDpiAwarenessContext(new IntPtr(-4));
            if (args.Length < 3 || !long.TryParse(args[0], NumberStyles.HexNumber,
                                                  CultureInfo.InvariantCulture, out long parent))
            {
                return;
            }

            float blur = float.TryParse(args[1], NumberStyles.Float,
                                        CultureInfo.InvariantCulture, out float parsedBlur)
                ? parsedBlur : 18.0f;
            float translucency = float.TryParse(args[2], NumberStyles.Float,
                                                CultureInfo.InvariantCulture, out float parsedTranslucency)
                ? parsedTranslucency : 100.0f;

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            try
            {
                Application.Run(new BackdropHostForm(new IntPtr(parent), translucency));
            }
            catch (Exception error)
            {
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                string logPath = Path.Combine(appData, "DailyPlanner", "acrylic_backend_error.log");
                Directory.CreateDirectory(Path.GetDirectoryName(logPath));
                File.WriteAllText(logPath, error.ToString());
            }
        }
    }
}
