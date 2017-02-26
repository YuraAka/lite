#!/usr/bin/env python
# coding=utf-8
import collections
import json
import itertools
__author__ = 'Yura'


"""
Основная идея:
- дерево выдачи описывается Node-иерархией
- у Node выделяется имя, значение, свойства, родитель и дети
- тип Node-a -- совокупность свойств
  - сравнение по типу происходит так: действительные свойства составляют подмножество ожидаемых
    * закрываем случай сравнения с корнем ожидания, напр:
      actual: 'one' : [1, 2, 3], expected: [1, 2, 3] => 'one' vs <unnamed>
- свойства могут быть: неупорядоченный, безымянный
  - неупорядоченный -- сравнения порядка не действуют на этот нод, напр. элементы дикта
  - безымянный -- сравнения имени не действуют на этот нод, напр. элементы списка
  - эффект сравнения действует с т.з. свойств ожидающего нода
    * если действительный нод не содержит свойств, а ожидающий содержит 'безымянный', то имя не будет учитываться
      при сравнении
- значение заполняется только у листовых нодов, имеет тип int, str, bool или матчер
- дети заполняются только у нелистовых нодов
- пример
  - {'name' : 1}, раскладывается на два элемента:
    * словарь: нод с именем 'dict', свойствами unordered, nameless
    * первый элемент словаря: нод с именем 'name' и значением 1, без детей, без свойств

  - <name one=1 two=2>text</name> раскладывается так:
    * нод с именем 'name', без значения, без свойств, с детьми:
      * первый с именем '__attrs__', со свойствами unordered, без значения, с детьми:
        * первый: имя 'one', значение 1
        * второй: имя 'two', значение 2
      * второй: имя 'text', значение 'text', свойства nameless, без детей

- ожидаемый фрагмент описывается Expected-синтаксисом, с доп. атрибутами, помогающими проверять различные аспекты
   соответствия:
   - четкое соответствие -- узлы в ожидании и действительности должны совпадать полностью
   - нечеткое соответствие -- узлы из ожидания должны быть подмножеством узлов из действительности
   - непрерывность -- узлы из ожидания должны быть непрерывным подмножеством узлов действительности
   - последовательность узлов -- ожидание формирует формулу последовательности, которой должна соответствовать действительность\
     - формула работает со сматченными нодами
     - каждый сматченный нод изменяет состояние ожидания
     - в конце теста проверяется ожидание формулы
     - при применении формулы может быть важен порядок, особенности зашиваются в формулу
     * [Increase] -- проверяет, что элементы списка возрастают
     * {'price' : Decrease, 'bid' : Constant} -- цена убывает, ставка не меняется
     - формулы делаются на основе матчеров с состоянием
     - формулы могут вычисляться динамически на основании данных
     * Price = Arg(), Discount = Arg()
     * {'price' : Price, 'discount' : Discount, 'oldprice' : Price * (1+Discount)}
     * <node price='$Price' discount='$Discount' oldprice='$Price*(1+Discount)'/>

   - отсутствие значения -- в действительности нет значения, которое есть в ожиданиях
   - маркер-якорь обязательного присутствия -- если в действительности нод не имеет этого атрибута,
    то ветка не раскручивается дальше и не участвует формировании гипотез. Нужно для разрешения неопределенности выбора гипотез

- логика проверки действительного и ожидаемого, порождающая Diff
- Diff -- информация о различии с возможностью ранжирования гипотез различия.
- Должно быть две фазы сбора дифа: быстрая и подробная -- если быстрая фейлится, то запускается подробная
- Мы не должны создавать диф на ноды с заполненным и незаполненным значением
- Не надо сравнивать список с диктом, и дочерные ноды с атрибутами (хмл), поэтому надо ввести тип элемента
- Алгоритмы ранжирования должны задаваться извне:
  - собираются цепочки соответствий и выбираются гипотезы с наибольшей длиной
  - соответствием считается по разному для разных типов нод:
    - лист -- полное соответствие
    - нелист -- частичное соответствие
      - имя
      - тип
- Кодеки выполняют декодирование входных данных: порожденных программой или заданных в тесте, и кодирование фрагмента
 для печати ошибки

todo:
- better rating calc
- json codec
- most probable hypotesis selection
- anchor support
- xml codec
- sequence -- extension of order

diff importance pyramid:

Node-instance
type
name
value
children content
children fixed set
children order/sequence

"""


