# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: common.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0c\x63ommon.proto\x1a\x1fgoogle/protobuf/timestamp.proto\"\x89\x01\n\x10SerializedObject\x12\x0e\n\x06method\x18\x01 \x01(\t\x12\x12\n\ndefinition\x18\x02 \x01(\x0c\x12\x15\n\rwas_it_raised\x18\x03 \x01(\x08\x12!\n\x14stringized_traceback\x18\x04 \x01(\tH\x00\x88\x01\x01\x42\x17\n\x15_stringized_traceback\"n\n\x10PartialRunResult\x12\x13\n\x0bis_complete\x18\x01 \x01(\x08\x12\x12\n\x04logs\x18\x02 \x03(\x0b\x32\x04.Log\x12&\n\x06result\x18\x03 \x01(\x0b\x32\x11.SerializedObjectH\x00\x88\x01\x01\x42\t\n\x07_result\"{\n\x03Log\x12\x0f\n\x07message\x18\x01 \x01(\t\x12\x1a\n\x06source\x18\x02 \x01(\x0e\x32\n.LogSource\x12\x18\n\x05level\x18\x03 \x01(\x0e\x32\t.LogLevel\x12-\n\ttimestamp\x18\x04 \x01(\x0b\x32\x1a.google.protobuf.Timestamp*.\n\tLogSource\x12\x0b\n\x07\x42UILDER\x10\x00\x12\n\n\x06\x42RIDGE\x10\x01\x12\x08\n\x04USER\x10\x02*Z\n\x08LogLevel\x12\t\n\x05TRACE\x10\x00\x12\t\n\x05\x44\x45\x42UG\x10\x01\x12\x08\n\x04INFO\x10\x02\x12\x0b\n\x07WARNING\x10\x03\x12\t\n\x05\x45RROR\x10\x04\x12\n\n\x06STDOUT\x10\x05\x12\n\n\x06STDERR\x10\x06\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'common_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_LOGSOURCE']._serialized_start=426
  _globals['_LOGSOURCE']._serialized_end=472
  _globals['_LOGLEVEL']._serialized_start=474
  _globals['_LOGLEVEL']._serialized_end=564
  _globals['_SERIALIZEDOBJECT']._serialized_start=50
  _globals['_SERIALIZEDOBJECT']._serialized_end=187
  _globals['_PARTIALRUNRESULT']._serialized_start=189
  _globals['_PARTIALRUNRESULT']._serialized_end=299
  _globals['_LOG']._serialized_start=301
  _globals['_LOG']._serialized_end=424
# @@protoc_insertion_point(module_scope)
