#!/usr/bin/env python
# coding=utf-8
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

    def __init__(self, kind, actual, expected, hits=0, misses=1):
        self.hits = hits
        self.misses = misses
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
    REGULAR = 'REG'  # general node
    NAMELESS = 'NAMELESS'  # element that has no name
    UNORDERED = 'UNORDER'  # holds collection of nodes without order

    def __init__(self, name=None, children=None, kind=None, value=None):
        self.parent = None
        self.name = name
        self.value = value   # built-in value or matcher
        self.children = children or []  # list of Nodes
        self.kind = kind or Node.REGULAR

    def __repr__(self):
        return 'name={}; value={}; kind={}'.format(self.name, self.value, self.kind)


class Expected(object):
    def __init__(self, node, anchor=False, absent=False, order=False, fixed=False):
        self.node = node
        self.anchor = anchor  # if this value is not found, do not process siblings
        self.absent = absent  # if this value is in actual output -- it is an error
        self.order = order    # preserve order of children
        self.fixed = fixed    # required all children match, otherwise -- part is sufficient

        if self.node.kind == Node.UNORDERED:
            self.order = False

    def diff(self, actual):
        expected = self.node
        hits = 0
        if not isinstance(actual, Node):
            return Diff(Diff.TYPES_NOT_EQUAL, actual, expected, hits=hits)
        hits += 1

        if actual.kind != expected.kind:
            return Diff(Diff.TYPES_NOT_EQUAL, actual, expected, hits=hits)
        hits += 1

        if expected.kind is not Node.NAMELESS:
            if actual.name != expected.name:
                if self.absent is True:
                    return None
                return Diff(Diff.NAME_NOT_EQUAL, actual, expected, hits=hits)
            hits += 1

        if expected.value is not None and actual.value != expected.value:
            return Diff(Diff.VALUE_NOT_EQUAL, actual, expected, hits=hits)

        return self._diff_children(actual)

    def __repr__(self):
        return str(self.node)

    def _diff_children(self, actual_parent):
        return ChildrenDiffBuilder(actual_parent, self).build()


class ChildrenDiffBuilder(object):
    def __init__(self, actual_parent, expected_parent):
        self.actual_parent = actual_parent
        self.expected_parent = expected_parent.node
        self.settings = expected_parent
        self.matched_actuals = set()
        self.matched_expected = set()
        self.result_diff = Diff(Diff.CHILDREN_DIFF, self.actual_parent, self.expected_parent, misses=0)
        self.hypothesis = collections.defaultdict(dict)

    def _apply_side_by_side(self):
        """
        Проверяет присутствие элементов из множества ожидаемого среди элементов множества действительного
        Обновляет статистику по совпадениям и промахам
        Прикапывает всевозможные гипотезы для последующей фильтрации
        """
        last_matched_idx = -1
        last_matched = None

        for expected_idx, expected in enumerate(self.expected_parent.children):
            for actual_idx, actual in enumerate(self.actual_parent.children):
                if actual_idx in self.matched_actuals:
                    continue
                candidate_diff = expected.diff(actual)
                if candidate_diff is None:
                    if self.settings.order and last_matched_idx > actual_idx:
                        reorder_diff = Diff(Diff.CHILDREN_ORDER, last_matched, expected)
                        self.hypothesis[expected_idx][actual_idx] = reorder_diff
                        continue
                    self.matched_actuals.add(actual_idx)
                    self.matched_expected.add(expected_idx)
                    last_matched_idx = actual_idx
                    last_matched = actual
                    self.result_diff.hits += 1
                    break
                self.hypothesis[expected_idx][actual_idx] = candidate_diff
            else:
                self.result_diff.misses += 1

    def _apply_rule_fixed(self):
        """
        Применяет сравнение фиксированных по длине списков
        Применяется только если расслабленная проверка (без фиксированной длины) дала пустой дифф,
        т.к. иначе будет зашумление гипотез
        """
        for actual_idx, actual in enumerate(self.actual_parent.children):
            if actual_idx in self.matched_actuals:
                continue
            child_diff = Diff(Diff.VALUES_MORE, actual=actual, expected=self.expected_parent)
            self.result_diff.children.append(child_diff)
            self.result_diff.misses += 1

    def _add_good_hypothesis(self):
        """
        Добавляет только рабочие гипотезы в результирующий дифф, в частности
        пропускает гипотезы на ноды, которые уже сматчились
        """
        for expected_idx, expected in enumerate(self.expected_parent.children):
            if expected_idx in self.matched_expected:
                continue
            child_diff = Diff(Diff.CHILD_NOT_FOUND, self.actual_parent, expected)
            for actual_idx, actual in enumerate(self.actual_parent.children):
                if actual_idx in self.matched_actuals:
                    continue
                child_diff.children.append(self.hypothesis[expected_idx][actual_idx])
            self.result_diff.children.append(child_diff)

    def build(self):
        # todo support anchor
        self._apply_side_by_side()
        if self.result_diff.misses:
            self._add_good_hypothesis()
        elif self.settings.fixed:
            self._apply_rule_fixed()

        return self.result_diff if self.result_diff.misses else None


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


