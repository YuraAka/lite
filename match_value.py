__author__ = 'Yura'


class NodeType(object):
    OWNER = 0,  # every node in json, tagged-node in xml
    ATTRIBUTE = 1, # xml attribute
    TEXT = 2,  # xml text
    BUILTIN = 3  # int/string/double


class Node(object):
    @property
    def level(self):
        return 0 if self.parent is None else self.parent.level + 1

    def __init__(self):
        self.parent = None
        self.name = None
        self.values = [] # list of Value / literals
        self.type = NodeType.REGULAR


class ExpectedNode(Node):
    def __init__(self):
        self.anchor = False  # parent value will be anchored by this value
        self.absent = False  # if this value is in actual output -- it is an error
        self.order = False # preserve order of values
        self.fixed = False # required all values matching

    def diff(self, actual_node):
        if not isinstance(actual_node, Node):
            return NodeDiff(reason=DiffReason(DiffType.MISS_TYPES, actual_node, self))

        if actual_node.name != self.name:
            if self.absent is True:
                return None
            return NodeDiff(reason=DiffReason(DiffType.NAMES, actual_node, self))

        if actual_node.type != self.type:
            return NodeDiff(reason=DiffReason(DiffType.MISS_TYPES, actual_node, self))

        if self.order is True:
            return self._diff_ordered_values(actual_node.values)
        return self._diff_unordered_values(actual_node.values)

    def _diff_ordered_values(self, actual_values):
        # todo
        pass

    """
    expected [1, 1, 2]
    actual [1, 2]
    error: missing value of 1
    rate: 1/3
    """
    def _diff_unordered_values(self, actual_values):
        # todo support fixed
        used_actuals = set()
        value_list_diff = NodeDiff(reason=DiffReason(DiffType.VALUES_DIFF, actual_values, self.values))
        for expected_value in self.values:
            value_diff = NodeDiff(reason=DiffReason(DiffType.VALUE_NOT_FOUND, actual_values, expected_value))
            for idx, actual_value in enumerate(actual_values):
                if idx in used_actuals:
                    continue
                # todo extend to builtin
                candidate_diff = expected_value.diff(actual_value)
                if candidate_diff is None:
                    used_actuals.add(idx)
                    value_diff = None
                    value_list_diff.hits += 1
                    break
                value_diff.children.append(candidate_diff)
            else:
                value_list_diff.misses += 1
                value_list_diff.children.append(value_diff)

        return None if value_list_diff.misses == 0 else value_list_diff

    def _diff_side_by_side(self, expected, actual):
        if isinstance(expected, ExpectedNode):
            return expected.diff(actual)
        if type(expected) != type(actual):
            return NodeDiff(reason=DiffReason(DiffType.MISS_TYPES, actual, expected))
        if isinstance(expected, list):
            return self._diff_builtin_lists(expected, actual)
        elif type(expected) in [int, str, unicode]:
            # TODO
            pass
        else:
            return NodeDiff(reason=DiffReason(DiffType.UNK_TYPE, actual, expected))

    def _diff_builtin_lists(self, expected, actual):
        # TODO
        pass


class DiffType(object):
    MISS_TYPES = 0
    NAMES = 1
    VALUES_MORE = 2
    VALUES_LESS = 3
    VALUES_DIFF = 4
    VALUE_NOT_EQUAL = 5
    VALUE_NOT_FOUND = 6
    UNK_TYPE = 7


# todo make classes for each type
class DiffReason(object):
    def __init__(self, dtype, actual, expected):
        self.actual = None
        self.expected = None
        self.type = None


class NodeDiff(object):
    def __init__(self, reason, rate=100):
        self.hits = 0
        self.misses = 0
        self.reasons = [reason]
        self.children = []

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

