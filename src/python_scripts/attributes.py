from typing import overload
from exceptions import *

# Practically just a key-value pair idea that I originally had
# deprecated since 2026/11/07
class Attribute(): # A simple outline for any possible attribute to serve in translation.
    name : str # The name of the attribute. 
    val : float 
    def __init__(self, _name : str, _val : float) -> None:
        self.name = _name
        self.val = _val
    def __str__(self) -> str:
        return f"Attribute instance with values\nName: {self.name}\nAttribute Value: {self.val}"
    def __repr__(self) -> str:
        return f"Attribute({self.name} : str, {self.val} : float)"
    
    def __eq__(self, other) -> bool:
        return self.name == other.name and self.val == other.val
    def __ne__(self, other) -> bool:
        return not self.__eq__(other)
    
    
    def __add__(self, other) -> "Attribute":
        if (self.name == other.name):
            return Attribute(self.name, self.val + other.val)
        else:
            raise IncompatibleAttribute(self, other)
    def __sub__(self, other) -> "Attribute":
        if (self.name == other.name):
            return Attribute(self.name, self.val - other.val)
        else:
            raise IncompatibleAttribute(self, other)

# A generic collection of attributes.
class AttributeCollection():
    collection : dict

    @overload 
    def __init__(self, keyval : tuple) -> None:
        if len(keyval) != 2:
            raise IndexError()
        else:
            self.collection = {
                keyval[0] : keyval[1]
            }
    @overload
    def __init__(self, key : str, val : float) -> None:
        self.collection = {
                key : val
        }
    @overload
    def __init__(self, collection : dict) -> None:
        self.collection = collection

    def __str__(self) -> str:
        return f"AttributeCollection instance with dictionary collection {self.collection}"
    def __repr__(self) -> str:
        return f"(default constructor) AttributeCollection({self.collection})"

    def __getitem__(self, key : str) -> float:
        return self.collection[key]
    def __setitem__(self, key, value):
        self.collection[key] = value

    @overload
    def __contains__(self, key : str) -> bool:
        return key in self.collection.keys
    @overload
    def __contains__(self, val : float):
        return val in self.collection.values

    def __iter__(self) -> None:
        return iter(self.collection) # python do this for me

    # Returns the collection as a 2d array in the format required by world.py
    # author Jacob Sexton
    # returns the 2 dimensional list to specify a set of attribute changes. 'No Change'  
    def toList(self) -> list: # Return the list in the format my teammates need it in
        myList : list = []
        for key, value in self.collection.items():
            if value == 0:
                myList.append([key, 'No Change'])
            else:
                myList.append([key, value])
        return myList