class Mismatch(object):
    pass

class Diff(object):
    """
    Описывает различие, и присваивает весь каждому различию. Могут быть:
    - различие в дочернем поддереве
    - нашли неизвестный узел
    - узлы различаются типом
    - узлы различаются именем
    - нежданный узел
    - значения узла различаются
    - дочерний узел не найден
    - лишний дочерний узел
    """
    @staticmethod
    def subtree_mismatch(actual, expected):
        return AggregationDiff('Subtree mismatch', actual, expected)

    @staticmethod
    def unknown_node(actual, expected):
        return Diff('Unknown node', actual, expected)

    @staticmethod
    def types_mismatch(actual, expected):
        return Diff('Types mismatch', actual, expected)

    @staticmethod
    def names_mismatch(actual, expected):
        return Diff('Names mismatch', actual, expected)

    @staticmethod
    def unexpected_node(actual, expected):
        return Diff('Unexpected node', actual, expected)

    @staticmethod
    def values_mismatch(actual, expected):
        return Diff('Values mismatch', actual, expected)

    @staticmethod
    def children_mismatch(actual, expected):
        return AggregationDiff('Children mismatch', actual, expected)

    @staticmethod
    def lost_child(actual, expected):
        absent = Actual(Node('<absent>', parent=actual))
        return AggregationDiff('Child is not found', absent, expected)

    @staticmethod
    def extra_child(actual, expected):
        return Diff('Extra child is found', actual, expected)

    @staticmethod
    def wrong_order(actual, expected):
        return Diff('Wrong sequence order', actual, expected)

    def __init__(self, text, actual, expected):
        if not isinstance(actual, Actual):
            raise RuntimeError("actual is not Actual")

        if not isinstance(expected, Expected):
            raise RuntimeError("expected is not Expected")

        self.__actual = actual
        self.__expected = expected
        self.__text = text

    def __repr__(self):
        return self.render(0)

    @property
    def expected(self):
        return self.__expected

    @property
    def actual(self):
        return self.__actual

    #@property
    #def depth(self):
        #return max([child.depth for child in self.__children]) + 1 if self.__children else 1

    @property
    def leafs(self):
        if len(self.__children) == 0:
            return [self]

        result = []
        for child in self.__children:
            result += child.leafs
        return result


    def render(self, level, depth=None):
        out = \
        '{tab}text = {text}\n' \
        '{tab}rate = {rate}\n' \
        '{tab}expected = {expected}\n' \
        '{tab}actual = {actual}\n\n'.format(
            text=self.__text,
            expected=self.__expected.node.path,
            actual=self.__actual.node.path,
            tab='-'*level,
            #depth=self.depth,
            rate=self.rank
        )

        return out


class AggregationDiff(Diff):
    def __init__(self, text, actual, expected):
        super(AggregationDiff, self).__init__(text, actual, expected)

        self.__children = []
        self.__hits = 0
        self.__misses = 0

    def add_reason(self, child_diff):
        assert child_diff is not None
        self.__children.append(child_diff)
        self.__misses += 1
        return True

    def add_match(self, value=1):
        self.__hits += value

    def effective(self):
        if self.__misses == 0:
            return None
        return self

    def prune_by(self, key):
        if len(self.__children) == 0:
            return

        def equal(lhs, rhs):
            return key(lhs) == key(rhs)

        self.__children.sort(key=key, reverse=True)
        #print [c.depth for c in self.children]
        self.__children = [child for child in self.__children if equal(child, self.__children[0])]

        for child in self.__children:
            child.prune_by(key)

    def render(self, level, depth=None):
        out = Diff.render(self, level, depth)

        if depth is None or depth > 0:
            if depth is not None:
                depth -= 1
            for child in self.__children:
                out += child.render(level+1, depth)

        return out

    def leafs(self):
        result = []
        for child in self.__children:
            result += child.leafs()
        return result

    @property
    def majority(self):
        return 100 * self.__hits / (self.__hits + self.__misses)


