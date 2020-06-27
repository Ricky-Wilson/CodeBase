import os, apport.packaging, re
from apport.hookutils import *

def add_info(report):
	# the issue is not in the unity-settings-daemon code so reassign
	if "Stacktrace" in report and "/usr/libg/nome-settings-daemon-3.0" in report["Stacktrace"]:
		for words in report["Stacktrace"].split():
			if words.startswith("/usr/lib/unity-settings-daemon-3.0"):
			    if apport.packaging.get_file_package(words) != 'unity-settings-daemon':
    				report.add_package_info(apport.packaging.get_file_package(words))
    				return    			
    		    # update the title to reflect the component and tab	
			    component = re.compile("lib(\w*).so").search(words).groups(1)[0]
			    report['Title'] = '[%s]: %s' % (component, report.get('Title', report.standard_title()))
			    report['Tags'] = '%s %s' % (report.get('Tags', ""), component)
			    break # Stop on the first .so that's the interesting one
