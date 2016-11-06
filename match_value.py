import collections

__author__ = 'Yura'


class NodeType(object):
    REGULAR = 0,  # every node in json, tagged-node in xml
    ATTRIBUTE = 1, # xml attribute


class DiffKind(object):
    TYPES_NOT_EQUAL = 0
    NAME_NOT_EQUAL = 1
    VALUES_MORE = 2
    VALUES_LESS = 3
    CHILDREN_DIFF = 4
    VALUE_NOT_EQUAL = 5
    CHILD_NOT_FOUND = 6
    UNK_TYPE = 7
    VALUE_UNEXP_EQUAL = 8
    VALUE_FIX_FAILURE = 9


# todo make classes for each type
class DiffReason(object):
    def __init__(self, dtype, actual, expected):
        self.actual = None
        self.expected = None
        self.type = None


class NodeDiff(object):
    def __init__(self, kind, actual, expected):
        self.hits = 0
        self.misses = 0
        self.children = []
        self.actual = actual
        self.expected = expected
        self.kind = kind


class Node(object):
    def __init__(self):
        self.parent = None
        self.name = None
        self.value = None   # built-in value or matcher
        self.children = []  # list of Values or ExpectedValues
        self.type = NodeType.REGULAR


class ExpectedNode(Node):
    def __init__(self):
        self.anchor = False  # if this value is not found, do not process siblings
        self.absent = False  # if this value is in actual output -- it is an error
        self.order = False # preserve order of children
        self.fixed = False # required children match, otherwise -- part is sufficient

    def diff(self, actual):
        if not isinstance(actual, Node):
            return NodeDiff(DiffKind.TYPES_NOT_EQUAL, actual, self)

        if actual.name != self.name:
            if self.absent is True:
                return None
            return NodeDiff(DiffKind.NAME_NOT_EQUAL, actual, self)

        if actual.type != self.type:
            return NodeDiff(DiffKind.TYPES_NOT_EQUAL, actual, self)

        if actual.value != self.value:
            return NodeDiff(DiffKind.VALUE_NOT_EQUAL, actual, self)

        if self.order is True:
            return self._diff_children_with_order(actual)
        return self._diff_children_no_order(actual)

    def _diff_children_with_order(self, actual_values):
        # todo
        pass

    """
    expected [1, 1, 2]
    actual [1, 2]
    error: missing value of 1
    rate: 1/3
    """
    def _diff_children_no_order(self, actual_parent):
        # todo support fixed
        # todo support anchor
        matched_actuals = set()
        matched_expected = set()

        # expected_idx => (actual_idx => diff)
        hypothesis = collections.defaultdict(dict)
        children_diff = NodeDiff(DiffKind.CHILDREN_DIFF, actual_parent, self)

        # matrix expected vs actual
        # ordered and unordered ways of traverse

        # collect all matched values
        for expected_idx, expected in enumerate(self.children):
            for actual_idx, actual in enumerate(actual_parent.children):
                if actual_idx in matched_actuals:
                    continue
                candidate_diff = self._diff_side_by_side(actual, expected)
                if candidate_diff is None:
                    matched_actuals.add(actual_idx)
                    matched_expected.add(expected_idx)
                    children_diff.hits += 1
                    break
                hypothesis[expected_idx][actual_idx] = candidate_diff
            else:
                children_diff.misses += 1

        if children_diff.misses == 0:
            return None

        # collect hypothesis
        for expected_idx, expected in enumerate(self.children):
            if expected_idx in matched_expected:
                continue
            child_diff = NodeDiff(DiffKind.CHILD_NOT_FOUND, actual_parent, expected)
            for actual_idx, actual in enumerate(actual_parent.children):
                if actual_idx in matched_actuals:
                    continue
                child_diff.children.append(hypothesis[expected_idx][actual_idx])
            children_diff.children.append(child_diff)
        return children_diff

    def _diff_side_by_side(self, actual, expected):
        if isinstance(expected, ExpectedNode):
            return expected.diff(actual)
        if type(expected) != type(actual):
            return NodeDiff(reason=DiffReason(DiffKind.TYPES_NOT_EQUAL, actual, expected))
        if isinstance(expected, list):
            return self._diff_builtin_lists(expected, actual)
        if type(expected) in [int, str, unicode]:
            return self._diff_builtin_atoms(expected, actual)
        return NodeDiff(reason=DiffReason(DiffKind.UNK_TYPE, actual, expected))

    def _diff_builtin_atoms(self, expected, actual):
        # TODO support matcher
        if expected != actual:
            return NodeDiff(reason=DiffReason(DiffKind.VALUE_NOT_EQUAL, actual, expected))
        return None


"""
xml repr
<node attr1="1" attr2="2">
  <subnode1>yura</subnode1>
  <subnode2/>
</node>

Node
  name = 'node'
  type = OWNER
  values = [
    Node
      name = 'attr1'
      values = ['1']
      type = ATTR
    Node
      name = 'attr2'
      values = ['2']
      type = ATTR
    Node
      name = 'subnode1'
      type = OWNER
      values = [
        Node
          name = None
          values = ['yura']
          type = TEXT
      ]
    Node
      name = 'subnode2'
      type = OWNER
      values = []
  ]

/// json repr
{
  'node1' : [1, 2, 3]
  'node2' : {
    'sub1' : 5
    'sub2' : 6
  }
  'node3' : 7
}

Node
  name = None
  type = OWNER
  values = [
    Node
      name = 'node1'
      values = [1, 2, 3]
      type = OWNER
    Node
      name = 'node2'
      type = OWNER
      values = [
        Node
          name = 'sub1'
          values = [5]
      ]
  ]

"""