class FitSnippet(object):
    def __init__(self):
        self.actual = None
        self.expected = None


class FitResult(object):
    @staticmethod
    def success():
        return FitResult(success=True)

    @staticmethod
    def ignore():
        return FitResult(ignore=True)

    def __init__(self, text=None, success=False, snippet=None, ignore=False):
        # textual description of mismatch
        self.text = text

        # output snippet to compare differences
        self.snippet = snippet

        # exact match
        self.success = success if not ignore else False

        # full mismatch and dont worth to be analysed
        self.ignore = ignore

    def __nonzero__(self):
        return self.success


class Node(object):
    def __init__(self, children=None, capture=False):
        self.parent = None

        # использовать при выводе сниппета
        self.tag = None

        # где-то в иерархии узлов есть capture-узел -- это изменяет логику проверок: надо крутить циклы до конца,
        # а не выходить при первом хите, т.к. нужно посетить все потенциально подходящие фрагменты
        self.capture = capture
        self.children = children or []
        for idx, child in enumerate(self.children):
            child.parent = self
            child.position = idx
            self.capture = self.capture or child.capture

    def __iter__(self):
        yield self
        for child in self.children:
            yield next(iter(child))

    def render(self, level, recurse=True):
        out = '{tab}{kind} {name}={value}'.format(name=self.name, value=self.value, kind=self.kind, tab=' ' * level)

        if recurse is True:
            for child in self.values:
                out += child.node.render(level + 1)

        return out


class AtomNode(Node):
    @staticmethod
    def type_of(obj):
        return isinstance(obj, (int,str,bool,float))

    def __init__(self, value, absent=False):
        super(self.__class__, self).__init__()
        if not AtomNode.type_of(value):
            raise RuntimeError('bad atom type')
        self.value = value

    def __repr__(self):
        return 'Atom({})'.format(self.value)

    def fit(self, other):
        if not isinstance(other, AtomNode):
            return FitResult.ignore()
        if self.value == other.value:
            return FitResult.success()
        return FitResult(text='{} != {}'.format(self.value, other.value))


class NamedNode(Node):
    def __init__(self, name, value, anchor=False, absent=False):
        super(self.__class__, self).__init__([value])
        self.name = name
        self.value = value

    def fit(self, other):
        if not isinstance(other, NamedNode):
            return FitResult.ignore()
        if self.name != other.name:
            return FitResult(text='names {} != {}'.format(self.name, other.name))
        return self.value.fit(other.value)


class ListNode(Node):
    def __init__(self, values, order=False, fixed=False, contiguous=False):
        super(self.__class__, self).__init__(values)

    def fit(self, other):
        """
        Перебирает все узлы из действительной иерархии, примеряя ее на текущее ожидание
        capture -- перебрать все узлы для сбора данных и проверки последовательности
        """
        # todo describe better
        result = FitResult(text='cannot find list')
        for actual in other:
            local_result = self._fit_local(actual)
            if local_result:
                result = FitResult.success()
                if self.capture is False:
                    return result
            elif not result.success and not local_result.ignore:
                # selection logic
                result = local_result
        return result

    def _fit_local(self, other):
        """
        Сравнивает выбранный корень в действительной иерархии с текущей ожидаемой
        Проверяет присутствие элементов из множества ожидаемого среди элементов множества действительного
        Обновляет статистику по совпадениям и промахам
        Прикапывает всевозможные гипотезы для последующей фильтрации
        """
        if not isinstance(other, ListNode):
            return FitResult.ignore()
        used_actuals = set()
        used_expected = set()
        for expected_idx, expected in enumerate(self.children):
            for actual_idx, actual in enumerate(other.children):
                if actual_idx in used_actuals:
                    continue
                does_fit = expected.fit(actual)
                if does_fit:
                    used_actuals.add(actual_idx)
                    used_expected.add(expected_idx)
                    break

        if len(used_expected) == len(self.children):
            return FitResult.success()
        return FitResult(text='subchildren are not matched')


