#!/usr/bin/env python
# coding=utf-8
import collections
import json

__author__ = 'Yura'


# todo test
"""
todo:
- json codec
- anchor support
- xml codec
"""


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

    # todo actual of type Actual, expected of type Expected
    def __init__(self, kind, actual, expected, hits=0, misses=1):
        if not isinstance(actual, Actual):
            raise RuntimeError("actual is not Actual")

        if not isinstance(expected, Expected):
            raise RuntimeError("expected is not Expected")

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
        '{tab}expected = \n{expected}\n' \
        '{tab}actual = \n{actual}\n\n'.format(
            kind=self.kind,
            hits=self.hits,
            misses=self.misses,
            expected=self.expected.node.render(level+1),
            actual=self.actual.node.render(level+1),
            tab=' '*level
        )

        for child in self.children:
            out += child.render(level+1)

        return out


class Node(object):
    NAMELESS = 'NAMELESS'  # element with irrelevant name
    UNORDERED = 'UNORDERED'  # holds collection of nodes without order

    def __init__(self, name=None, children=None, props=None, value=None):
        self.parent = None
        self.name = name
        self.value = value   # built-in value or matcher
        self.children = children or []  # list of Nodes
        self.props = props or set()

    def __repr__(self):
        return self.render(0)

    def render(self, level):
        out = \
            '{tab}name = {name}\n' \
            '{tab}value = {value}\n' \
            '{tab}props = {props}\n\n'.format(
                name=self.name,
                value=self.value,
                props=self.props,
                tab=' ' * level
            )

        for child in self.children:
            out += child.node.render(level + 1)

        return out


class Actual(object):
    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return repr(self.node)


class Expected(object):
    def __init__(self, node, anchor=False, absent=False, order=False, fixed=False):
        self.node = node
        self.anchor = anchor  # if this value is not found, do not process siblings
        self.absent = absent  # if this value is in actual output -- it is an error
        self.order = order    # preserve order of children
        self.fixed = fixed    # required all children match, otherwise -- part is sufficient

        if Node.UNORDERED in self.node.props:
            self.order = False

    def diff(self, actual):
        # todo clean confusing Expected and Actual vs Expected.Node and Actual.Node
        expected = self
        expected_node = self.node
        actual_node = actual.node
        hits = 0
        if not isinstance(actual_node, Node):
            return Diff(Diff.TYPES_NOT_EQUAL, actual, expected, hits=hits)
        hits += 1

        # equality compare is wrong, because extected root can have more props than matching actual node (nameless)
        if actual_node.props - expected_node.props:
            return Diff(Diff.TYPES_NOT_EQUAL, actual, expected, hits=hits)
        hits += 1

        if Node.NAMELESS not in expected_node.props:
            if actual_node.name != expected_node.name:
                if self.absent is True:
                    return None
                return Diff(Diff.NAME_NOT_EQUAL, actual, expected, hits=hits)
            hits += 1

        if expected_node.value is not None and actual_node.value != expected_node.value:
            return Diff(Diff.VALUE_NOT_EQUAL, actual, expected, hits=hits)

        return self._diff_children(actual)

    def __repr__(self):
        return str(self.node)

    def _diff_children(self, actual_parent):
        return ChildrenDiffBuilder(actual_parent, self).build()


class ChildrenDiffBuilder(object):
    def __init__(self, actual_parent, expected_parent):
        self.actual_parent = actual_parent
        self.expected_parent = expected_parent
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

        for expected_idx, expected in enumerate(self.expected_parent.node.children):
            for actual_idx, actual in enumerate(self.actual_parent.node.children):
                if actual_idx in self.matched_actuals:
                    continue
                candidate_diff = expected.diff(actual)
                if candidate_diff is None:
                    if self.expected_parent.order and last_matched_idx > actual_idx:
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
        for actual_idx, actual in enumerate(self.actual_parent.node.children):
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
        for expected_idx, expected in enumerate(self.expected_parent.node.children):
            if expected_idx in self.matched_expected:
                continue
            child_diff = Diff(Diff.CHILD_NOT_FOUND, self.actual_parent, expected)
            for actual_idx, actual in enumerate(self.actual_parent.node.children):
                if actual_idx in self.matched_actuals:
                    continue
                child_diff.children.append(self.hypothesis[expected_idx][actual_idx])
            self.result_diff.children.append(child_diff)

    def build(self):
        # todo support anchor
        self._apply_side_by_side()
        if self.result_diff.misses:
            self._add_good_hypothesis()
        elif self.expected_parent.fixed:
            self._apply_rule_fixed()

        return self.result_diff if self.result_diff.misses else None


