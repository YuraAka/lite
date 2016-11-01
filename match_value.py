__author__ = 'Yura'


class NodeType(object):
    OWNER = 0,
    ATTRIBUTE = 1,
    TEXT = 2,


class Node(object):

    def __init__(self):
        self.name = None
        self.values = [] # list of Value / literals
        self.type = NodeType.REGULAR


class ExpectedNode(Node):
    def __init__(self):
        self.anchor = False  # parent value will be anchored by this value
        self.absent = False  # if this value is in actual output -- it is an error
        self.order = False # preserve order of values


class DiffType(object):
    TYPES = 0,
    NAMES = 1,
    VALUES_MORE = 2,
    VALUES_LESS = 3,
    VALUE_NOT_EQUAL = 4


class DiffReason(object):
    def __init__(self, dtype, actual, expected):
        self.actual = None
        self.expected = None
        self.type = None


class NodeDiff(object):
    def __init__(self):
        self.rate = 100 # [0, 100] int
        self.reasons = []

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


def make_diff(actual_node, expected_node):
    if not isinstance(actual_node, Node):
        raise RuntimeError('actual must be Value')

    if not isinstance(expected_node, ExpectedNode):
        raise RuntimeError('expected must be ExpectedValue')

    if actual_node.name != expected_node.name:
        diff = NodeDiff()
        diff.reasons += [DiffReason(DiffType.NAMES, actual_node.name, expected_node.name)]
        return diff

    if actual_node.type != expected_node.type:
        diff = NodeDiff()
        diff.reasons += [DiffReason(DiffType.TYPES, actual_node.type, expected_node.type)]
        return diff

    min_diff = None
    # todo ordered case
    for expected_value in expected_node.values:
        for actual_value in actual_node.values:
            diff = make_diff(actual_value, expected_value)
            if diff is None:
                # current expected value has passed check
                continue
            # todo interesting
            if min_diff is not None and min_diff.rate > diff.rate or min_diff is None:
                min_diff = diff


