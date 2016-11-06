#!/usr/bin/env python
import collections

__author__ = 'Yura'


class Diff(object):
    TYPES_NOT_EQUAL = 'TYPES NOT EQUAL'
    NAME_NOT_EQUAL = 'NAME NOT EQUAL'
    VALUES_MORE = 'VALUES MORE'
    VALUES_LESS = 'VALUES LESS'
    CHILDREN_DIFF = 'CHILDREN DIFF'
    VALUE_NOT_EQUAL = 'VALUE NOT EQUAL'
    CHILD_NOT_FOUND = 'CHILD NOT FOUND'
    UNK_TYPE = 'UNK TYPE'
    VALUE_UNEXP_EQUAL = 'VALUE UNEXP EQUAL'
    CHILDREN_ORDER = 'CHILDREN ORDER'

    def __init__(self, kind, actual, expected):
        self.hits = 0
        self.misses = 0
        self.children = []
        self.actual = actual
        self.expected = expected
        self.kind = kind

    def __repr__(self):
        return self.render(0)

    def render(self, level):
        out = \
        '{tab}kind = {kind}\n' \
        '{tab}hits = {hits}\n' \
        '{tab}misses = {misses}\n' \
        '{tab}expected = {expected}\n' \
        '{tab}actual = {actual}\n\n'.format(
            kind=self.kind,
            hits=self.hits,
            misses=self.misses,
            expected = self.expected,
            actual = self.actual,
            tab=' '*level
        )

        for child in self.children:
            out += child.render(level+1)

        return out


class Node(object):
    REGULAR = 0,  # every node in json, tagged-node in xml
    ATTRIBUTE = 1,  # xml attribute
    LIST_ELEMENT = 2

    def __init__(self, name, children=None, kind=None, value=None):
        self.parent = None
        self.name = name
        self.value = value   # built-in value or matcher
        self.children = children or []  # list of Nodes
        self.kind = kind or Node.REGULAR
        for child in self.children:
            child.parent = self

    def __repr__(self):
        return 'name={}; value={}; kind={}'.format(self.name, self.value, self.kind)


class Expected(object):
    def __init__(self, node, anchor=False, ansent=False, order=False, fixed=False):
        self.node = node
        self.anchor = False  # if this value is not found, do not process siblings
        self.absent = False  # if this value is in actual output -- it is an error
        self.order = False   # preserve order of children
        self.fixed = False   # required children match, otherwise -- part is sufficient

    def diff(self, actual):
        expected = self.node
        if not isinstance(actual, Node):
            return Diff(Diff.TYPES_NOT_EQUAL, actual, expected)

        if actual.kind != expected.kind:
            return Diff(Diff.TYPES_NOT_EQUAL, actual, expected)

        if expected.kind is not Node.LIST_ELEMENT and actual.name != expected.name:
            if self.absent is True:
                return None
            return Diff(Diff.NAME_NOT_EQUAL, actual, expected)

        if expected.value is not None and actual.value != expected.value:
            return Diff(Diff.VALUE_NOT_EQUAL, actual, expected)

        return self._diff_children(actual)

    def __repr__(self):
        return str(self.node)

    """
    expected [1, 1, 2]
    actual [1, 2]
    error: missing value of 1
    rate: 1/3
    """
    def _diff_children(self, actual_parent):
        # todo support fixed
        # todo support anchor
        expected_parent = self.node
        matched_actuals = set()
        matched_expected = set()
        last_matched_idx = -1
        last_matched = None

        # expected_idx => (actual_idx => diff)
        hypothesis = collections.defaultdict(dict)
        children_diff = Diff(Diff.CHILDREN_DIFF, actual_parent, expected_parent)
        for expected_idx, expected in enumerate(expected_parent.children):
            for actual_idx, actual in enumerate(actual_parent.children):
                if actual_idx in matched_actuals:
                    continue
                candidate_diff = expected.diff(actual)
                if candidate_diff is None:
                    if self.order is True and last_matched_idx > actual_idx:
                        hypothesis[expected_idx][actual_idx] = Diff(
                            Diff.CHILDREN_ORDER, last_matched, expected
                        )
                        continue
                    matched_actuals.add(actual_idx)
                    matched_expected.add(expected_idx)
                    last_matched_idx = actual_idx
                    last_matched = actual
                    children_diff.hits += 1
                    break
                hypothesis[expected_idx][actual_idx] = candidate_diff
            else:
                children_diff.misses += 1

        if children_diff.misses == 0:
            return None

        for expected_idx, expected in enumerate(expected_parent.children):
            if expected_idx in matched_expected:
                continue
            child_diff = Diff(Diff.CHILD_NOT_FOUND, actual_parent, expected)
            for actual_idx, actual in enumerate(actual_parent.children):
                if actual_idx in matched_actuals:
                    continue
                child_diff.children.append(hypothesis[expected_idx][actual_idx])
            children_diff.children.append(child_diff)
        return children_diff

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
  children = [
    Node
      name = 'node1'
      children = [
        Node
          value = 1
        Node
          value = 2
        Node
          value = 3
    Node
      name = 'node2'
      children = [
        Node
          name = 'sub1'
          values = [5]
      ]
  ]

"""


def test_good():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.LIST_ELEMENT),
        Node(name='1', value=2, kind=Node.LIST_ELEMENT),
        Node(name='2', value=3, kind=Node.LIST_ELEMENT)
    ])

    expected = Expected(node=Node(name='list', children=[
        Expected(Node(name='0', value=2, kind=Node.LIST_ELEMENT)),
        Expected(Node(name='1', value=3, kind=Node.LIST_ELEMENT))
    ]))

    assert expected.diff(actual) is None

def test_bad():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.LIST_ELEMENT),
        Node(name='1', value=2, kind=Node.LIST_ELEMENT),
        Node(name='2', value=3, kind=Node.LIST_ELEMENT)
    ])

    expected = Expected(node=Node(name='list', children=[
        Expected(Node(name='0', value=2, kind=Node.LIST_ELEMENT)),
        Expected(Node(name='1', value=4, kind=Node.LIST_ELEMENT))
    ]))

    expout = '''kind = CHILDREN DIFF
hits = 1
misses = 1
expected = name=list; value=None; kind=(0,)
actual = name=list; value=None; kind=(0,)

 kind = CHILD NOT FOUND
 hits = 0
 misses = 0
 expected = name=1; value=4; kind=2
 actual = name=list; value=None; kind=(0,)

  kind = VALUE NOT EQUAL
  hits = 0
  misses = 0
  expected = name=1; value=4; kind=2
  actual = name=0; value=1; kind=2

  kind = VALUE NOT EQUAL
  hits = 0
  misses = 0
  expected = name=1; value=4; kind=2
  actual = name=2; value=3; kind=2
'''
    assert expout in str(expected.diff(actual))

if __name__ == '__main__':
    test_good()
    test_bad()
