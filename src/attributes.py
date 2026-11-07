from typing import overload
from exceptions import *

class Attribute(): # A simple outline for any possible attribute to serve in translation.
    name : str # The name of the attribute. 
    val : float 
    def __init__(self, _name : str, _val : float):
        self.name = _name
        self.val = _val
    def __str__(self) -> str:
        return f"Attribute instance with values\nName: {self.name}\nAttribute Value: {self.val}"
    def __repr__(self):
        return f"Attribute({self.name} : str, {self.val} : float)"
    
    def __eq__(self, other):
        return self.name == other.name and self.val == other.val
    def __ne__(self, other):
        return not self.__eq__(other)
    
    
    def __add__(self, other):
        if (self.name == other.name):
            return Attribute(self.name, self.val + other.val)
        else:
            raise IncompatibleAttribute(self, other)
    def __sub__(self, other):
        if (self.name == other.name):
            return Attribute(self.name, self.val - other.val)
        else:
            raise IncompatibleAttribute(self, other)

class AttributeCollection(): # Generic collection of attributes. 
    collection : dict

    @overload 
    def __init__(self, keyval : tuple):
        if len(keyval) != 2:
            raise IndexError()
        else:
            self.collection = {
                keyval[0] : keyval[1]
            }
    @overload
    def __init__(self, key : str, val : float):
        self.collection = {
                key : val
        }
    @overload
    def __init__(self, collection : dict):
        self.collection = collection

    def __str__(self):
        return f"AttributeCollection instance with dictionary collection {self.collection}"
    def __repr__(self):
        return f"(default constructor) AttributeCollection({self.collection})"

    def __getitem__(self, key : str):
        return self.collection[key]