class CaptureNode(Node):
    def __init__(self):
        super(self.__class__, self).__init__(capture=True)
        self.captured = []

    def fit(self, other):
        if not isinstance(other, AtomNode):
            return FitResult.ignore()
        self.captured.append(other.value)
        return FitResult.success()

    def increased(self):
        return all(x < y for x, y in zip(self.captured, self.captured[1:]))

    def __add__(self, other):
        if len(self.captured) != len(other.captured) or len(self.captured) == 0:
            return None
        sum = [x + y for x, y in zip(self.captured, other.captured)]
        if all(x == sum[0] for x in sum):
            return sum[0]
        return None

# ====

class Expected(object):
    def __init__(self, node, anchor=False, absent=False, order=False, fixed=False, contiguous=False):
        self.node = node
        self.anchor = anchor  # if this value is not found, do not process siblings
        self.absent = absent  # if this value is in actual -- it is an error
        self.order = order    # preserve order of children
        self.fixed = fixed    # required all children match, otherwise -- part is sufficient
        self.contiguous = contiguous # if expected children fit to contiguous actual range -- ok, otherwise -- false
        self.formula = None   # apply formula on match

        if Node.UNORDERED in self.node.props:
            self.order = False
            self.contiguous = False

    def diff(self, actual):
        expected = self.node
        actual = actual.node



    def _traverse(self, root):
        yield root
        for child in root.node.children:
            yield next(self._traverse(child))

    def _diff_branch(self, actual):
        node_diff = self._diff_node(actual)
        return self._diff_children(actual) if node_diff is None else node_diff

    def _diff_node(self, actual):
        # todo how rank node matching???
        expected = self
        if not isinstance(actual.node, Node):
            return Diff.unknown_node(actual, expected)

        # equality compare is wrong, because extected root can have more props than matching actual node (nameless)
        if actual.node.props - expected.node.props:
            return Diff.types_mismatch(actual, expected)

        if Node.NAMELESS not in expected.node.props:
            if actual.node.name != expected.node.name:
                return Diff.names_mismatch(actual, expected) if expected.absent is False else None
            elif expected.absent is True:
                return Diff.unexpected_node(actual, expected)

        if expected.node.value is not None and actual.node.value != expected.node.value:
            return Diff.values_mismatch(actual, expected)

        return None

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
        self.children_diff = Diff.children_mismatch(self.actual_parent, self.expected_parent)

    def _apply_by_node_cmp(self):
        """
        Проверяет присутствие элементов из множества ожидаемого среди элементов множества действительного
        Обновляет статистику по совпадениям и промахам
        Прикапывает всевозможные гипотезы для последующей фильтрации
        """

        used_actuals = []
        used_expected = []
        hypothesis = collections.defaultdict(dict)
        for expected_idx, expected in enumerate(self.expected_parent.node.children):
            for actual_idx, actual in enumerate(self.actual_parent.node.children):
                if actual_idx in used_actuals:
                    continue
                child_mismatched = expected.diff(actual)
                if child_mismatched is None:
                    used_actuals.append(actual_idx)
                    used_expected.append(expected_idx)
                    break
                hypothesis[expected_idx][actual_idx] = child_mismatched
            else:
                hypothesis[expected_idx][-1] = Diff.lost_child(self.actual_parent, expected)

        return self._filter_hypothesis(used_actuals, used_expected, hypothesis)

    def _apply_rule_ordered(self):
        last_matched_idx = -1
        last_matched = None
        actual_children = self.actual_parent.node.children
        next_matched_candidate = None if len(actual_children) == 0 else actual_children[0]

        # todo continue
        hypothesis = collections.defaultdict(dict)
        for expected_idx, expected in enumerate(self.expected_parent.node.children):
            for actual_idx, actual in enumerate(self.actual_parent.node.children):
                if actual_idx in self.matched_actuals:
                    continue
                candidate_diff = expected.diff(actual)
                if candidate_diff is None:
                    if self.expected_parent.order and last_matched_idx > actual_idx:
                        reorder_diff = Diff.wrong_order(last_matched, expected)
                        # reorder_diff = Diff.wrong_order(actual, expected)
                        # todo reorder_diff.hits = len(self.expected_parent.node.children)
                        hypothesis[expected_idx][actual_idx] = reorder_diff
                        continue
                    self.matched_actuals.add(actual_idx)
                    self.matched_expected.add(expected_idx)
                    last_matched_idx = actual_idx
                    last_matched = actual
                    self.children_diff.add_match()
                    break
                hypothesis[expected_idx][actual_idx] = candidate_diff
            else:
                return True
        return False

    def _apply_rule_fixed(self):
        """
        Применяет сравнение фиксированных по длине списков
        Применяется только если расслабленная проверка (без фиксированной длины) дала пустой дифф,
        т.к. иначе будет зашумление гипотез
        """
        for actual_idx, actual in enumerate(self.actual_parent.node.children):
            if actual_idx in self.matched_actuals:
                continue
            extra_child = Diff.extra_child(actual, self.expected_parent)
            self.children_diff.add_reason(extra_child)

    def _apply_rule_contiguous(self):
        """
        Применяет проверку непрерывности ожидаемых значений в действительном множестве
        """
        # todo
        pass

    def _add_to_result(self, hypothesis):
        for reason in [reason for reason in [reason_pack.itervalues() for reason_pack in hypothesis.itervalues()]]:
            self.children_diff.add_reason(reason)

    def _filter_hypothesis(self, used_actuals, used_expected, hypothesis):
        # удаляем гипотезы на сматченные объекты
        for expected_idx in used_expected:
            if expected_idx in hypothesis:
                del hypothesis[expected_idx]

        for expected_idx in hypothesis.iterkeys():
            for actual_idx in used_actuals:
                if actual_idx in hypothesis[expected_idx]:
                    del hypothesis[expected_idx][actual_idx]

        return hypothesis

    def build(self):
        # todo support anchor
        mismatches = self._apply_by_node_cmp()
        if mismatches:
            self._add_to_result(mismatches)
        elif self.expected_parent.fixed:
            self._apply_rule_fixed()

        return self.children_diff.effective()


