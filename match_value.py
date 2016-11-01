__author__ = 'Yura'


class Value(object):
    def __init__(self):
        self.attrs = [] # list of Value
        self.data = None # list of Value / int / string


class ExpectedValue(Value):
    def __init__(self):
        self.obligatory = True