"""
Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential

"""

import os

from vmis import vmisdebug
from vmis.util.log import getLog
from vmis.core.errors import ConflictError, UnsatisfiedDependency, DowngradeError, \
   VersionError, CycleError, InvalidInstallError
from vmis.core.version import Version, LongVersion
from functools import cmp_to_key
import traceback

log = getLog('vmis.core.dependency')

# Variables for dependency recursion debugging
recCounter=1
recDict={}
recDict[""] = 0

class Op:
    """ Operator Enum """
    unknown, LT, LE, EQ, GE, GT, NE = list(range(7))

def printDepGraph(text):
    """
    Passthrough to print out a node in the dependency graph in .dot format if VMWARE_VMIS_PRINT_DEP_GRAPH
    is set.  This allows for an easy visualization of the search tree.
    """
    if os.environ.get('VMWARE_VMIS_PRINT_DEP_GRAPH'):
        print(text)

def debuglog(*args):
    """
    Passthrough that allows a quick switch to prints when debugging.
    This sort of thing isn't usually necessary, but when
    running our unit tests, prints are much more useful.
    """
    log.debug(args)

def throwConflictError(nlName, nlVer, conflict1, ilName, ilVer, conflict2):
   """
   Raise an appropriate conflict error

   @param nlName: Long name of the new component
   @param nlVer: Version of the new component
   @param conflict1: None or the Conflict object if the new component has this conflict
   @param ilName: Long name of the installed component
   @param ilVer: Version of the installed component
   @param conflict2: None or the Conflict object if the installed component has this conflict

   Raises a ConflictError in all cases
   """
   if conflict1:
      if conflict1.version == "0.0.1": # Special case
         raise ConflictError('Cannot install %s while %s %s is installed.  Please uninstall %s %s'
                             ' and run the installer again.  Aborting installation.' %
                             ( nlName,
                               ilName, ilVer,
                               ilName, ilVer))
      else:
         raise ConflictError('Cannot install %s %s version %s while %s %s is installed.  Please uninstall %s %s'
                             ' and run the installer again.  Aborting installation.' %
                             ( nlName, conflict1.opAsString(), conflict1.version,
                               ilName, ilVer,
                               ilName, ilVer))
   elif conflict2:
      if conflict2.version == "0.0.1": # Special case
         raise ConflictError('Cannot install %s %s while %s is installed.  Please uninstall %s %s'
                             ' and run the installer again.  Aborting installation.' %
                             ( nlName, nlVer,
                               ilName,
                               ilName, ilVer))
      else:
         raise ConflictError('Cannot install %s %s while %s %s version %s is installed.  Please uninstall %s %s'
                             ' and run the installer again.  Aborting installation.' %
                             ( nlName, nlVer,
                               ilName, conflict2.opAsString(), conflict2.version,
                               ilName, ilVer))
   else:
      raise ConflictError('Cannot install %s %s and %s %s.  Aborting installation.' %
                          ( nlName, nlVer,
                            ilName, ilVer))


class VersionedObject(object):
   """ Parent class for dependencies and conflicts

       NOTE: Version 0.0.1 is used as a special case for conflicts, to denote a conflict
             against the entire component.  Conflict syntax is set, so we're stuck with it.
   """

   # Set up a hash of string to Op and vice versa.
   ops = {}
   strings = {}
   for (strng, operator) in [('<',  Op.LT),
                             ('<=', Op.LE),
                             ('=',  Op.EQ),
                             ('>=', Op.GE),
                             ('>',  Op.GT),
                             ('!=', Op.NE)]:
      ops[strng] = operator
      strings[operator] = strng

   def __str__(self):
       """
       Print this object
       """
       strparts = []
       if self.optional:
         strparts = ['Opt:']
       strparts.extend([str(self.name), self.strings[self.op], str(self.version)])

       return ''.join(strparts)

   def __init__(self, str, optional = False):
      """
      Split the string into component, operation, and version
      information.
      """
      tmp = None

      self.optional = optional
      if str.startswith('Opt:'):
         self.optional = True
         str = str[4:]

      # XXX: This if/else nastiness doesn't seem to be avoidable.
      #  The two char operators have to be checked first since they
      #  contain the one char operators.
      if '!=' in str:
         tmp = str.split('!=')
         self.op = Op.NE
      elif '>=' in str:
         tmp = str.split('>=')
         self.op = Op.GE
      elif '<=' in str:
         tmp = str.split('<=')
         self.op = Op.LE
      elif '<' in str:
         tmp = str.split('<')
         self.op = Op.LT
      elif '>' in str:
         tmp = str.split('>')
         self.op = Op.GT
      elif '=' in str:
         tmp = str.split('=')
         self.op = Op.EQ
      else:
         # Operator is unknown.
         # Throw a fatal error.  This should *not* be allowed to happen.
         raise VersionError('Dependencies: Incorrect operator supplied in string: %s.' % str)

      # Name before op, Version after, that's it.
      assert len(tmp) == 2
      self.name = tmp[0]
      self.version = Version(tmp[1])
      self.longVersion = LongVersion(tmp[1])

   def opAsString(self):
       return(self.strings[self.op])

   def isMatch(self, comp):
       """
       Return true if the component satisfies the (in)equality, false otherwise
       """
       # XXX: Is there a better way to do this in Python?

       if self.name == comp.name:
          # Create a set lambdas for possible operations
          match = { Op.EQ: lambda other, ours: other == ours,
                    Op.NE: lambda other, ours: other != ours,
                    Op.GT: lambda other, ours: other > ours,
                    Op.LT: lambda other, ours: other < ours,
                    Op.GE: lambda other, ours: other >= ours,
                    Op.LE: lambda other, ours: other <= ours }

          # Call the appropriate lambda
          return match[self.op](comp.version, self.version)

       return False

class Dependency(VersionedObject):
   """ Dependency object.  Essentially just a VersionedObject with a new name"""

class Conflict(VersionedObject):
   """ Conflict object.  Essentially just a VersionedObject with a new name"""

class ComponentState:
   """ Component State Enum """
   UNKNOWN, INSTALLED, TO_INSTALL = list(range(3))

