"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
"""

from binascii import crc32
from xml import etree
import struct

from io import StringIO
from vmis.core.dependency import Version
from vmis.core.component import ComponentFileObj, FileComponent
from vmis.core.errors import BundleError
from vmis.core import common
from vmis.util.log import getLog

log = getLog('vmis.core.bundle')

class ComponentEntry(object):
   """ Simple class that represents a component in the component list """

   def __init__(self, name, offset, size):
      self.name = name
      self.offset = offset
      self.size = size

   @staticmethod
   def CreateFromXML(component):
      """
      Creates a ComponentEntry from the XML

      @param component: component XML fragment
      @returns:         deserialized ComponentEntry
      """
      name           = component.attrib['name']
      offset         = int(component.attrib['offset'])
      size           = int(component.attrib['size'])

      return ComponentEntry(name, offset, size)

class Components(object):
   """ Simple class containing the collection of components """
   def __init__(self):
      self.components = []

   def __iter__(self):
      """ Returns a simple iterator on the internal components list """
      return iter(self.components)

   def __contains__(self, e):
      """ Returns True if element e is in the name of components """
      for component in self.components:
         if component.name == e:
            return True

      return False

   @staticmethod
   def CreateFromXML(components):
      return [ComponentEntry.CreateFromXML(c) for c in components.findall('component')]

class Bundle(object):
   MAGIC_NUMBER     = 0x36158611
   FOOTER_FORMAT    = '=QIIIIIIIIIII' # If you change this must also change bundle-header
   FOOTER_SIZE      = struct.calcsize(FOOTER_FORMAT)

   def __init__(self, coreVersion, components, productComponents):
      """
      @param coreVersion:  version of targetted VMIS
      @param components:   components listing
      @param productComponents: components belonging to the product
      """
      self.coreVersion = coreVersion
      self.components = components
      self.productComponents = productComponents

   @classmethod
   def LoadBundle(cls, source):
      """
      Creates a bundle from the given path.

      @param source: file object of the bundle
      """
      source.seek(-Bundle.FOOTER_SIZE, 2)
      header = source.read(Bundle.FOOTER_SIZE)

      try:
         dataSize, dataOffset, manifestSize, manifestOffset, payloadSize, payloadOffset, \
             launcherSize, presize, preoffset, version, checksum, magicNumber = \
             struct.unpack(Bundle.FOOTER_FORMAT, header)
      except struct.error:
         raise BundleError('Unable to unpack header')

      if magicNumber != Bundle.MAGIC_NUMBER:
         raise BundleError('Magic number of %#x does not match' % magicNumber)

      calcChecksum = cls.CalculateChecksum(header[0:-8])
      if calcChecksum != checksum:
         raise BundleError('Calculated checksum %d does not match expected %d' % \
                           (calcChecksum, checksum))

      source.seek(manifestOffset)
      manifest = source.read(manifestSize)
      if len(manifest) != manifestSize:
         raise BundleError('Unable to read manifest')

      log.debug('Loaded bundle manifest:\n%s', manifest)

      tree = etree.ElementTree.fromstring(manifest)
      bundle = tree.find('.')

      product = bundle.find('product')

      coreVersion = product.find('coreVersion').text
      coreVersion = Version(coreVersion) # Convert to Version object

      productComponents = [c.get('ref') for c in product.findall('components/component/[@ref]')]

      # XXX: Check coreVersion to make sure it is correct.  May have
      # @todo: to relaunch with the right core version.

      xmlComponents = bundle.find('components')
      components = Components.CreateFromXML(xmlComponents)

      loaded = []
      for c in components:
         componentFileObj = ComponentFileObj(source, dataOffset + c.offset,
            dataOffset + c.offset + c.size)
         comp = FileComponent.LoadComponent(componentFileObj)

         if comp.name in productComponents:
            comp.bonus = True
            comp.cachedBonus = True # Set the cached value to True as well

         loaded.append(comp)
         common.repository.Add(comp)

      return Bundle(coreVersion=coreVersion, components=loaded,
                    productComponents=productComponents)

   @staticmethod
   def CalculateChecksum(header):
      """ Calculate a CRC32 checksum from the given header bytes """
      return crc32(header) & 0xffffffff # XXX: Python bug 1202
