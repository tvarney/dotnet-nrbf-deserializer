#!/usr/bin/env python3

from nrbf.object import DataStore, ClassInstance

import typing
if typing.TYPE_CHECKING:
    from typing import Dict, Tuple
    from nrbf.object import ClassObject, Instance


def inspect_classes(classes: 'Dict[Tuple[int, str], ClassObject]', libraries: 'Dict[int, str]'):
    print("Read {} classes".format(len(classes)))
    for class_key, class_obj in classes.items():
        print("  Class {} [Library {}]".format(class_key[1], libraries[class_key[0]]))
        for member in class_obj.members:
            extra_info = member.extra_info.name if member.binary_type == 0 else member.extra_info
            print("    {}: {}, {}".format(member.name, member.binary_type.name, extra_info))


def inspect_objects(objects: 'Dict[int, Instance]'):
    print("Read {} objects".format(len(objects)))
    for obj_id, obj in objects.items():
        print("  object[{}]".format(obj_id, type(obj).__name__))
        inspect_instance(obj)


def inspect_instance(instance: 'Instance') -> None:
    instance_type = type(instance)
    if instance_type is ClassInstance:
        instance: ClassInstance
        inspect_class_inst(instance)


def inspect_class_inst(inst: 'ClassInstance'):
    print("    Class: {}".format(inst.class_object.name))
    print("    Members:")
    for i, value in enumerate(inst.member_data):
        print("      {}: {}".format(inst.class_object.members[i].name, value))


if __name__=="__main__":
    ds = DataStore()
    ds.read_file("./testdata/primitives.dat")
    inspect_classes(ds.classes, ds.libraries)
    inspect_objects(ds.objects)