class JsonCodec(object):
    @classmethod
    def encode_actual(cls, text):
        """
        Encodes textual representation of actual json to tree of Nodes
        :param text: json string under test
        :return: tree of Nodes
        """
        src = json.loads(text)
        result = cls._encode_obj('<root>', src, lambda x: Actual(x))
        result.node.props.add(Node.NAMELESS)
        return result

    @classmethod
    def encode_expected(cls, src, order=False):
        """
        Encodes textual representation of json-expectation to tree of Expected
        :param text: json-expectation
        :return: tree of Expected
        """

        # todo anchor can be represented in wrapper: &name => name with anchor
        result = cls._encode_obj('<root>', src, lambda x: Expected(x, order=order))
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
            result_child.node.parent = result
            result.values.append(result_child)
        return wrap(result)

    @classmethod
    def _encode_list(cls, name, value, wrap):
        result = Node(name=name)
        for child_idx, child_value in enumerate(value):
            result_child = cls._encode_obj(str(child_idx), child_value, wrap)
            result_child.node.props.add(Node.NAMELESS)
            result_child.node.parent = result
            result.values.append(result_child)
        return wrap(result)

    @classmethod
    def _encode_atom(cls, name, value, wrap):
        return wrap(Node(name=name, value=value))


def test_describe():
    """
    {'abc': [1,2,3]}

    """

    r = ListNode(values=[
            NamedNode(name='abc', value=ListNode(values=[
                AtomNode(2),
                AtomNode(1),
                AtomNode(3)
            ]))
        ])

    #print r


def test_good_list():
    actual = ListNode([
        AtomNode(1),
        AtomNode(2),
        AtomNode(3)
    ])

    expected = ListNode([
        AtomNode(2),
        AtomNode(3)
    ])

    assert expected.fit(actual)
    assert not actual.fit(expected)


