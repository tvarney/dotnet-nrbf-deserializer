#!/usr/bin/env python3

import argparse

from dotnet.object import PrimitiveArray, ClassInstance
from dotnet.io.binary import BinaryFormatter

import typing
if typing.TYPE_CHECKING:
    from typing import Dict, Tuple
    from dotnet.object import ClassObject, Instance


def inspect_classes(classes: 'Dict[Tuple[int, str], ClassObject]', libraries: 'Dict[int, str]'):
    print("Read {} classes".format(len(classes)))
    for class_key, class_obj in classes.items():
        print("  Class {}".format(class_key))
        for member in class_obj.members:
            extra_info = member.extra_info.name if member.binary_type == 0 else member.extra_info
            print("    {}: {}, {}".format(member.name, member.binary_type.name, extra_info))


def inspect_objects(objects: 'Dict[int, Instance]'):
    print("Read {} objects".format(len(objects)))
    for obj_id, obj in objects.items():
        print("  object[{}]: {}".format(obj_id, type(obj).__name__))
        inspect_instance(obj)


def inspect_instance(instance: 'Instance') -> None:
    instance_type = type(instance)
    if instance_type is ClassInstance:
        instance: ClassInstance
        inspect_class_inst(instance)
    elif instance_type is PrimitiveArray:
        instance: PrimitiveArray
        inspect_primitive_array(instance)


def inspect_primitive_array(inst: 'PrimitiveArray') -> None:
    print("    Data Type: {}".format(inst.primitive_class.__name__))
    print("    Values:")
    for i, value in enumerate(inst):
        print("      value[{}] = {}".format(i, value))


def inspect_class_inst(inst: 'ClassInstance'):
    print("    Class: {}".format(inst.class_object.name))
    print("    Members:")
    for i, value in enumerate(inst.member_data):
        print("      {}: {}".format(inst.class_object.members[i].name, value))


if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="NRBF Test Data Visualizer")
    parser.add_argument("--file", "-f", help="Data file to parse")

    args = parser.parse_args()
    if args.file is None:
        print("No input file specified")
        sys.exit(1)

    formatter = BinaryFormatter()
    ds = formatter._data_store
    formatter.read_file(args.file)
    inspect_classes(ds.classes, ds.libraries)
    inspect_objects(ds.objects)