class DependencyGraph(object):
   """
   A graph or subgraph of DependencyNode

   Graphs are collections of DependencyNode as vertices, which are connected in
   various ways: they can either have no relation, a parent-child (directed)
   relation, or a conflict (undirected) relation. The parent-child relation
   signifies that the parent depends on the child. The conflict relation
   signifies that both cannot be on the system at the same time. Note that since
   these relations require synchronization of information, one should not tinker
   with the internal structure directly
   """

   def __init__(self):
      self._graph = {} # Dict, keyed on Component.name, of Dict, keyed on Component.longVersion, of DependencyNode

   def logList(self):
       for n in self.nodeNames():
          debuglog(self.nodesSorted(n))

   def printList(self):
       for n in self.nodeNames():
          print(("     ", self.nodesSorted(n)))

   def addNode(self, node):
      """
      Add a DependencyNode to the graph, if it is not in the graph already

      @param node: The DependencyNode that should be added to the graph

      @returns: true if the node was added, or false if the node was already there
      """
      if node.component.name in self._graph:
         if node.component.longVersion in self._graph[node.component.name]:
            debuglog('Add attempt failed')
            debuglog('Subgraph: %r' % self._graph[node.component.name])
            debuglog('Version: %r' % node.component.longVersion)
            return False
         self._graph[node.component.name][node.component.longVersion] = node
      else:
         self._graph[node.component.name] = { node.component.longVersion: node }
      return True

   def removeNode(self, node):
      """
      Remove a DependencyNode from the graph

      @param node: The node that should be removed from the graph

      @returns: true if the node was removed, or false if it wasn't in the graph
      """
      if node.component.name not in self._graph:
         return False
      if node.component.longVersion not in self._graph[node.component.name]:
         return False
      del self._graph[node.component.name][node.component.longVersion]
      if not self._graph[node.component.name]:
         del self._graph[node.component.name]
      return True

   def upgradeToNode(self, node):
      """
      Remove all nodes in the version pool that are not this node, and make this
      the only version of the component in the graph

      @param node: The node that hsould be the only remaining node in the version pool

      @returns: A dict of all of the nodes that were removed from the version
                pool, keyed by longVersion
      """
      if node.component.name in self._graph:
         oldNodes = self._graph[node.component.name]
         self._graph[node.component.name] = { node.component.longVersion: node }
         if node.component.longVersion in oldNodes:
            del oldNodes[node.component.longVersion]
         return oldNodes
      else:
         self._graph[node.component.name] = { node.component.longVersion: node }
         return {}

   def lookupNode(self, name, version):
      """
      Retrieve a DependencyNode based on its name and version

      @param name: The name of the component
      @param version: The LongVersion of the component

      @returns: The node associated with these values, or None if one is not on
                the graph
      """
      if name not in self._graph:
         return None
      return self._graph[name].get(version)

   def nodesFor(self, name):
      """
      Retrieve a dict of DependencyNode based on its name

      @param name: The name of the components to get

      @returns: A dict, keyed on Component.longVersion of all the DependencyNode
                that have this name
      """
      return dict(self._graph.get(name) or {})

   def nodesSorted(self, name, ascending = True):
      """
      Retrieve a list of DependencyNode for this name, sorted by precedence
      (primarily version number, then build number, but with a few exceptions)
      in the order specified

      @param name: The name of the components to get
      @param ascending: Whether the list should be in ascending or descending order

      @returns: A list of Dependency node, sorted as specified
      """
      if name not in self._graph:
         return []
      nodes = list(self._graph[name].values())
      if ascending:
         nodes = sorted(nodes, key=cmp_to_key(DependencyNode._cmp))
      else:
         nodes = sorted(nodes, key=cmp_to_key(DependencyNode._cmp), reverse=True)
      return nodes

   def nodeNames(self):
      """
      Retrieve a list of the names of all DependencyNode in the graph

      @returns: A list of the names of all the DependencyNode in the graph, in
                no specific order
      """
      return list(self._graph.keys())

   def nodesMatching(self, func, ascending = True):
      """
      Retrieve a list of all nodes that pass the function passed

      @param func: A function that takes DependencyNode and returns a boolean
      @param ascending: If the results should be sorted ascending or descedning
                        inside of the partition for components of the same name

      @returns: A list of nodes for which func returned true, sorted within
                partitions of nodes of the same name.  The partitions themselves
                are not sorted
      """
      passed = []
      for name in self.nodeNames():
         for node in self.nodesSorted(name, ascending):
            if func(node):
               passed.append(node)
      return passed

   def constructLinks(self, installed, constructConflicts = True, force = False):
      """
      Construct the links between the vertecies of this graph

      @param installed: The list of installed components.  This is used to
                        give proper error messages.
      @param constructConflicts: Specify whether, in addition to construction
                                 links for dependencies, links for conflicts
                                 should be constructed as well
      @param force: If false, dependency links not being able to be constructed
                    will raise an UnsatisfiedDependency exception

      @raises UnsatisfiedDependency: If force is not true, dependency links that
                                     cannot be created will throw this
      """
      for name in self.nodeNames():
         for node in self.nodesFor(name).values():
            debuglog('Constructing links for %s' % node)
            # For each dependency in each node:
            for dependency in node.component.dependencies:
               matched = False
               debuglog(' searching for dependency %s' % dependency)
               # ...try to find a match in all of the components with the right name
               for (version, possibleDep) in self.nodesFor(dependency.name).items():
                  if dependency.isMatch(possibleDep.component):
                     debuglog('  found match: %s' % possibleDep)
                     node.addDependency(possibleDep, dependency.optional)
                     matched = True
               debuglog('  match for %s is %s' % (node, matched))
               debuglog('  dependency.optional: %s' % dependency.optional)
               debuglog('  force:', force)
               if not matched and not dependency.optional and not force:
                  exception = UnsatisfiedDependency('Component %s has unsatisfied '
                                                    'dependency: %s' % (node.component,
                                                    dependency))
                  exception.node = node
                  exception.dependency = dependency
                  raise exception

   def cleanupMarks(self):
      """
      Clear the marked field on all nodes
      """
      for name in self.nodeNames():
         for node in self.nodesFor(name).values():
            node.marked = False

   def checkCycles(self):
      """
      Throw an exception if there are cycles in the graph

      @returns: True, unless an exception is raised

      @raises: CycleError if a cycle exists on the graph
      """
      def recurOnNode(node):
         if node.marked:
            raise CycleError('Component %s version %s has a cyclic dependency'
                          % (node.component.name, node.component.longVersion))
         node.marked = True
         for name in node.dependencyNames():
            for listNode in node.dependenciesFor(name).values():
               recurOnNode(listNode)
         node.marked = False
         return True

      for name in self.nodeNames():
         for node in self.nodesFor(name).values():
            if not node.marked:
               try:
                  recurOnNode(node)
               finally:
                  # Make sure we don't leave any marks on the graph
                  self.cleanupMarks()

      return True

   def checkConflicts(self, installed):
      """
      Try to find conflicts within the graph nodes

      @returns: True, unless an exception is raised

      @raises: ConflictError if conflicts exist on the graph
      """
      for name in self.nodeNames():
         for node in self.nodesFor(name).values():
            for conflict in node.component.conflicts:
               debuglog(' searching for conflict %s' % conflict)
               for (version, possibleConf) in self.nodesFor(conflict.name).items():
                  if conflict.isMatch(possibleConf.component):
                     debuglog('  found match: %s' % possibleConf)
                     node.addConflict(possibleConf)
                     # There are several cases where this can happen and we need to pass the
                     # appropriate arguments to throwConflictError
                     if node.component in installed and possibleConf.component not in installed:
                        throwConflictError(possibleConf.component.longName,
                                           possibleConf.component.longVersion,
                                           conflict,
                                           node.component.longName,
                                           node.component.longVersion,
                                           None)
                     elif node.component not in installed and possibleConf.component in installed:
                        throwConflictError(node.component.longName,
                                           node.component.longVersion,
                                           None,
                                           possibleConf.component.longName,
                                           possibleConf.component.longVersion,
                                           conflict)
                     else:
                        # This will only happen if a user attempts to install two conflicting
                        # components or a bundle was made with conflicting conflicting components
                        # inside it.
                        throwConflictError(node.component.longName,
                                           node.component.longVersion,
                                           None,
                                           possibleConf.component.longName,
                                           possibleConf.component.longVersion,
                                           None)
      return True


   def copy(self):
      """
      Create a copy of this graph, with shallow copies of each node

      @returns: A copy of the graph, with copies of each node. Note that a
                copied node has no links
      """
      newGraph = DependencyGraph()
      for name in self.nodeNames():
         for node in self.nodesFor(name).values():
            newGraph.addNode(DependencyNode(node))
      return newGraph

   def toList(self, state, allNodes = False, sort = False):
      """
      Convert this graph to a list, starting from the product nodes

      @param state: Only nodes of this state are included in the list

      @returns: A list of nodes, with nodes with no parents at the top, and
                their dependencies beneath
      """
      def depthFirstDescent(node, accum):
         """
         Accumulate a list of the node's children in a depth first
         fashion.  Build up a list from the bottom up, ending up
         with a list that begins with node, followed by its dependencies
         in order.

         If the node has already been visited, skip it.
         If the node doesn't match the given state, skip it.

         @param node: The node to descend through
         @param accum: The accumulator containing the results of the descent as
                       the search winds back up.
         """
         if node.marked:
            return;

         for name in node.dependencyNames():
            for dep in node.dependenciesFor(name).values():
               depthFirstDescent(dep, accum)

         node.marked = True
         if state is None or node.state == state:
            accum.insert(0, node.component)
         return
         

      # Get the top level nodes
      self.cleanupMarks()
      debuglog("Building list...")
      topNodes = self.nodesMatching(lambda n: not n.parentNames(), False)
      debuglog("   topNodes: ", topNodes)
      accum = []
      # Continue the breadth-first search until there are no nodes left
      while topNodes:
         debuglog("   Accum: ", accum)
         depthFirstDescent(topNodes.pop(0), accum)
      debuglog("   Accum: ", accum)
      if allNodes:
          # Add the stragglers that aren't connected to any top nodes.
          # This is important for uninstallation.
          all = self.nodesMatching(lambda n: True, False)
          for acc in accum:
             for n in all:
                if n.component == acc:
                   all.remove(n)
                   break
          for n in all:
              if state is None or n.state == state:
                 accum.extend([n.component])
      debuglog("   Final accum: ", accum)
      self.cleanupMarks()
      if sort:
          from vmis.core.component import FileComponent
          accum.sort(key=cmp_to_key(FileComponent.__cmp__))
      return accum