def test_formula():
    actual = ListNode([
        ListNode([
            NamedNode('fee', AtomNode(10)),
            NamedNode('bid', AtomNode(1)),
        ]),
        ListNode([
            NamedNode('bid', AtomNode(2)),
            NamedNode('fee', AtomNode(9))
        ]),
        ListNode([
            NamedNode('bid', AtomNode(3)),
            NamedNode('fee', AtomNode(8)),
        ])
    ])

    # diag -- extra values check
    bid = CaptureNode()
    fee = CaptureNode()
    expected = ListNode([NamedNode('bid', bid), NamedNode('fee', fee)])
    assert expected.fit(actual)
    assert bid + fee == 11
    assert bid.increased() is True


def test_missed_value():
    actual = ListNode([
        AtomNode(1),
        AtomNode(2),
        AtomNode(3),
    ])

    expected = ListNode([
        AtomNode(1),
        AtomNode(4),
    ])

    # error:
    # - cannot find 4 (*)
    #   - 4 != 2  (good if one)
    #   - 4 != 3

    result = expected.fit(actual)

    #reasons = result.prune().leafs()
    #assert len(reasons) == 2
    #assert reasons[0].expected.node.value == 4 and reasons[0].actual.node.value == 1
    #assert reasons[1].expected.node.value == 4 and reasons[1].actual.node.value == 3

    """
    green -- matched parts
    yellow -- suspicios actual parts
    red -- non-matched expected parts

    [1, 2, 3] vs [1, 4] => no element 4
    [1, 2] vs [1, 4] => no element 4, due to 2 != 4
    {'a':1, 'b':2, 'c':3} vs {'a':1, 'c':4} => no element 'c':4 due to 'c':3
    {'a':1, 'b':2, 'c':3} vs {'a':1, 'd':4} => no element 'd':4
    {'a':1, 'b':2} vs {'a':1, 'd':4} => no element 'd':4
    # error:
      - cannot find "green" : 4
        - green != blue (good if one)
        - 4 != 3 (*) (green == green)
    actual = ListNode([
        NamedNode("red", AtomNode(1)),
        NamedNode("blue", AtomNode(2)),
        NamedNode("green", AtomNode(3)),
    ])

    expected = ListNode([
        NamedNode("red", AtomNode(1)),
        NamedNode("green", AtomNode(4)),
    ])

    actual = {

    }
    """


def test_bad_list_ordered():
    actual = Actual(Node(name='list', children=[
        Actual(Node(name='0', value=1, props={Node.NAMELESS})),
        Actual(Node(name='1', value=2, props={Node.NAMELESS})),
        Actual(Node(name='2', value=3, props={Node.NAMELESS}))
    ]))

    expected = Expected(order=True, node=Node(name='list', children=[
        Expected(Node(name='0', value=2, props={Node.NAMELESS})),
        Expected(Node(name='1', value=1, props={Node.NAMELESS}))
    ]))

    print expected.diff(actual).prune().leafs()


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


def test_json_encode_good():
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

    assert expected_int.diff(actual_int) is None


def test_json_encode_bad():
    actual = {
        'hello': [1, 2, 3],
        'world': {
            'name1': [6, 4, 5],
            'color': 'red'
        },
        'ball': {
            'name1': [6, 5, 4],
            'color': 'red',
            'some': 'thing'
        }
    }

    actual_str = json.dumps(actual)

    expected = {
        'name1': [4, 5, 6],
        'color': 'red',
        'some': 'thing'
    }

    actual_int = JsonCodec.encode_actual(actual_str)
    expected_int = JsonCodec.encode_expected(expected, order=True)

    diff = expected_int.diff(actual_int)
    diff.prune()
    leafs = diff.leafs
    print leafs
    #assert len(leafs) == 1
    #assert '<root>/world/name1/2' in leafs[0].render(0)

    #diff.prune()
    #print diff.render(0)


if __name__ == '__main__':
    test_describe()
    test_good_list()
    test_formula()
    """test_missed_value()
    test_bad_list_ordered()
    test_good_list_ordered()
    test_good_list_ordered2()
    test_good_attrs_ordered()
    test_bad_attrs()
    test_fixed_bad()
    test_json_encode_good()
    test_json_encode_bad()
    """

