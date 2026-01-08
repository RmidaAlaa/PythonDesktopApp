PREREQUISITES FOR INSTALLER BUILD
=================================

Current Status:
--------------
1. Drivers (ST-Link and CP210x):
   - Extracted to 'stlink/' and 'cp210x/' folders.
   - Ready for packaging.

2. Visual C++ Redistributable:
   - File present: 'VC_redist.x86.exe' (32-bit).
   - REQUIRED: 'vc_redist.x64.exe' (64-bit).
   - ACTION: Please download the x64 version from Microsoft and place it here, renaming it to 'vc_redist.x64.exe'.
   - The installer script expects the x64 version because the application is 64-bit.

3. Inno Setup Compiler:
   - Status: Not found in standard paths.
   - ACTION: Install Inno Setup 6 (https://jrsoftware.org/isdl.php).

How to Build:
------------
1. Ensure 'vc_redist.x64.exe' is present in this folder.
2. Open '..\setup.iss' with Inno Setup Compiler.
3. Click "Build" (or Run).