class DependencyNode(object):
   """ A node in a graph of dependencies and conflicts """

   def __init__(self, comp):
      """
      Initialize the DependencyNode

      @param comp: the Component to wrap this node around
      """
      if isinstance(comp, DependencyNode):
         self.component = comp.component
         self.state = comp.state
      else:
         self.component = comp # Component
         self.state = ComponentState.UNKNOWN # Used for checking the state
      self._dependencies = DependencyGraph() # Things we depend on, including optional ones
      self._optDependencies = {} # Dict of Dict of DependencyNode; The subset of dependencies which are optional
      self._conflicts = DependencyGraph() # Things we conflict with or that conflict with us
      self._parents = DependencyGraph() # Things that depend on us
      self.marked = False # Used for checking if a node has been visited. Make sure to clean up after use

   def __str__(self):
      return str(self.component)

   def __repr__(self):
      return repr(self.component)

   def _cmp(self, other):
      """
      Compare two DependencyNode

      @param other: The other DependencyNode to compare against

      @returns: 1 if this is "newer", -1 if this is "older", and 0 otherwise
      """
      def myCmp(a, b):
         return (a > b) - (a < b)

      # Check if they're both e.x.p
      if self.component.version == 'e.x.p' and \
            other.component.version == 'e.x.p':
         # Check if there's no build 0
         if self.component.longVersion.buildNumber != 0 and \
               other.component.longVersion.buildNumber != 0:
            # See if a build number is newer
            cmpRes = myCmp(self.component.longVersion.buildNumber,
                           other.component.longVersion.buildNumber)
            if cmpRes != 0:
               return cmpRes
      # Comparison between e.x.p and non-e.x.p or build 0
      if self.component.version == 'e.x.p' or \
            other.component.version == 'e.x.p':
         return myCmp(self.state, other.state)
      # Get the version comparison
      cmpRes = self.component.version._cmp(other.component.version)
      if cmpRes == 0:
         # They appear to be equal...check build numbers
         if self.component.longVersion.buildNumber == 0 or \
               other.component.longVersion.buildNumber == 0:
            return myCmp(self.state, other.state)
         return myCmp(self.component.longVersion.buildNumber,
                    other.component.longVersion.buildNumber)
      return cmpRes

   def dependency(self, name, version):
      """
      Get the DependencyNode associated with the name and version passed if it
      exists as a dependency

      @param name: The name of the dependency to lookup
      @param version: The longVersion of the dependency to lookup

      @returns: The DepednencyNode associated, or None otherwise
      """
      return self._dependencies.lookupNode(name, version)

   def dependenciesFor(self, name):
      """
      Get a dict of all the dependencies that match the name

      @param name: The name of the dependencies to lookup

      @returns: A dict, keyed on Component.longVersion, of all the
                DependencyNode in the graph that match the name
      """
      return self._dependencies.nodesFor(name)

   def dependenciesSorted(self, name, ascending = True):
      """
      Retrieve a list of DependencyNode for this name, sorted in the order
      specified by the ascending parameter

      @param name: The name of the dependencies to lookup
      @param ascending: If true, the results will be in ascending order. If
                        false, they will be in descending order

      @returns: A list of DependencyNode for this name
      """
      return self._dependencies.nodesSorted(name, ascending)

   def dependencyNames(self):
      """
      Get a list of the names of all the dependencies

      @returns: A list of the names of all the dependencies
      """
      return self._dependencies.nodeNames()

   def parent(self, name, version):
      """
      Get the DependencyNode associated with the name and version passed if it
      exists as a parent

      @param name: The name of the parent to lookup
      @param version: The longVersion of the parent to lookup

      @returns: The DepednencyNode associated, or None otherwise
      """
      return self._parents.lookupNode(name, version)

   def parentsFor(self, name):
      """
      Get a dict of all the parents that match the name

      @param name: The name of the parents to lookup

      @returns: A dict, keyed on Component.longVersion, of all the
                DependencyNode in the graph that match the name
      """
      return self._parents.nodesFor(name)

   def parentNames(self):
      """
      Get a list of the names of all the parents

      @returns: A list of the names of all the parents
      """
      return self._parents.nodeNames()

   def isOptional(self, node):
      """
      Returns true if the node is an optional dependency of this node

      @returns: True if the node is an optional dependency, false otherwise
      """
      if node.component.name not in self._optDependencies:
         return False
      if node.component.longVersion not in self.optDependencies[node.component.name]:
         return False
      return True

   def conflictsFor(self, name):
      """
      Get a dict of all the conflicts that match the name

      @param name: The name of the conflicts to lookup

      @returns: A dict, keyed on Component.longVersion, of all the
                DependencyNode in the graph that match the name
      """
      return self._conflicts.nodesFor(name)

   def conflictNames(self):
      """
      Get a list of the names of all the conflicts

      @returns: A list of the names of all the conflicts
      """
      return self._conflicts.nodeNames()

   def addDependency(self, node, optional = False):
      """
      Adds the passed node to this node's subgraph of dependencies, and
      adds this node to the passed node's subgraph of parents

      @param node: The node to be the dependency
      @param optional: Whether or not this is an optional dependency

      @returns: True if the dependency was added, false otherwise
      """

      if not self._dependencies.addNode(node):
         return False
      assert node._parents.addNode(self), "Dependency bidirectional invariant not maintained"
      if optional:
         if node.component.name in self._optDependencies:
            self._optDependencies[node.component.name][node.component.longVersion] = node
         else:
            self._optDependencies[node.component.name] = { node.component.longVersion: node }
      return True

   def addConflict(self, node):
      """
      Adds the passed node to this node's subgraph of conflicts, and
      adds this node to the passed node's subgraph of conflicts

      @param node: The node to be the conflict

      @returns: True if the dependency was added, false otherwise
      """

      if not self._conflicts.addNode(node):
         return False
      assert node._conflicts.addNode(self), "Conflict bidirectional invariant not maintained"
      return True

   def clearDependency(self, node):
      """
      Remove the passed node from the list of dependencies, and remove this node
      from the passed node's list of parents

      @param node: The node to be removed from the list of dependencies
      """
      self._dependencies.removeNode(node)
      node._parents.removeNode(self)
      if node.component.name in self._optDependencies and node.component.longVersion \
                             in self._optDependencies[node.component.name]:
         del self._optDependencies[node.component.name][node.component.longVersion]
         if not self._optDependencies[node.component.name]:
            del self._optDependencies[node.component.name]

   def clearLinks(self):
      """
      Remove all of this node's links on the graph
      """
      for name in self.dependencyNames():
         for node in self.dependenciesFor(name).values():
            self.clearDependency(node)
      for name in self.parentNames():
         for node in self.parentsFor(name).values():
            node.clearDependency(self)