class JsonCodec(object):
    @classmethod
    def encode_actual(cls, text):
        """
        Encodes textual representation of actual json to tree of Nodes
        :param text: json string under test
        :return: tree of Nodes
        """
        src = json.loads(text)
        result = cls._encode_obj('_', src, lambda x: Actual(x))
        result.node.props.add(Node.NAMELESS)
        return result

    @classmethod
    def encode_expected(cls, src):
        """
        Encodes textual representation of json-expectation to tree of Expected
        :param text: json-expectation
        :return: tree of Expected
        """

        # todo anchor can be represented in wrapper: &name => name with anchor
        result = cls._encode_obj('_', src, lambda x: Expected(x))
        result.node.props.add(Node.NAMELESS)
        return result

    @classmethod
    def decode(cls, diff):
        """
        Decodes differences in json form
        :param diff: tree of Diff
        :return: json comparison representation
        """
        pass

    @classmethod
    def _encode_obj(cls, name, value, wrap):
        if isinstance(value, dict):
            return cls._encode_dict(name, value, wrap)
        if isinstance(value, list):
            return cls._encode_list(name, value, wrap)
        if isinstance(value, (int, float, str, unicode)) or value is None:
            return cls._encode_atom(name, value, wrap)
        raise RuntimeError('Unsupported type of {}: {} => {}'.format(name, value, type(value)))

    @classmethod
    def _encode_dict(cls, name, value, wrap):
        result = Node(name=name, props={Node.UNORDERED})
        for child_name, child_value in value.iteritems():
            result_child = cls._encode_obj(child_name, child_value, wrap)
            result.children.append(result_child)
        return wrap(result)

    @classmethod
    def _encode_list(cls, name, value, wrap):
        result = Node(name=name)
        for child_idx, child_value in enumerate(value):
            result_child = cls._encode_obj(str(child_idx), child_value, wrap)
            result_child.node.props.add(Node.NAMELESS)
            result.children.append(result_child)
        return wrap(result)

    @classmethod
    def _encode_atom(cls, name, value, wrap):
        return wrap(Node(name=name, value=value))


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
    actual = Actual(Node(name='list', children=[
        Actual(Node(name='0', value=1, props={Node.NAMELESS})),
        Actual(Node(name='1', value=2, props={Node.NAMELESS})),
        Actual(Node(name='2', value=3, props={Node.NAMELESS}))
    ]))

    expected = Expected(node=Node(name='list', children=[
        Expected(Node(name='0', value=2, props={Node.NAMELESS})),
        Expected(Node(name='1', value=3, props={Node.NAMELESS}))
    ]))

    assert expected.diff(actual) is None


def test_bad_list():
    actual = Actual(Node(name='list', children=[
        Actual(Node(name='0', value=1, props={Node.NAMELESS})),
        Actual(Node(name='1', value=2, props={Node.NAMELESS})),
        Actual(Node(name='2', value=3, props={Node.NAMELESS}))
    ]))

    expected = Expected(node=Node(name='list', children=[
        Expected(Node(name='0', value=2, props={Node.NAMELESS})),
        Expected(Node(name='1', value=4, props={Node.NAMELESS}))
    ]))

    actout = str(expected.diff(actual))
    assert 'CHILDREN DIFF' in actout
    assert 'CHILD NOT FOUND' in actout
    assert 'VALUE NOT EQUAL' in actout


