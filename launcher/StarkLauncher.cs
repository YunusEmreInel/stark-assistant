// Stark.exe: masaüstünden çift tıklanan küçük başlatıcı. Simge exe'nin içine gömülüdür (Windows simgeyi
// ayrı .ico dosyasından aramaz). Proje sanal ortamındaki pythonw ile "python -m stark" çalıştırır.
// Her açılış %USERPROFILE%\.stark\stark_hata.log dosyasına bir satır yazar: tıklamanın ulaştığı görülebilsin.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("Stark")]
[assembly: AssemblyProduct("Stark")]
[assembly: AssemblyDescription("Stark kişisel asistan")]

static class StarkLauncher
{
    [STAThread]
    static void Main()
    {
        // Exe proje klasörünün içindeki launcher\ klasöründedir; proje kökü bir üst klasör.
        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string root = Path.GetFullPath(Path.Combine(exeDir, ".."));
        string pythonw = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        Log("başlatıcı açıldı: " + root);

        if (!File.Exists(pythonw))
        {
            Log("HATA: pythonw bulunamadı: " + pythonw);
            MessageBox.Show("Stark'ın Python ortamı bulunamadı:\n" + pythonw +
                            "\n\nProje klasörü taşındıysa kurulum betiğini yeniden çalıştırın.",
                            "Stark", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        try
        {
            var psi = new ProcessStartInfo(pythonw, "-m stark");
            psi.WorkingDirectory = root;
            psi.UseShellExecute = false;
            Process.Start(psi);
        }
        catch (Exception e)
        {
            Log("HATA: başlatılamadı: " + e.Message);
            MessageBox.Show("Stark başlatılamadı:\n" + e.Message, "Stark",
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    static void Log(string line)
    {
        try
        {
            // AppData değil: Store paketli uygulamalardan başlatılınca yönlendiriliyor (bkz. config.py)
            string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".stark");
            Directory.CreateDirectory(dir);
            // Çalışan Stark aynı dosyayı yazmak için açık tutar: paylaşımlı aç (AppendAllText burada sessizce başarısız oluyordu)
            using (var fs = new FileStream(Path.Combine(dir, "stark_hata.log"), FileMode.Append, FileAccess.Write,
                                           FileShare.ReadWrite | FileShare.Delete))
            using (var w = new StreamWriter(fs, new System.Text.UTF8Encoding(false)))
            {
                w.WriteLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " " + line);
            }
        }
        catch { }
    }
}
