
import unittest

from dotnet.enum import BinaryType, PrimitiveType
from dotnet.structures import ClassTypeInfo, ExtraTypeInfo, NullReferenceMultiple


class TestExtraTypeInfo(unittest.TestCase):
    def test_validate_class(self):
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Class, PrimitiveType.Byte))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Class, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Class, "System.Int32"))
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.Class, ClassTypeInfo("MyClass", 2)))

    def test_validate_object(self):
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Object, PrimitiveType.Byte))
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.Object, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Object, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Object, ClassTypeInfo("MyClass", 2)))

    def test_validate_object_array(self):
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.ObjectArray, PrimitiveType.Byte))
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.ObjectArray, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.ObjectArray, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.ObjectArray, ClassTypeInfo("MyClass", 2)))

    def test_validate_primitive(self):
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.Primitive, PrimitiveType.Byte))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Primitive, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Primitive, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.Primitive, ClassTypeInfo("MyClass", 2)))

    def test_validate_primitive_array(self):
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.PrimitiveArray, PrimitiveType.Byte))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.PrimitiveArray, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.PrimitiveArray, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.PrimitiveArray, ClassTypeInfo("MyClass", 2)))

    def test_validate_string(self):
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.String, PrimitiveType.Byte))
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.String, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.String, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.String, ClassTypeInfo("MyClass", 2)))

    def test_validate_string_array(self):
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.StringArray, PrimitiveType.Byte))
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.StringArray, None))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.StringArray, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.StringArray, ClassTypeInfo("MyClass", 2)))

    def test_validate_system_class(self):
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.SystemClass, PrimitiveType.Byte))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.SystemClass, None))
        self.assertTrue(ExtraTypeInfo.validate(BinaryType.SystemClass, "System.Int32"))
        self.assertFalse(ExtraTypeInfo.validate(BinaryType.SystemClass, ClassTypeInfo("MyClass", 2)))


class TestNullReferenceStruct(unittest.TestCase):
    def test_length(self):
        self.assertEqual(len(NullReferenceMultiple(100)), 100)

    def test_iter(self):
        self.assertEqual(list(NullReferenceMultiple(100)), [None] * 100)
