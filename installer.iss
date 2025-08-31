[Setup]
AppName=PDF Reader
AppVersion=1.0
DefaultDirName={pf}\PDF Reader
DefaultGroupName=PDF Reader
OutputDir=dist
OutputBaseFilename=PDFReaderSetup
Compression=lzma
SolidCompression=yes
SetupIconFile=app\icon.ico

[Files]
Source: "dist\PDFReader.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PDF Reader"; Filename: "{app}\PDFReader.exe"; IconFilename: "app\icon.ico"
Name: "{commondesktop}\PDF Reader"; Filename: "{app}\PDFReader.exe"; IconFilename: "app\icon.ico"
