"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

"""

class Version(str):
   """
   Class for comparing versions

   @warning: e.x.p is handled in a way that breaks symmetry. If e.x.p is on
   @warning:  either side in the comparator (_cmp), it will always return 1,
   @warning:  indicating that the left-hand side is greater. This means that
   @warning:  e.x.p > * and * > e.x.p, but a less than operation with an e.x.p
   @warning:  thrown in will always fail
   """

   def __new__(cls, version):
      if not version:
         raise AttributeError('version must be a non-empty string')

      return super(Version, cls).__new__(cls, version)

   def __str__(self):
      if self._text is None:
         return str('')
      else:
         return str(self._text);

   def __init__(self, version):
      """
      Input may be integer, long, or string.
      3, '1.5', '1.5-3' are allowed
      floats, ie: 1.5 are not allowed
      -1 = No version
      'e.x.p' is a special case.
      """
      if isinstance(version, int):
         self._version = (version,)
         self._text = repr(version)
      elif (version == '-1'):
         self._version = (-1, )
         self._text = version
      elif version != 'e.x.p':
         self._text = version
         split = version.split('.')

         # Trim trailing 0's so that comparisons like (1, 5, 0) and (1, 5)
         # and (1, 5, 0, 0) will all be the same.
         self._trimZeros(split)

         if not split:
            raise AttributeError('version must not be version 0')

         last = split[-1]
         minor = last.split('-')
         if minor != None:
            del split[-1] # Remove the split item.
            split += minor

         self._trimZeros(split)

         split = [int(x) for x in split]

         self._version = split
      else:  # The only way to get here is if version == 'e.x.p'
         self._version = version
         self._text = version

      super(Version, self).__init__()

   def _trimZeros(self, version):
      """
      Remove all trailing 0's from version

      @param version: list of elements representing a version
      @returns: None; version is modified
      """
      while version:
         last = version.pop()

         if last not in ('0', 0):
            version.append(last)
            break

   def __le__(self, other):
      return self.__lt__(other) or self.__eq__(other);

   def __lt__(self, other):
      return self._cmp(other) == -1

   def __ge__(self, other):
      return self.__gt__(other) or self.__eq__(other);

   def __gt__(self, other):
      return self._cmp(other) == 1

   def __eq__(self, other):
      if not isinstance(other, Version): other = Version(other)
      return (super(Version, self).__eq__('e.x.p') and super(Version, other).__eq__('e.x.p')) \
                                       or self._cmp(other) == 0

   def _cmp(self, other):
      """
      Compare version self to other returning -1 if self is less than
      other, 0 if self is equal to other, or 1 if self is greater than
      other.
      """
      if not isinstance(other, Version):
         if isinstance(other, str):
            other = Version(other)
         else:
            raise TypeError('other is not of type Version, LongVersion or basestring')

      # This special case is necessary for __gt__ and __lt__ to function on
      # e.x.p versions. Note that _cmp and == will not necessarily give the same
      # results, so use these carefully
      # e.x.p > * and * > e.x.p
      if super(Version, self).__eq__('e.x.p') or super(Version, other).__eq__('e.x.p'):
         return 1
      else:
         return (self._version > other._version) - (self._version < other._version)

   def __repr__(self):
      return "%s('%s')" % (self.__class__.__name__, self._text)

class LongVersion(Version):
   """
   Class for comparing versions with build numbers

   @warning: e.x.p is handled in a way that breaks symmetry. If e.x.p is on
   @warning:  either side in the comparator (_cmp), it will always return 1,
   @warning:  indicating that the left-hand side is greater. This means that
   @warning:  e.x.p > * and * > e.x.p, but a less than operation with an e.x.p
   @warning:  thrown in will always fail. The same operation applies for build
   @warning:  number zero when the version numbers match
   """
   def __new__(cls, version, buildNumber = -1):
      return super(LongVersion, cls).__new__(cls, version)

   def __init__(self, version, buildNumber = -1):
      """
      Input is expected to be the same as to Version, except with a build
      number optionally appended after a third period. If no build number
      is found, it is assumed to be -1
      """
      if not isinstance(buildNumber, int):
         buildNumber = int(buildNumber)
      if isinstance(version, int) or version == '-1' or version == 'e.x.p':
         super(LongVersion, self).__init__(version)
         self.buildNumber = buildNumber
      else:
         super(LongVersion, self).__init__(version)
         if buildNumber >= 0:
            self.buildNumber = buildNumber
         elif len(self._version) > 3:
            self.buildNumber = self._version.pop()
         else:
            self.buildNumber = -1
      self._text += '.%i' % self.buildNumber

   def __eq__(self, other):
      """
      Return true if self is equal to other. Note that due to inheritance
      woes, there is a hack which is documented below
      """
      if not isinstance(other, Version):
         other = LongVersion(other)
      # XXX: super must see the build numbers as equal and nonzero because
      # XXX:  super.__eq__ calls _cmp, which calls our _cmp
      sBuildNumber = self.buildNumber
      oBuildNumber = other.buildNumber
      self.buildNumber = -1
      other.buildNumber = -1
      eqres = super(LongVersion, self).__eq__(other)
      self.buildNumber = sBuildNumber
      other.buildNumber = oBuildNumber
      return eqres and self.buildNumber == other.buildNumber

   def _cmp(self, other):
      """
      Compare version and build number self to other returning -1 if
      self is less than other, 0 if self is equal to other, or 1 if
      self is greater than other.
      """
      if not isinstance(other, Version):
         if isinstance(other, str):
            other = Version(other)
         else:
            raise TypeError('other is not of type Version, LongVersion or basestring')

      verCmp = super(LongVersion, self)._cmp(other)
      if verCmp:
         return verCmp

      # This case is analogous to the e.x.p case above: there is a special case
      # whereby _cmp will return 1 but __eq__ will return True
      if self.buildNumber == 0 or other.buildNumber == 0:
         return 1
      else:
         return (self.buildNumber > other.buildNumber) - (self.buildNumber < other.buildNumber)

   def __hash__(self):
      return hash(self._text)
