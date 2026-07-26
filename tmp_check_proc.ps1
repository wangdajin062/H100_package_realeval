Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*experiments.runner*--exp 6,8*" } |
  Select-Object ProcessId, CommandLine |
  Format-List
