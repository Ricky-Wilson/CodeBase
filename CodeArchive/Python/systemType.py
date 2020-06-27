def SystemType():
   """
   Returns a tuple of results for the system found.
   (sysName = 'Ubuntu', 'RHEL', 'SLE', 'Fedora', or None
    sysVersion = The system version or None
    sysExtra) = Desktop or Server (RHEL, SLE) or None
   """
   # We must scan through these in order.  SuSE systems for example
   # have a /etc/lsb-release file AND a /etc/SuSE-release file.  The
   # latter contains the right information.
   possibles = ('/etc/lsb-release', '/etc/redhat-release',
                '/etc/SuSE-release', '/etc/fedora-release')

   txt = ''
   for p in possibles:
      fil = path(p)
      if fil.exists():
         txt = fil.text()

   if txt == '':
      log.Warn('No release file found...')
      return (None, None, None)

   sysName = ''
   sysVersion = ''
   sysExtra = ''

   # All sorts of things can go wrong with this...  Let's not die if it does.
   try:
      if re.findall('DISTRIB_ID=Ubuntu', txt):
         sysName = 'Ubuntu'
         mt = re.findall('DISTRIB_RELEASE=\d+\.\d+', txt)
         sysVersion = re.sub('DISTRIB_RELEASE=', '', mt[0])

      elif re.findall('Red Hat Enterprise Linux', txt):
         sysName = 'RHEL'
         mt = re.findall('elease \d+\.\d+', txt)
         sysVersion = re.sub('elease ', '', mt[0])
         mt = re.findall('Enterprise Linux \w+', txt)
         sysExtra = re.sub('Enterprise Linux ', '', mt[0])

      elif re.findall('SUSE Linux Enterprise', txt):
         sysName = 'SLE'
         mt = re.findall('VERSION = \d+', txt)
         sysVersion = re.sub('VERSION = ', '', mt[0])
         mt = re.findall('Enterprise \w+ ', txt)
         sysExtra = re.sub('Enterprise ', '', mt[0])

      elif re.findall('Fedora release', txt):
         sysName = 'Fedora'
         mt = re.findall('Fedora release \d+', txt)
         sysVersion = re.sub('Fedora release ', '', mt[0])

      elif re.findall('CentOS .*release', txt):
         sysName = 'CentOS'
         mt = re.findall('elease \d+\.\d+', txt)
         sysVersion = re.sub('elease ', '', mt[0])

   except Exception:
      log.Warn('Not fatal: Could not determine system type...  Exception caught.')
      log.Warn('Found text reads:')
      log.Warn(txt)
      pass

   # If we didn't find a sysName, then we don't have any useful system information.
   if sysName == '':
      return (None, None, None)

   return (sysName, sysVersion, sysExtra)
