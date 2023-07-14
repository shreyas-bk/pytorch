from typing import Dict, List
import inspect

import torch
from ..utils import (
    istype,
)
from .base import VariableTracker


class PlacementClassVariable(VariableTracker):
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    @staticmethod
    def is_placement_type(value):
        # we can't rely on importing/accessing torch distributed, it is not always built.
        if torch.distributed.is_available():
            from torch.distributed._tensor.placement_types import Placement

            return issubclass(value, Placement)
        return False

    def call_function(
        self, tx, args: "List[VariableTracker]", kwargs: "Dict[str, VariableTracker]"
    ) -> "VariableTracker":
        options = VariableTracker.propagate(self, args, kwargs.values())
        if (
            inspect.getattr_static(self.value, "__new__", None) in (object.__new__,)
            and self.source
        ):
            # NOTE: we don't need to track mutations to the placement class as they
            # suppose to be immutable.
            new_obj = object.__new__(self.value)
            var = PlacementVariable(new_obj, **options)
            if inspect.getattr_static(self.value, "__init__", None):
                return var.add_options(var.call_method(tx, "__init__", args, kwargs))

        return super().call_function(tx, args, kwargs)


class PlacementVariable(VariableTracker):
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    @staticmethod
    def is_placement(value):
        # we can't rely on importing/accessing torch distributed, it is not always built.
        if torch.distributed.is_available():
            from torch.distributed._tensor.placement_types import Placement

            return istype(value, Placement)
        return False

    def as_python_constant(self):
        return self.value

    def call_method(
        self,
        tx,
        name,
        args: "List[VariableTracker]",
        kwargs: "Dict[str, VariableTracker]",
    ) -> "VariableTracker":
        from . import ConstantVariable
        options = VariableTracker.propagate(self, args, kwargs.values())
        allowed_methods = ["__init__", "__setattr__"]
        # placement types dynamo tracking allows only __init__
        # and __setattr__ methods, the latter is for case like `Shard(dim)`
        if name in allowed_methods:
            try:
                method = inspect.getattr_static(type(self.value), name)
            except AttributeError:
                method = None
            if method is object.__init__:
                return ConstantVariable(None, **options)

            args = [x.as_python_constant() for x in args]
            kwargs = {k: v.as_python_constant() for k, v in kwargs.items()}
            method(self.value, *args, **kwargs)
            return self

        return super().call_method(tx, name, args, kwargs)

class DeviceMeshVariable(VariableTracker):
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    @staticmethod
    def is_device_mesh(value):
        # we can't rely on importing/accessing torch distributed, it is not always built.
        if torch.distributed.is_available():
            from torch.distributed._tensor.device_mesh import DeviceMesh

            return istype(value, DeviceMesh)
        return False

    def as_python_constant(self):
        return self.value
