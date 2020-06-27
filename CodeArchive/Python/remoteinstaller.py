#
#Copyright 2009 VMware, Inc.  All rights reserved. -- VMware Confidential
#

"""
Module stub for communication with the remote/older VMIS installer
component.
"""

import inspect
import pickle
import io
import sys
import traceback
import vmispy

import vmis.vmisdebug as vmisdebug
import vmis.core.files as files
import vmis.util.path as path
from vmis.core.errors import *

from vmis.core.installer import Installer
from vmis.core.localinstallerops import LocalInstallerOps
from vmis.util.log import getLog
log = getLog('vmis.core.installer')

class RemoteInstaller(Installer):
    """
    Implementation of the Installer methods for remote access.

    This class will pack up remote calls and pass them off through
    the C structure to the remote installer.  It implements the
    main VMIS-side stub.
    """
    def __init__(self, remoteUID):
       self._installer = self # XXX: Probably not necessary in this class.
       self._remoteUID = remoteUID

       # Register this object with the C wrapper.  We don't need to
       #  protect this because this portion of the code is not involved
       #  in creating the bundle, only during installation/uninstallation.
       retval = vmispy.SetPythonInstallerObject(self, 0, remoteUID)

       # Could not properly parse the arguments to set the installer object.
       if retval == -1:
           raise IllegalParameters('Error passing parameters to C function SetPythonInstallerObject.')

       # Files is a list of mapping between one-to-many sources and one
       # destination.  Files are a list because order of installation
       # sometimes matters (e.g., with symlinks).  This means the order
       # of installation between a mapping of sources and destinations
       # is not guaranteed.
       self._component = None
       self._files = []
       self._permissions = []
       self._filetypes = []
       self._questions = []
       self._banner = None
       self._iconImagePaths = []
       self._headerImagePath = None

       # XXX: Rendered obsolete?  I believe so.  Check to make sure
       self._config = None

    # Outgoing methods.  These need to be overridden to convert them
    #  into messages and pass them on to the remote component.

    def whoami(self):
        """ Return the name of the calling method """
        return inspect.stack()[1][3]

    def PreTransactionInstall(self, old, new, upgrade):
       """
       Called before anything else during install.

       This is where global settings like branding should be set.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def PreTransactionUninstall(self, old, new, upgrade):
       """
       Called before anything else during uninstall.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def PostTransactionInstall(self, old, new, upgrade):
       """
       Called after everything else during install.

       This function is called after the database has been committed
       for the current component.  Since no transaction is active at
       this point, external programs may modify the installer database.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    # Note: There is no PostUninstallTransaction because there's no
    # sane way to reference a component in the database that has
    # already been deleted.  For example, if you were to call
    # PostUninstallTransaction it would fail when it tried to log the
    # component being called because its name can no longer be looked
    # up in the database.

    def InitializeQuestions(self, old, new, upgrade):
       """
       XXX: to be removed in favor of PreTransaction.

       Called for each component scheduled to be installed.

       InitializeQuestions should add (or remove) any questions to be
       asked.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def InitializeInstall(self, old, new, upgrade):
       """
       Called for each component scheduled to be installed after
       questions have been asked.

       Initialize should perform quick, fail-fast checks on the system
       to determine whether or not the component is able to be
       installed.  It should check for dependencies on the system that
       cannot be expressed otherwise.  The state of the system should
       not be modified.

       The component should also populate its file and question sets
       here.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def InitializeUninstall(self, old, new, upgrade):
       """
       Called for each component scheduled to be uninstalled.

       Initialize should perform quick, fail-fast checks on the system
       that would prevent the component from being uninstalled.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def PreInstall(self, old, new, upgrade):
       """
       Called before component installation commences.

       PreInstall should perform whatever tasks are necessary to put
       the system in a state where the component may be installed.

       PreInstall should rarely fail.  Any likely scenarios to cause
       failure should be checked for in Initialize instead.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def PostInstall(self, old, new, upgrade):
       """
       Called after a component is installed.

       PostInstall should configure the compoonent on the system.  Any
       changes made here should likely have a counterpart in
       PostUninstall.

       Example:  Making changes to a system configuration file.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def PreUninstall(self, old, new, upgrade):
       """
       Called before component uninstallation commences.

       PreUninstall should perform whatever tasks are necessary to
       decommission the component before its files are removed from the
       system.

       PreUninstall should rarely fail.  Any likely scenarios to cause
       failure should be checked for in Initialize instead.

       Example: Services must be stopped before Workstation can be
       uninstalled.  However, stopping services can fail if there are
       virtual machines running.  Instead of PreInstall failing because
       services failed to stop, Initialize should check if virtual
       machines are running in the first place.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    def PostUninstall(self, old, new, upgrade):
       """
       Called after a component is uninstalled.

       PostUninstall should unconfigure the component on the system.
       Anything changed in PostInstall should likely have a counterpart
       here.

       Example:  Undoing changes made to system configuration file.
       """
       return self.MessageOut(self.whoami(), old, new, upgrade)

    # Incoming methods will be covered by LocalInstallerOps due to
    #  inheritence.

    # XXX: The code from here down is duplicated for remoteinstallerops.py
    # and remoteinstaller.py at the moment, but with small differences.
    # Find a good way to consolidate them.
    def _rebuildArgs(self, args, kwargs):
       """
       Rebuild args that have been deconstructed into tuples.
       The tuple structure is:

       position   value
       0:         type: string
       1*:         args*: data packed into the object

       It is assumed that types can reconstruct themselves by passing
       args[1:] to __init__
       """
       for typ in [files.Destination, path.path]:
          nargs = ()
          for a in args:
              # If the argument is a tuple and the first item matches the type
              if type(a) is tuple and a[0] == str(typ):
                  dest = typ(*a[1:])
                  nargs = nargs + (dest,)
              else:
                  nargs = nargs + (a,)
          args = nargs

          # Fiddle kwargs to unpack Destinations
          for k, v in kwargs.items():
              if type(v) is tuple and v[0] == str(typ):
                  kwargs[k] = typ(*v[1:])

       return (args, kwargs)

    def _unpackSingleArg(self, arg):
        """
        Helper function for _unpackArgs.  Unpack a single argument to
        a tuple.
        """
        if type(arg) is files.Destination:
            return (str(files.Destination), arg.rawText, arg.perm, arg.fileType)
        # Treat ComponentDestinations as Destinations when outgoing.
        elif str(type(arg)) == "<class '__main__.ComponentDestination'>":
            return (str(files.Destination), arg.rawText, arg.perm, arg.fileType)
        elif type(arg) is path.path:
            return (str(path.path), str(arg))
        else:
            return arg

    def _unpackArgs(self, args, kwargs):
        """
        Scan args and kwargs for any types that need to be broken down
        into a tuple of simpler types.
        We can't allow complex objects to be transferred, as unpickling
        may not be possible.
        """
        for typ in [files.Destination]:
           nargs = ()
           for a in args:
               nargs = nargs + (self._unpackSingleArg(a),)
           args = nargs

           for k, v in kwargs.items():
               kwargs[k] = self._unpackSingleArg(v)

        return (args, kwargs)

    # Communication methods.  These two methods handle the communication
    #  with remote components, both incoming and outgoing messages and
    #  route the flow of control appropriately.
    def MessageIn(self, uid, message):
        """
        This function receives messages from remote components.  Its function
        is to unpack the message, build a function call, and pack up the
        resulting return value or exception and send it back.

        @param uid: The UID of the receiver XXX: Not used at this moment.
        @param str: The message
        """
        log.debug('RemoteInstaller received message from uid %d as: %s', uid, message)

        # Wrap everything in a try/catch
        try:
            # Unpickle the incoming message
            strio = io.BytesIO(message.encode('latin-1'))
            execmethod = pickle.load(strio, fix_imports=True)
            methodName = pickle.load(strio, fix_imports=True)
            args = pickle.load(strio, fix_imports=True)
            kwargs = pickle.load(strio, fix_imports=True)
            strio.close()

            # Verify that we have received the correct type of message.
            #  If not, raise an exception.
            if execmethod != 'ExecuteMethod':
               raise MalformedMessage('Message from remote component not properly formatted!')

            (args, kwargs) = self._rebuildArgs(args, kwargs)

            # Look up the method name on the current installer.
            method = getattr(self, methodName, None)
            if method is None:
                raise MethodNotFound('Method: %s not found on remote component stub!' % (methodName,))

            # Call the remote method and catch exceptions
            try:
                ret = method(*args, **kwargs)
            except Exception as e:
                # If there is an exception, we want to pickle it up and return.
                strioOut = io.BytesIO()

                # Get information on the exception.
                (excType, excValue, tback) = sys.exc_info()
                strList = traceback.format_exception(excType, excValue, tback)
                excValue = '%s' % excValue # Explicitly make it a string.

                # Log it if it's the first time it's been called.
                if excValue.rfind('VMIS:') == -1:
                    log.error('\n'.join(strList))
                    # Prepend VMIS: to the error text so we don't log later on
                    excValue = 'VMIS:' + excValue

                # Pickle it into strioOut
                pickle.dump('exception', strioOut, protocol=0, fix_imports=True)
                pickle.dump('%s' % excType, strioOut, protocol=0, fix_imports=True)
                pickle.dump('%s' % excValue, strioOut, protocol=0, fix_imports=True)
                self.VerifyArguments(strList)
                pickle.dump(strList, strioOut, protocol=0, fix_imports=True)
                strioOut.flush()

                # Pickle dumped result are bytes, whose type is different from the 2nd
                # parameter of the interface SetReturnValue. So, we need to convert
                # the bytes to a string. Latin-1 values are identical to 0-255, so
                # decode the bytes to latin-1. When passed to C with SetReturnValue,
                # the string is encoded with UTF-8 by Python. The length of UTF-8
                # string may be larger than latin-1's, so we get the length of the
                # string to be passed by encoding it with UTF-8 first. In this way,
                # This string's real size is equal to the variable length.
                retstr = strioOut.getvalue().decode('latin-1')
                length = len(retstr.encode('utf-8'))
                retval = vmispy.SetReturnValue(0, retstr, length) # XXX: HACK!
                return

            # Pickle and return the return argument.
            strioOut = io.BytesIO()
            pickle.dump('return value', strioOut, protocol=0, fix_imports=True)
            self.VerifyArguments(ret)
            pickle.dump(ret, strioOut, protocol=0, fix_imports=True)
            strioOut.flush()
            retstr = strioOut.getvalue().decode('latin-1') # Get the return pickled string
            length = len(retstr.encode('utf-8'))
            # The first value in SetReturnValue has been set to 0.  This
            # is the UID of the main installer.
            retval = vmispy.SetReturnValue(0, retstr, length) # XXX: HACK!
            strioOut.close() # Close the strioOut object
            return
        except Exception as e:
            log.error('RemoteInstaller exception: %s' % e)
            (excType, excValue, tback) = sys.exc_info()
            strList = traceback.format_exception(excType, excValue, tback)
            log.error('\n'.join(strList))
            retval = vmispy.SetReturnValue(0, '-1', 2) # XXX: HACK!
            return

    def MessageOut(self, methodName, *args, **kwargs):
        """
        This method is the gateway for all remote component calls.  It is
        responsible for packing the method call into a message and sending
        it out to the remote component, as well as returning the return value
        from the remote call to the calling method.

        @param methodname: The method to call on the class
        @param args: Method arguments
        @param kwargs: Method keyword arguments
        """
        (args, kwargs) = self._unpackArgs(args, kwargs)

        # Pickle the query and args and send them
        # to the other end.
        strio = io.BytesIO()
        self.VerifyArguments(methodName)
        self.VerifyArguments(args)
        self.VerifyArguments(kwargs)
        pickle.dump('ExecuteMethod', strio, protocol=0, fix_imports=True)
        pickle.dump(methodName, strio, protocol=0, fix_imports=True)
        pickle.dump(args, strio, protocol=0, fix_imports=True)
        pickle.dump(kwargs, strio, protocol=0, fix_imports=True)
        strio.flush()

        log.debug('RemoteInstaller: Executing remote method: %s with UID: %d' % (methodName, self._remoteUID))
        # XXX: Hardcoded 0 here, which is the number for the main installer
        # XXX:  but should be only set in one place.  Pass in from the C shell.
        retval = vmispy.RunExternalMethod(self._remoteUID, 0, strio.getvalue().decode('latin-1'))
        log.debug('Back in RemoteInstaller with return value!')

        # If the return value is empty, then simply return None.  Something
        # happened upstream that did not return a good value, and Pickle can't
        # handle None.  (Example: RunCommand died.  I need to track this one
        # down: XXX)
        if not retval:
           return None

        strio.close() # No more ops on the string

        # Interpret the return value and pass it back to the calling method.
        strin = io.BytesIO(retval.encode('latin-1'))
        retType = pickle.load(strin, fix_imports=True)

        # Check if ret is an exception.  If so, we need to raise it here.
        if retType == 'exception':
            # Check the exception type and raise it.
            excepType = pickle.load(strin, fix_imports=True)
            excepValue = pickle.load(strin, fix_imports=True)
            excepStr = pickle.load(strin, fix_imports=True)

            typ = '%s' % excepType
            # These come in the form: <class '__main__.MyError'>
            # Pare it down to the exception class, and grab the Exception type
            typ = typ.split("'")[1] # Grab text in quotes
            typ = typ.split(".")    # Split by .
            typ = typ[len(typ) - 1] # grab the last class name.  It's the one we want
            execType = None
            # First search our global space for errors.
            try:
               execType = globals()[typ]
            except KeyError:
               pass
            # If the exception doesn't exist in the global dict, check against
            # exceptions.
            if not execType:
               try:
                  import exceptions
                  execType = getattr(exceptions, typ)
               except:
                  pass
            # If the exception has been found, raise it, otherwise just
            # raise a generic exception.
            if execType:
               raise execType(excepValue)
            else:                          # Or raise a generic exception
               raise Exception(excepValue)

        elif retType == 'return value':
            # Grab the return type and pass it back
            ret = pickle.load(strin, fix_imports=True)
            return ret
        else:
            raise TypeError('Unknown return type: %s' % retType)