def Resolve(available, installed, touninstall, dbase):
   """
   Resolve dependencies
   """

   # Changes we have made to bonuses
   bonused = {}
   # Things that are going to be upgraded
   upgradeDict = {}

   def moveToNegative(node, positiveGraph, negativeGraph):
      """
      Move the node to the negative graph and return the list of nodes that
      have become orphaned as a result of this

      @param node: The node to be moved
      @param postiveGraph: The graph that currently contains the node
      @param negativeGraph: The graph to which the node will be moved

      @returns: All the nodes that have become orphaned (no longer have parents
                and are not bonused) by this change
      """
      debuglog('Moving %s to the negative graph' % node)
      if node.marked:
         debuglog(' ...but already marked, skipping')
         return []
      if node.component.name == 'vmware-installer':
         debuglog(' ...but this is vmware-installer, handling later')
         return []
      children = []
      for name in node.dependencyNames():
         for dep in node.dependenciesFor(name).values():
            children.append(dep)
      node.clearLinks()
      node.marked = True
      positiveGraph.removeNode(node)
      negativeGraph.addNode(node)
      return [n for n in children if not n.parentNames() and not n.component.cachedBonus]

   def finalizeGraphs(positiveGraph, negativeGraph):
      """
      Create final, working versions of the graphs

      This method does all the final work on the graphs to ensure that they are
      viable.  This includes final handling of upgrades and constructing links
      on the graph.  If the graph is not viable, one of various exceptions is
      thrown

      @param positiveGraph: The positive graph (modified in the method)
      @param negativeGraph: The negative graph (modified in the method)

      @returns: A new version of the upgrades dict

      @raises DowngradeError: If the version pending install is older than the
                              version installed, but only if it's a product.
      @raises ConflictError: If a conflict is found on the graph
      @raises UnsatisfiedDepenedency: If links cannot be created fully
      """
      debuglog('Trying to finalize the graphs...')

      # Debug info
      theNodes = positiveGraph.nodesMatching(lambda n: True)
      for node in theNodes:
          debuglog('  PosNode: %s CB: %s B: %s' % (node, node.component.cachedBonus, node.component.bonus))
      theNodes = negativeGraph.nodesMatching(lambda n: True)
      for node in theNodes:
          debuglog('  NegNode: %s CB: %s B: %s' % (node, node.component.cachedBonus, node.component.bonus))


      newUpgrades = {}
      # Do upgrades
      # Locate the one node in our install graph that contains a component matching
      # the product we are attempting to install.  This component *must* come first
      # in the nodeList so it generates the proper Dependency Error.  See bug 529894
      nodes = positiveGraph._graph
      names = []
      for key in nodes:
         node=nodes[key]
         # Node is a list of one or more DependencyNodes.  Find the one that contains
         # the component in the available list that is marked as the product.  There
         # will be only one.
         productNode = False
         for comp in node:
            comp=node[comp]
            if productComponent and comp.component.name == productComponent.name:
               productNode = True
               break
         if productNode:
            names.insert(0, key)
         else:
            names.append(key)

      # Handle upgrade cases.  We want to be sure the old component is uninstalled,
      # the new component is installed, and it is marked as an upgrade.  Also,
      # don't allow downgrades.
      for name in names:
         # Don't touch VMware Installer right now
         if name == 'vmware-installer':
            continue
         debuglog(' Trying to upgrade %s' % name)
         debuglog('  All +versions, sorted: %s' % positiveGraph.nodesSorted(name))
         latest = positiveGraph.nodesSorted(name).pop()
         outdated = positiveGraph.upgradeToNode(latest)
         uninstalled = negativeGraph.nodesFor(name)
         debuglog('  Latest: %s (%s)' % (latest.component, type(latest.component)))
         debuglog('  Latest is version %s b.%s' %
                  (latest.component.longVersion, latest.component.longVersion.buildNumber))
         debuglog('   Installed: %s' % (latest.state == ComponentState.INSTALLED))
         debuglog('   Outdated: %s' % outdated)
         debuglog('   Uninstalled: %s' % uninstalled)
         outdated.update(uninstalled)
         for oldVersion in outdated.values():
            # Check if the old version is to be installed
            if latest.state == ComponentState.INSTALLED and \
                  oldVersion.state == ComponentState.TO_INSTALL and \
                  latest.component.longVersion > oldVersion.component.longVersion:
               debuglog('Exception occured in finalizeGraphs: %s.' % latest.component.longName)
               debuglog('Possible Downgrade Error: %s ...  Is product? %s' % (latest.component.longName, latest.component.cachedBonus))
               debuglog('  latest: %s oldVersion: %s' % (latest.component.longVersion, oldVersion.component.longVersion))
               # We have a downgrade.  Only complain if this is a product.
               if latest.component.cachedBonus:
                  raise DowngradeError('You have a newer version of %s installed. '
                                       'Please uninstall it before installing an older version.' %
                                           latest.component.longName)
            debuglog('Checking: %s' % oldVersion.component)
            debuglog('  Uninstalled at this point: %s' % uninstalled)
            debuglog('  Installed: %s' % latest)
            # Update the upgrade dict
            if oldVersion.state == ComponentState.INSTALLED:
               newUpgrades[oldVersion.component] = latest.component
            # Uninstall the old version
            if oldVersion.component.longVersion not in uninstalled:
               debuglog('Uninstalling: %s' % oldVersion.component.name)
               oldVersion.clearLinks()
               negativeGraph.addNode(oldVersion)

      debuglog('Constructing positive graph links')
      # Force link construction the first time without unresolved dependency
      # errors.  We need the links built to cull the tree.
      positiveGraph.constructLinks(installed, force=True)

      # Move unneeded nodes in positive graph to negative graph
      rootNodes = positiveGraph.nodesMatching(lambda n: not n.parentNames() and
                                                        not n.component.cachedBonus)
      while rootNodes:
         debuglog('Moving to negative graph')
         debuglog(rootNodes[0])
         debuglog('Bonus: %s' % rootNodes[0].component.cachedBonus)
         rootNodes.extend(moveToNegative(rootNodes.pop(0), positiveGraph, negativeGraph))
      negativeGraph.cleanupMarks()

      # Now check for conflicts...
      positiveGraph.checkConflicts(installed)

      # Build links a second time, this time checking for unresolved dependencies.
      debuglog('Constructing positive graph links (2nd run)')
      debuglog('  positiveGraph:')
      debuglog(positiveGraph.toList(None))
      positiveGraph.constructLinks(installed, force=False)
      debuglog('Links built...')

      # Clean up installers
      installers = positiveGraph.nodesSorted('vmware-installer')
      if installers:
         debuglog('Installers on system: %s' % installers)
         newestInstaller = installers.pop()
         if positiveGraph.nodeNames() == ['vmware-installer']:
            # Nothing left! Uninstall the installer too
            debuglog('Nothing left on the system but the installer. Removing installer')
            for installer in installers:
               positiveGraph.removeNode(installer)
               negativeGraph.addNode(installer)
            positiveGraph.removeNode(newestInstaller)
            negativeGraph.addNode(newestInstaller)
         elif newestInstaller.state == ComponentState.TO_INSTALL:
            # Upgrade other installers
            for installer in negativeGraph.nodesFor('vmware-installer').values():
               debuglog('Upgrading dead installer %s' %
                         installer.component.longVersion)
               newUpgrades[installer.component] = newestInstaller.component
            for installer in installers:
               debuglog('Upgrading old installer %s' %
                         installer.component.longVersion)
               newUpgrades[installer.component] = newestInstaller.component
               if installer.component.version == newestInstaller.component.version or \
                     not installer.parentNames():
                  positiveGraph.removeNode(installer)
                  # Move the links pointing to the old installer to the new one
                  for name in installer.parentNames():
                     for version in installer.parentsFor(name).values():
                        version.clearDependency(installer)
                        version.addDependency(newestInstaller)
                  negativeGraph.addNode(installer)
               else:
                  debuglog('Installer %s is still relied upon by %s' %
                           (installer.component.longVersion,
                            [list(installer.parentsFor(n).values()) for n in installer.parentNames()]))
         elif len(installers) > 0:
             # The newest installer is already installed.  We need to make sure that the other one
             # doesn't get installed, but only if it's the same version
             olderInstaller = installers.pop()
             if olderInstaller.component.version == newestInstaller.component.version:
                debuglog("Removing extra installers...  They should not be installed.")
                debuglog("   Newer = %s.%s" % (newestInstaller.component, newestInstaller.component.buildNumber))
                debuglog("   Older = %s.%s" % (olderInstaller.component, olderInstaller.component.buildNumber))
                positiveGraph.removeNode(olderInstaller)
                debuglog("   Older installer removed...")

      else:
         debuglog('No installers found...continuing anyway')

      # Final conflict check on our positive graph
      positiveGraph.checkConflicts(installed)
      debuglog('Constructing negative graph links')
      negativeGraph.constructLinks(installed, constructConflicts=False, force=True)
      return newUpgrades

   def depSearch(nodeList, positiveGraph, negativeGraph, recDebug=""):
      """
      Recursively resolve which attempts work and which don't

      @param nodeList: A list of lists of all the nodes to consider for the
                       positive graph. Each of the lists within this list is of
                       like-named components, sorted in ascending order
      @param positiveGraph: The positive graph. Note that this is not modified
                            within the function, but instead copied
      @param negativeGraph: The negative graph. Note that this is not modified
                            within the function, but instead copied

      @warning if this function succeeds, it will modify upgradeDict

      @returns: A tuple of the final positive and negative graphs

      @raises ConflictError: If no graph could be found, and at least one had
                             conflicts
      @raises DowngradeError: If no graph could be found, and at least one had
                              a downgrade error
      @raises UnsatisfiedDependency: If no graph could be found because there is
                                     no combination of nodes that has all
                                     dependencies satisfied
      """
      def validateGraph(newNodeList, pGraph, nGraph, recDebug=''):
         # Recursion debugging code.  Keeping track of each node we visit, this can be
         # used to generate a graph in .dot format, which allows us to visually inspect
         # the graph for inefficiencies and to get an idea of the search space that was
         # needed to solve the dependency.
         global recCounter
         global recDict
         curStr = ''
         for p in pGraph.toList(None, sort=True):
             curStr = curStr+str(p.__repr__())
         for p in nGraph.toList(None, sort=True):
             curStr = curStr+str(p.__repr__())
         if not recDict.get(curStr):
             recDict[curStr] = recCounter
             recCounter = recCounter + 1
         n1 = recDict.get(curStr)
         n2 = recDict.get(recDebug)
         printDepGraph('   "%d" -- "%d";' % (n2, n1))
         recDebug = curStr

         try:
            debuglog('Calling depSearch from a non-bonused component.')
            retVal = depSearch(newNodeList, pGraph, nGraph, recDebug)
            if not retVal:
                debuglog('Got NONE returned in validateGraph.  Exception is: %s' % exception[0])
                # If we don't have a graph coming back, then it excepted out...
                # re-raise the exception
                debuglog('No valid graph was found down this tree.  Raising exception')
                raise exception[0]

            # Otherwise, we were returned a graph!
            newPosGraph = retVal[0]
            newNGraph = retVal[1]
            debuglog('Positive Graph: ')
            newPosGraph.logList()
            debuglog('Negative Graph: ')
            newNGraph.logList()

            # One more check for conflicts in our positive graph
            # It's possible to get two installers in this graph though.  One has to go
            # and it always has to be the older one.
            debuglog('Constructing Links...')
            # Check the nodes and build links on the Positive Graph
            newPosGraph.constructLinks(installed, force=False)

            # One last check for the negative graph.  We can't allow any
            # Productized components from the available list to be on here,
            # after all, we're trying to install them :)
            names = newNGraph.nodeNames()
            for name in names:
                nodes = newNGraph.nodesSorted(name, ascending=False)
                for node in nodes:
                    debuglog('Scanning Neg Graph: %s %s' % (node, type(node)))
                    if node.component in available and node.component.cachedBonus:
                        raise InvalidInstallError('Cannot place %s in the uninstall list.' % node.component)

            return [newPosGraph, newNGraph]
         except (ConflictError, DowngradeError, UnsatisfiedDependency, InvalidInstallError) as e:
            debuglog('Exception occured: %s' % e)
            if not isinstance(exception[0], ConflictError):
               debuglog(' Stored exception is not ConflictError')
               if isinstance(e, ConflictError):
                  debuglog(' ...but this one is')
                  exception[0] = e
               elif not isinstance(exception[0], DowngradeError):
                  debuglog(' Stored exception is not DowngradeError')
                  if isinstance(e, DowngradeError):
                     debuglog(' ...but this one is')
                     exception[0] = e
                  elif not exception[0]:
                     debuglog(' No exception actually stored')
                     exception[0] = e
            debuglog('Returning NONE in validateGraph...  exception is: %s' % exception[0])
            return None


      debuglog('-------------------------------------------')
      debuglog('Nodelist: ')
      debuglog(nodeList)
      debuglog('positiveGraph: ')
      positiveGraph.logList()
      debuglog('negativeGraph: ')
      negativeGraph.logList()

      if nodeList:
         versions = nodeList.pop()
         debuglog('Looking at Versions: %s' % versions)
         latestInstalled = None
         exception = [None]  # This *must* be a mutable variable (so a list) to be modified by
                             # validateGraph. Hooray for Python...  Why can't you just let me
                             # pass anything by reference... C-style?

         if versions[0].component.name == 'vmware-installer':
            # The installer has to be handled differently.  It's possible to have more than one installer
            # installed at any given time and we may be upgrading/installing/uninstalling one of them.
            #
            # Rather than try to fold this in with the generic component depSearch, special case this
            # and handle the installer here.

            lastNode=None;
            nodesOfInterest=[]

            versionCopy = versions[:] # Duplicate the items in the list (NOT a deep copy)
            for node in versionCopy:
                # Identify the one installer that is changing, if any.  It will have two entries of the same
                #  version in this list.
                if lastNode and (lastNode.component.version == node.component.version):
                    # We found it... Remove the nodes from versionCopy and store them away separately
                    nodesOfInterest.append(lastNode)
                    nodesOfInterest.append(node)
                    versionCopy.remove(lastNode)
                    versionCopy.remove(node)
                    break
                else:
                    lastNode = node

            # Add all remaining versions of the installer to the positive graph
            pGraph = positiveGraph.copy()
            nGraph = negativeGraph.copy()
            newNodeList = nodeList[:] # Duplicate the items in the list (NOT a deep copy)
            for node in versionCopy:
                pGraph.addNode(DependencyNode(node))

            # Now if there are two possibilities for any of the installer versions, test out both,
            # adding one to the pgraph and one to the ngraph and recursing...
            if nodesOfInterest:
               debuglog('Found two installer nodes of interest:')
               debuglog(nodesOfInterest)
               pg = pGraph.copy()
               ng = nGraph.copy()
               pg.addNode(DependencyNode(nodesOfInterest[0]))
               ng.addNode(DependencyNode(nodesOfInterest[1]))
               graph = validateGraph(newNodeList, pg, ng, recDebug)
               # Only return if we've found a valid graph.  Otherwise, try our other alternative.
               if graph:
                  return graph
               pg = pGraph.copy()
               ng = nGraph.copy()
               pg.addNode(DependencyNode(nodesOfInterest[1]))
               ng.addNode(DependencyNode(nodesOfInterest[0]))
               graph = validateGraph(newNodeList, pg, ng, recDebug)
               # Only return if we've found a valid graph.  Otherwise, try our other alternative.
               if graph:
                  return graph
            else:
               # No strange installer versioning to worry about, recurse to check the rest of
               # our dependencies.
               debuglog('No interesting installer nodes... continuing...')
               graph = validateGraph(newNodeList, pGraph, nGraph, recDebug)
               if graph:
                  return graph
            # If we get here, none of the attempted graphs worked.  Re-raise the stored exception
            debuglog('Recursion failed when searching for dependencies on the installer...  Reraising exception')
            raise exception[0]
         else:
            # Recursively search the rest of our nodes, forking to trying all alternatives at each decision point.
            versionCopy = versions[:] # Duplicate the items in the list (NOT a deep copy)

            # A little pre-filtering to cut down dramatically on the recursion in most cases.
            # If the node has two components of the same version (one installed, one not), only
            # consider the newest one by longversion
            # ***unless*** the version is e.x.p or the build number is 0...  They're special.
            if len(versionCopy) == 2:
                if versionCopy[0].component.version == versionCopy[1].component.version:
                    if versionCopy[0].component.version != 'e.x.p' and \
                       versionCopy[1].component.version != 'e.x.p' and \
                       versionCopy[0].component.buildNumber != '0' and \
                       versionCopy[1].component.buildNumber != '0':
                       # Only use the newest one.
                       if versionCopy[0].component.longVersion > versionCopy[1].component.longVersion:
                          versionCopy.remove(versionCopy[1])
                       elif versionCopy[0].component.longVersion < versionCopy[1].component.longVersion:
                          versionCopy.remove(versionCopy[0])
                       else:
                          versionCopy.remove(versionCopy[0])

            for node in versionCopy:
               debuglog('Node=%s' % node.component)
               # Find a version that works
               debuglog(' Searching within %s b. %s' % (node, node.component.buildNumber))
               # Check for downgrades
               if not latestInstalled:
                  latestInstalled = node
               elif latestInstalled.state == ComponentState.INSTALLED:
                  debuglog('Found possible downgrade')
                  if isinstance(exception[0], ConflictError):
                     debuglog('Stored exception is a ConflictError')
                     continue
                  else:
                     if node.component.cachedBonus:
                        debuglog('DowngradeError in depSearch for %s' % node.component.longName)
                        exception[0] = DowngradeError('You have a newer version of %s installed. '
                                                      'Please uninstall it before installing '
                                                      'an older version.' % node.component.longName)
                        continue
               else:
                  latestInstalled = node

               pGraph = positiveGraph.copy()
               nGraph = negativeGraph.copy()
               pGraph.addNode(DependencyNode(node))
               debuglog('Adding Node: %s' % node.component)
               newNodeList = nodeList[:] # Duplicate the items in the list (NOT a deep copy)
               nonVersions = versions[:] # Duplicate the items in the list (NOT a deep copy)
               nonVersions.remove(node)

               # Put all the other versions in the negative graph
               for nv in nonVersions:
                  nGraph.addNode(DependencyNode(nv))
               graph = validateGraph(newNodeList, pGraph, nGraph, recDebug)
               # Only return if we've found a valid graph.  Otherwise, go on with our
               # search.
               if graph:
                  return graph

            # If we get here, we were unable to find a valid tree... Raise the stored exception
            debuglog('Recursion failed when searching for dependencies...  Reraising exception')
            raise exception[0]
      else:
         debuglog('Nodelist is empty.  Attempting to finalize graphs:')
         upgrades = finalizeGraphs(positiveGraph, negativeGraph)
         debuglog('Graph has been finalized')
         # If we have gotten here, there will be no more exceptions, so we are safe
         upgradeDict.update(upgrades)
         return (positiveGraph, negativeGraph)



   # ------------- ENTRY POINT --------------
   # A summary of how this code should work.  Up to date by trenner
   # as of 2010-11-05:
   #
   # Three lists of components come in:
   #
   #  available: What components are available for installation
   #    * Components with a bonus set are the ones we really care about.  The
   #      rest are just support.  All bonused components *must* be installed
   #      or a Downgrade/Conflict error thrown if it's impossible to do so.
   #
   #  installed: What components are already installed
   #
   #  touninstall: Which components should be uninstalled
   #    * If a component is NOT bonused, it is initially added to the uninstall list
   #      (the negative graph)
   #    * If a component IS bonused, it's **only** added to the debonused graph,
   #      removing it as a product, but necessarily resulting in an uninstallation
   #      if another product depends on it. (Think Workstation and VIX)
   #
   #  * Components come in two flavors, regular and product.  If a component has a bonus
   #    it's a product.  It's called a bonus because it gets an automatic bonus to its
   #    ref-count.  This is what keeps it around.
   #
   #  * Versions of e.x.p and build #s of 0 are special.  They *always* should upgrade.
   #    We do this because they are developer builds and considered special.  Also, e.x.p
   #    isn't a real version, so we can't do any actual comparison with it.
   #
   #  * No component should have two versions installed *EXCEPT* the vmware-installer.
   #    It must remain on the system if another component requires it as its Python will
   #    be needed.
   #
   #  * At final resolution, all components in the dependency tree not attached to a Product
   #    component will end up with a ref count of 0 and will be added to the uninstall list.
   #
   #  * Attempting to install a non-product component that is not required by any product
   #    either directly or indirectly will result in a null operation.
   #    Example:  WS depends on Player.  Both are installed.  I try to install non-product
   #      component foo.  Nothing depends on it, so it will never be installed.
   #    XXX: This may need to change.
   #

   global recCounter
   global recDict
   recCounter=1
   recDict={}
   recDict[""] = 0

   debuglog('Available: %s' % available)
   debuglog('Installed: %s' % installed)
   debuglog('Uninstall: %s' % touninstall)

   # Make sure cachedBonus is set to the current bonus.  We'll be modifying the cachedBonus as we go,
   # and in some cases, we'll need a reference back to what the bonus was before we started messing
   # with it.
   for node in installed:
      node.cachedBonus = node.bonus

   # If there is one, pick out the product we are attempting to install.
   productComponent = None
   for comp in available:
      if comp.cachedBonus:
         productComponent = comp

   # This is a graph of the things that should be on the system after the
   # installation is complete
   positiveGraph = DependencyGraph()
   # This is a graph of the things that should be uninstalled from the system
   # after the installation is complete
   negativeGraph = DependencyGraph()
   # This graph is necessary because alike components might not be the same ID
   debonusedGraph = DependencyGraph()

   # Process the uninstall list first
   debuglog('Processing uninstall list...')
   for component in touninstall:
      debuglog(' processing %s b.%s' % (component, component.longVersion.buildNumber))
      node = DependencyNode(component)
      if node.component.cachedBonus:
         debonusedGraph.addNode(node)
      else:
         negativeGraph.addNode(node)

   debuglog('Uninstall list processed:')
   debuglog('  debonusedGraph: ')
   debuglog(debonusedGraph.toList(None))
   debuglog('  negativeGraph: ')
   debuglog(negativeGraph.toList(None))

   # Now process the installed list
   debuglog('Processing installed list...')
   for component in installed:
      debuglog(' processing %s b.%s' % (component, component.longVersion.buildNumber))
      negativeNode = negativeGraph.lookupNode(component.name, component.longVersion)
      if negativeNode:
         negativeNode.state = ComponentState.INSTALLED
      else:
         node = DependencyNode(component)
         debonusedNode = debonusedGraph.lookupNode(component.name, component.longVersion)
         if debonusedNode:
            node.component.cachedBonus = False
            bonused[node.component] = False
         node.state = ComponentState.INSTALLED
         positiveGraph.addNode(node)

   debuglog('Install list processed:')
   debuglog('  positiveGraph: ')
   debuglog(positiveGraph.toList(None))

   # Finally, process the available list
   debuglog('Processing available list...')
   for component in available:
      debuglog(' processing %s b.%s' % (component, component.longVersion.buildNumber))
      negativeNode = negativeGraph.lookupNode(component.name, component.longVersion)
      if not negativeNode:
         positiveNode = positiveGraph.lookupNode(component.name, component.longVersion)
         # Special case e.x.p and build 0--we have to move those to the negative graph here
         node = DependencyNode(component)
         if positiveNode and (component.version == 'e.x.p' or
                              component.longVersion.buildNumber == 0):
            debuglog('  Found special case update--moving existing node to negative graph')
            if positiveNode.component.cachedBonus:
               debuglog('Transferring bonus')
               node.component.cachedBonus = True
               bonused[node.component] = True
               positiveNode.component.cachedBonus = False
               bonused[positiveNode.component] = False
            positiveGraph.removeNode(positiveNode)
            negativeGraph.addNode(positiveNode)
            positiveNode = None
         if not positiveNode:
            node.state = ComponentState.TO_INSTALL
            positiveGraph.addNode(node)

   debuglog('Processed Available list:')
   debuglog('  debonusedGraph: ')
   debuglog(debonusedGraph.toList(None))
   debuglog('  negativeGraph: ')
   debuglog(negativeGraph.toList(None))
   debuglog('  positiveGraph: ')
   debuglog(positiveGraph.toList(None))

   # Transfer bonuses
   bonusedNodes = positiveGraph.nodesMatching(lambda n: n.component.cachedBonus)
   for oldVersion in bonusedNodes:
      versions = positiveGraph.nodesSorted(oldVersion.component.name)
      latest = versions.pop()
      debuglog('Got bonused %r b.%s' % (oldVersion, oldVersion.component.buildNumber))
      debuglog('Latest %r b.%s' % (latest, latest.component.buildNumber))
      debuglog('Other versions: %r' % versions)
      if latest.component is not oldVersion.component and latest.component not in installed:
         debuglog('Transferring bonus')
         latest.component.cachedBonus = True
         bonused[latest.component] = True
         oldVersion.component.cachedBonus = False
         bonused[oldVersion.component] = False
         debuglog('Removed bonus from %s.%s...' % (oldVersion.component, oldVersion.component.buildNumber))

   debuglog('Transferred Bonuses:')
   debuglog('  debonusedGraph: ')
   debuglog(debonusedGraph.toList(None))
   debuglog('  negativeGraph: ')
   debuglog(negativeGraph.toList(None))
   debuglog('  positiveGraph: ')
   debuglog(positiveGraph.toList(None))
   debuglog('  bonused: ')
   debuglog(bonused)

   # Construct links in positive graph
   debuglog('Constructing links in positive graph...')
   try:
      positiveGraph.constructLinks(installed)
   except UnsatisfiedDependency as e:
      # Detect if the exception is from an uninstall
      for node in negativeGraph.nodesFor(e.dependency.name).values():
         if e.dependency.isMatch(node.component):
            raise UnsatisfiedDependency('%s is needed by %s, cannot uninstall.'
               % (e.dependency.name, e.node.component.name))
      raise

   # We don't need to check the return value--it'll raise an exception if it fails
   positiveGraph.checkCycles()

   # Now we must sort out which components can be installed together, with upgrades
   debuglog('Deducing a workable final graph...')
   nodeList = []
   for name in positiveGraph.nodeNames():
      nodeList.append(positiveGraph.nodesSorted(name, False))
   debuglog('Using list %s' % nodeList)
   if os.environ.get('VMWARE_VMIS_PRINT_DEP_GRAPH'): # Dep graph debugging
      print("graph dependencySearch {")
   (positiveGraph, negativeGraph) = depSearch(nodeList, DependencyGraph(), negativeGraph)
   if os.environ.get('VMWARE_VMIS_PRINT_DEP_GRAPH'): # Dep graph debugging
      print("}")
   debuglog('Found a graph!')
   debuglog('positiveGraph: ')
   positiveGraph.logList()
   debuglog(positiveGraph.toList(None))
   debuglog('negativeGraph: ')
   negativeGraph.logList()
   debuglog(negativeGraph.toList(None))

   debuglog('Making positive list...')
   installList = positiveGraph.toList(ComponentState.TO_INSTALL)
   # The list needs to be reversed because the bottom elements should be
   # installed first, and this is listed with the top elements first
   installList.reverse()

   debuglog('\nMaking negative list...')
   uninstallList = negativeGraph.toList(ComponentState.INSTALLED, allNodes=True)

   debuglog('************** DEPENDENCY RESULTS **************')
   debuglog('installList:')
   debuglog(installList)
   debuglog('uninstallList:')
   debuglog(uninstallList)
   debuglog('upgradeDict:')
   debuglog(upgradeDict)
   debuglog('bonused:')
   debuglog(bonused)
   debuglog('************** DEPENDENCY RESULTS **************')

   return {
      'install': installList,
      'uninstall': uninstallList,
      'upgrade': upgradeDict,
      'bonused': bonused
   }