def test_bad_list_ordered():
    actual = Actual(Node(name='list', children=[
        Actual(Node(name='0', value=1, props={Node.NAMELESS})),
        Actual(Node(name='1', value=2, props={Node.NAMELESS})),
        Actual(Node(name='2', value=3, props={Node.NAMELESS}))
    ]))

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=3, props={Node.NAMELESS})),
        Expected(Node(name='1', value=2, props={Node.NAMELESS}))
    ]))

    assert 'CHILDREN ORDER' in str(expected.diff(actual))


def test_good_list_ordered():
    actual = Actual(Node(name='list', children=[
        Actual(Node(name='0', value=1, props={Node.NAMELESS})),
        Actual(Node(name='1', value=2, props={Node.NAMELESS})),
        Actual(Node(name='2', value=3, props={Node.NAMELESS}))
    ]))

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=1, props={Node.NAMELESS})),
        Expected(Node(name='1', value=3, props={Node.NAMELESS}))
    ]))

    assert expected.diff(actual) is None


def test_good_list_ordered2():
    actual = Actual(Node(name='list', children=[
        Actual(Node(name='0', value=1, props={Node.NAMELESS})),
        Actual(Node(name='1', value=2, props={Node.NAMELESS})),
        Actual(Node(name='2', value=1, props={Node.NAMELESS}))
    ]))

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=2, props={Node.NAMELESS})),
        Expected(Node(name='1', value=1, props={Node.NAMELESS}))
    ]))

    assert expected.diff(actual) is None


def test_good_attrs_ordered():
    actual = Actual(Node(name='node', children=[
        Actual(Node(name='__xml_attributes__', props={Node.UNORDERED}, children=[
            Actual(Node(name='attr0', value=0)),
            Actual(Node(name='attr1', value=1)),
            Actual(Node(name='attr2', value=2))
        ]))
    ]))

    expected = Expected(order=True, node=Node(name='node', children=[
        Expected(Node(name='__xml_attributes__', props={Node.UNORDERED}, children=[
            Expected(Node(name='attr2', value=2)),
            Expected(Node(name='attr1', value=1)),
        ]))
    ]))

    assert expected.diff(actual) is None


def test_bad_attrs():
    actual = Actual(Node(name='node', children=[
        Actual(Node(name='__xml_attributes__', props={Node.UNORDERED}, children=[
            Actual(Node(name='attr0', value=0)),
            Actual(Node(name='attr1', value=1)),
            Actual(Node(name='attr2', value=2))
        ]))
    ]))

    expected = Expected(node=Node(name='node', children=[
        Expected(Node(name='__xml_attributes__', props={Node.UNORDERED}, children=[
            Expected(Node(name='attr2', value=3)),
            Expected(Node(name='attr1', value=1))
        ]))
    ]))

    assert 'VALUE NOT EQUAL' in str(expected.diff(actual))


def test_fixed_bad():
    actual = Actual(Node(name='node', children=[
        Actual(Node(name='zero', value=0)),
        Actual(Node(name='one', value=1)),
        Actual(Node(name='two', value=2))
    ]))

    expected = Expected(fixed=True, node=Node(name='node', children=[
        Expected(Node(name='zero', value=0)),
        Expected(Node(name='one', value=1)),
    ]))

    assert 'VALUES MORE' in str(expected.diff(actual))


def test_json_encode():
    actual = {
        'hello': [1, 2, 3],
        'world': {
            'name1': [4, 5],
            'color': 'red'
        }
    }

    actual_str = json.dumps(actual)

    expected = {
        'name1': [4, 5],
        'color': 'red'
    }

    actual_int = JsonCodec.encode_actual(actual_str)
    expected_int = JsonCodec.encode_expected(expected)

    print expected_int.diff(actual_int)


if __name__ == '__main__':
    test_good_list()
    test_bad_list()
    test_bad_list_ordered()
    test_good_list_ordered()
    test_good_list_ordered2()
    test_good_attrs_ordered()
    test_bad_attrs()
    test_fixed_bad()
    test_json_encode()
