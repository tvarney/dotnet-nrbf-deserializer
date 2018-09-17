
if exist %WINDIR%\Microsoft.NET\Framework\v4.0.30319\Microsoft.Net.Compilers.2.9.0/tools/csc.exe (
    %WINDIR%\Microsoft.NET\Framework\v4.0.30319\Microsoft.Net.Compilers.2.9.0\tools\csc.exe Program.cs
) else (
    if exist %WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe (
        %WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe Program.cs
    ) else (
        echo "Can not find C# Compiler"
    )
)