def test_good_list():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.NAMELESS),
        Node(name='1', value=2, kind=Node.NAMELESS),
        Node(name='2', value=3, kind=Node.NAMELESS)
    ])

    expected = Expected(node=Node(name='list', children=[
        Expected(Node(name='0', value=2, kind=Node.NAMELESS)),
        Expected(Node(name='1', value=3, kind=Node.NAMELESS))
    ]))

    assert expected.diff(actual) is None


def test_bad_list():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.NAMELESS),
        Node(name='1', value=2, kind=Node.NAMELESS),
        Node(name='2', value=3, kind=Node.NAMELESS)
    ])

    expected = Expected(node=Node(name='list', children=[
        Expected(Node(name='0', value=2, kind=Node.NAMELESS)),
        Expected(Node(name='1', value=4, kind=Node.NAMELESS))
    ]))

    actout = str(expected.diff(actual))
    assert 'CHILDREN DIFF' in actout
    assert 'CHILD NOT FOUND' in actout
    assert 'VALUE NOT EQUAL' in actout


def test_bad_list_ordered():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.NAMELESS),
        Node(name='1', value=2, kind=Node.NAMELESS),
        Node(name='2', value=3, kind=Node.NAMELESS)
    ])

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=3, kind=Node.NAMELESS)),
        Expected(Node(name='1', value=2, kind=Node.NAMELESS))
    ]))

    assert 'CHILDREN ORDER' in str(expected.diff(actual))

def test_good_list_ordered():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.NAMELESS),
        Node(name='1', value=2, kind=Node.NAMELESS),
        Node(name='2', value=3, kind=Node.NAMELESS)
    ])

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=1, kind=Node.NAMELESS)),
        Expected(Node(name='1', value=3, kind=Node.NAMELESS))
    ]))

    assert expected.diff(actual) is None


def test_good_list_ordered2():
    actual = Node(name='list', children=[
        Node(name='0', value=1, kind=Node.NAMELESS),
        Node(name='1', value=2, kind=Node.NAMELESS),
        Node(name='2', value=1, kind=Node.NAMELESS)
    ])

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=2, kind=Node.NAMELESS)),
        Expected(Node(name='1', value=1, kind=Node.NAMELESS))
    ]))

    assert expected.diff(actual) is None


def test_good_attrs_ordered():
    actual = Node(name='node', children=[
        Node(name='__xml_attributes__', kind=Node.UNORDERED, children=[
            Node(name='attr0', value=0),
            Node(name='attr1', value=1),
            Node(name='attr2', value=2)
        ])
    ])

    expected = Expected(order=True, node=Node(name='node', children=[
        Expected(Node(name='__xml_attributes__', kind=Node.UNORDERED, children=[
            Expected(Node(name='attr2', value=2)),
            Expected(Node(name='attr1', value=1)),
        ]))
    ]))

    assert expected.diff(actual) is None


def test_bad_attrs():
    actual = Node(name='node', children=[
        Node(name='__xml_attributes__', kind=Node.UNORDERED, children=[
            Node(name='attr0', value=0),
            Node(name='attr1', value=1),
            Node(name='attr2', value=2)
        ])
    ])

    expected = Expected(node=Node(name='node', children=[
        Expected(Node(name='__xml_attributes__', kind=Node.UNORDERED, children=[
            Expected(Node(name='attr2', value=3)),
            Expected(Node(name='attr1', value=1))
        ]))
    ]))

    assert 'VALUE NOT EQUAL' in str(expected.diff(actual))


def test_fixed_bad():
    actual = Node(name='node', children=[
        Node(name='zero', value=0),
        Node(name='one', value=1),
        Node(name='two', value=2)
    ])

    expected = Expected(fixed=True, node=Node(name='node', children=[
        Expected(Node(name='zero', value=0)),
        Expected(Node(name='one', value=1)),
    ]))

    assert 'VALUES MORE' in str(expected.diff(actual))


if __name__ == '__main__':
    test_good_list()
    test_bad_list()
    test_bad_list_ordered()
    test_good_list_ordered()
    test_good_list_ordered2()
    test_good_attrs_ordered()
    test_bad_attrs()
    test_fixed_bad()
